from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from app.core.config import Settings
from app.domain.alerts.notifications import NotificationChannel
from app.infrastructure.repositories.mobile_push import (
    PushTarget,
    SqlAlchemyMobilePushRepository,
)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_FCM_TOKEN_HOSTS = {"oauth2.googleapis.com", "www.googleapis.com"}
_PROJECT_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _b64url(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _jwt_part(payload: Mapping[str, object]) -> str:
    return _b64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def _rs256_jwt(private_key_pem: str, claims: Mapping[str, object]) -> str:
    header = _jwt_part({"alg": "RS256", "typ": "JWT"})
    body = _jwt_part(claims)
    signing_input = f"{header}.{body}".encode("ascii")
    key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("FCM service account key must be RSA")
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{body}.{_b64url(signature)}"


def _es256_jwt(
    *,
    private_key_pem: str,
    key_id: str,
    team_id: str,
    issued_at: int,
) -> str:
    header = _jwt_part({"alg": "ES256", "kid": key_id})
    body = _jwt_part({"iss": team_id, "iat": issued_at})
    signing_input = f"{header}.{body}".encode("ascii")
    key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError("APNs provider key must use an EC private key")
    der_signature = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_signature)
    component_bytes = (key.curve.key_size + 7) // 8
    signature = r.to_bytes(component_bytes, "big") + s.to_bytes(component_bytes, "big")
    return f"{header}.{body}.{_b64url(signature)}"


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} push configuration must be a JSON object")
    return dict(value)


def _string(config: Mapping[str, object], name: str) -> str:
    value = config.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"push configuration requires {name}")
    return value.strip()


class MobilePushTransport:
    def __init__(
        self,
        repository: SqlAlchemyMobilePushRepository,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._settings = settings

    def send(
        self,
        channel: NotificationChannel,
        payload: dict[str, object],
        secret: str,
    ) -> None:
        config = self._decode_secret(secret)
        user_ids = self._string_set(channel.config.get("userIds"), field="userIds")
        roles = self._string_set(channel.config.get("roles"), field="roles")
        if user_ids is None and roles is None:
            roles = {"operator", "administrator"}
        if roles is not None and not roles <= {"viewer", "operator", "administrator"}:
            raise ValueError("push roles contain unsupported values")

        targets = self._repository.list_targets(user_ids=user_ids, roles=roles)
        if not targets:
            return

        failures: list[str] = []
        fcm_targets = [target for target in targets if target.provider == "fcm"]
        apns_targets = [target for target in targets if target.provider == "apns"]
        if fcm_targets:
            failures.extend(self._send_fcm(fcm_targets, payload, config))
        if apns_targets:
            failures.extend(self._send_apns(apns_targets, payload, config))
        if failures:
            raise RuntimeError("mobile push transient delivery failure")

    @staticmethod
    def _decode_secret(secret: str) -> dict[str, object]:
        try:
            payload = json.loads(secret)
        except json.JSONDecodeError as exc:
            raise ValueError("push notification secret must be JSON") from exc
        if not isinstance(payload, dict):
            raise TypeError("push notification secret must be a JSON object")
        return dict(payload)

    @staticmethod
    def _string_set(value: object, *, field: str) -> set[str] | None:
        if value is None:
            return None
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError(f"push channel config {field} must be a non-empty string array")
        if not value:
            raise ValueError(f"push channel config {field} cannot be empty")
        return {str(item).strip() for item in value}

    @staticmethod
    def _notification(payload: Mapping[str, object]) -> tuple[str, str, dict[str, str]]:
        transition = str(payload.get("event", "alert")).removeprefix("alert.")
        device = str(payload.get("deviceId", "unknown-device"))
        metric = str(payload.get("metricName", "unknown-metric"))
        value = str(payload.get("value", ""))
        title = f"DeviceMesh alert {transition}"[:120]
        body = f"{device} · {metric}={value}"[:240]
        data = {
            key: str(value)
            for key, value in payload.items()
            if value is not None
        }
        return title, body, data

    def _send_fcm(
        self,
        targets: list[PushTarget],
        payload: Mapping[str, object],
        config: Mapping[str, object],
    ) -> list[str]:
        fcm = _object(config.get("fcm"), "fcm")
        project_id = _string(fcm, "projectId")
        if not _PROJECT_RE.fullmatch(project_id):
            raise ValueError("FCM projectId is invalid")
        access_token = self._fcm_access_token(fcm)
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        title, body, data = self._notification(payload)
        failures: list[str] = []

        with httpx.Client(timeout=self._settings.notification_delivery_timeout_seconds) as client:
            for target in targets:
                response = client.post(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "message": {
                            "token": target.token,
                            "notification": {"title": title, "body": body},
                            "data": data,
                            "android": {"priority": "HIGH"},
                        }
                    },
                )
                if response.is_success:
                    continue
                if response.status_code in {404, 410}:
                    self._repository.disable(target.id)
                    continue
                failures.append(f"fcm:{response.status_code}")
        return failures

    def _fcm_access_token(self, config: Mapping[str, object]) -> str:
        client_email = _string(config, "clientEmail")
        private_key = _string(config, "privateKey")
        token_uri = str(config.get("tokenUri", "https://oauth2.googleapis.com/token")).strip()
        parsed = urlsplit(token_uri)
        if parsed.scheme != "https" or parsed.hostname not in _FCM_TOKEN_HOSTS:
            raise ValueError("FCM tokenUri must use Google's HTTPS OAuth endpoint")

        now = int(time.time())
        assertion = _rs256_jwt(
            private_key,
            {
                "iss": client_email,
                "scope": _FCM_SCOPE,
                "aud": token_uri,
                "iat": now,
                "exp": now + 3600,
            },
        )
        with httpx.Client(timeout=self._settings.notification_delivery_timeout_seconds) as client:
            response = client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("FCM OAuth token exchange failed") from exc
            body = response.json()
        token = body.get("access_token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise RuntimeError("FCM OAuth response did not contain an access token")
        return token

    def _send_apns(
        self,
        targets: list[PushTarget],
        payload: Mapping[str, object],
        config: Mapping[str, object],
    ) -> list[str]:
        apns = _object(config.get("apns"), "apns")
        team_id = _string(apns, "teamId")
        key_id = _string(apns, "keyId")
        bundle_id = _string(apns, "bundleId")
        private_key = _string(apns, "privateKey")
        provider_token = _es256_jwt(
            private_key_pem=private_key,
            key_id=key_id,
            team_id=team_id,
            issued_at=int(time.time()),
        )
        title, body, data = self._notification(payload)
        failures: list[str] = []
        with httpx.Client(
            timeout=self._settings.notification_delivery_timeout_seconds,
            http2=True,
        ) as client:
            for target in targets:
                host = (
                    "api.sandbox.push.apple.com"
                    if target.environment == "sandbox"
                    else "api.push.apple.com"
                )
                response = client.post(
                    f"https://{host}/3/device/{target.token}",
                    headers={
                        "authorization": f"bearer {provider_token}",
                        "apns-topic": bundle_id,
                        "apns-push-type": "alert",
                        "apns-priority": "10",
                    },
                    json={
                        "aps": {
                            "alert": {"title": title, "body": body},
                            "sound": "default",
                        },
                        "devicemesh": data,
                    },
                )
                if response.is_success:
                    continue
                if response.status_code in {404, 410}:
                    self._repository.disable(target.id)
                    continue
                failures.append(f"apns:{response.status_code}")
        return failures
