import base64
import json

import httpx

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from app.infrastructure.mobile_push_delivery import (
    _apns_token_is_invalid,
    _es256_jwt,
    _fcm_token_is_invalid,
    _rs256_jwt,
)


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def test_fcm_service_account_jwt_is_valid_rs256() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    token = _rs256_jwt(
        pem,
        {
            "iss": "service@example.iam.gserviceaccount.com",
            "aud": "https://oauth2.googleapis.com/token",
            "scope": "scope",
            "iat": 1,
            "exp": 2,
        },
    )
    header, body, signature = token.split(".")
    assert json.loads(_decode(header)) == {"alg": "RS256", "typ": "JWT"}
    key.public_key().verify(
        _decode(signature),
        f"{header}.{body}".encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_apns_provider_token_uses_raw_es256_signature() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    token = _es256_jwt(
        private_key_pem=pem,
        key_id="ABC123",
        team_id="TEAM123",
        issued_at=1_700_000_000,
    )
    header, body, signature = token.split(".")
    raw = _decode(signature)
    assert len(raw) == 64
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    key.public_key().verify(
        encode_dss_signature(r, s),
        f"{header}.{body}".encode("ascii"),
        ec.ECDSA(hashes.SHA256()),
    )


def test_fcm_invalid_token_requires_unregistered_provider_reason() -> None:
    request = httpx.Request("POST", "https://fcm.googleapis.com/v1/projects/p/messages:send")
    unregistered = httpx.Response(
        404,
        request=request,
        json={
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "UNREGISTERED",
                    }
                ]
            }
        },
    )
    generic_not_found = httpx.Response(404, request=request, json={"error": {"status": "NOT_FOUND"}})
    invalid_payload = httpx.Response(
        400,
        request=request,
        json={
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "INVALID_ARGUMENT",
                    }
                ]
            }
        },
    )
    assert _fcm_token_is_invalid(unregistered)
    assert not _fcm_token_is_invalid(generic_not_found)
    assert not _fcm_token_is_invalid(invalid_payload)


def test_apns_invalid_token_recognizes_only_token_reasons() -> None:
    request = httpx.Request("POST", "https://api.push.apple.com/3/device/token")
    assert _apns_token_is_invalid(
        httpx.Response(410, request=request, json={"reason": "Unregistered"})
    )
    assert _apns_token_is_invalid(
        httpx.Response(400, request=request, json={"reason": "BadDeviceToken"})
    )
    assert _apns_token_is_invalid(
        httpx.Response(400, request=request, json={"reason": "DeviceTokenNotForTopic"})
    )
    assert not _apns_token_is_invalid(
        httpx.Response(400, request=request, json={"reason": "PayloadEmpty"})
    )
    assert not _apns_token_is_invalid(
        httpx.Response(403, request=request, json={"reason": "InvalidProviderToken"})
    )
