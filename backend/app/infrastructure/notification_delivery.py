import json
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings
from app.domain.alerts.notifications import NotificationChannel
from app.infrastructure.repositories.notifications import SqlAlchemyNotificationRepository

_SECRET_REF_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class NotificationSecretResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(self, secret_ref: str) -> str:
        if not _SECRET_REF_RE.fullmatch(secret_ref):
            raise ValueError("invalid notification secret reference")
        path = Path(self._settings.notification_secret_directory) / secret_ref
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        key = "DEVICEMESH_NOTIFICATION_SECRET_" + re.sub(
            r"[^A-Za-z0-9]",
            "_",
            secret_ref,
        ).upper()
        value = os.environ.get(key, "").strip()
        if value:
            return value
        raise RuntimeError(f"notification secret '{secret_ref}' is not configured")


class NotificationTransport:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(
        self,
        channel: NotificationChannel,
        payload: dict[str, object],
        secret: str,
    ) -> None:
        if channel.kind.value == "webhook":
            self._post_webhook(secret, payload)
            return
        if channel.kind.value == "slack":
            self._post_webhook(secret, {"text": self._slack_text(payload)})
            return
        if channel.kind.value == "email":
            self._send_email(channel, payload, secret)
            return
        raise ValueError(f"unsupported notification channel kind: {channel.kind.value}")

    def _post_webhook(self, url: str, payload: dict[str, object]) -> None:
        parsed = urlsplit(url)
        allowed_schemes = {"https"} if self._settings.env == "production" else {"http", "https"}
        if parsed.scheme not in allowed_schemes or not parsed.hostname:
            raise ValueError("notification webhook must use an allowed HTTP(S) URL")
        with httpx.Client(timeout=self._settings.notification_delivery_timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()

    def _send_email(
        self,
        channel: NotificationChannel,
        payload: dict[str, object],
        secret: str,
    ) -> None:
        try:
            smtp = json.loads(secret)
        except json.JSONDecodeError as exc:
            raise ValueError("email notification secret must be JSON") from exc
        if not isinstance(smtp, dict):
            raise ValueError("email notification secret must be a JSON object")
        host = smtp.get("host")
        from_address = smtp.get("fromAddress")
        recipients = channel.config.get("to")
        if not isinstance(host, str) or not host.strip():
            raise ValueError("email secret requires host")
        if not isinstance(from_address, str) or not from_address.strip():
            raise ValueError("email secret requires fromAddress")
        if not isinstance(recipients, list) or not recipients or not all(
            isinstance(value, str) and value.strip() for value in recipients
        ):
            raise ValueError("email channel config requires a non-empty 'to' list")
        port = int(smtp.get("port", 587))
        security = str(smtp.get("security", "starttls"))
        if self._settings.env == "production" and security not in {"starttls", "ssl"}:
            raise ValueError("production email notifications require TLS")

        message = EmailMessage()
        message["From"] = from_address
        message["To"] = ", ".join(str(value) for value in recipients)
        prefix = str(channel.config.get("subjectPrefix", "DeviceMesh"))
        message["Subject"] = f"[{prefix}] {payload.get('event', 'alert')} {payload.get('deviceId', '')}"
        message.set_content(json.dumps(payload, indent=2, sort_keys=True))

        context = ssl.create_default_context()
        if security == "ssl":
            client: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=10, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=10)
        try:
            if security == "starttls":
                client.starttls(context=context)
            username = smtp.get("username")
            password = smtp.get("password")
            if isinstance(username, str) and username:
                if not isinstance(password, str):
                    raise ValueError("email username requires password")
                client.login(username, password)
            client.send_message(message)
        finally:
            client.quit()

    @staticmethod
    def _slack_text(payload: dict[str, object]) -> str:
        event = str(payload.get("event", "alert"))
        device = str(payload.get("deviceId", "unknown-device"))
        metric = str(payload.get("metricName", "unknown-metric"))
        value = payload.get("value")
        threshold = payload.get("threshold")
        return f"DeviceMesh {event}: {device} · {metric}={value} (threshold {threshold})"


class NotificationDispatcher:
    def __init__(
        self,
        repository: SqlAlchemyNotificationRepository,
        resolver: NotificationSecretResolver,
        transport: NotificationTransport,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._resolver = resolver
        self._transport = transport
        self._settings = settings

    def run_due(self, now: datetime) -> tuple[int, int]:
        delivered = 0
        failed = 0
        claimed = self._repository.claim_due(
            now,
            limit=self._settings.notification_delivery_batch_size,
            lease_seconds=self._settings.notification_delivery_lease_seconds,
        )
        for delivery, channel in claimed:
            try:
                secret = self._resolver.resolve(channel.secret_ref)
                self._transport.send(channel, delivery.payload, secret)
                self._repository.mark_delivered(delivery.id, now)
                delivered += 1
            except Exception as exc:
                self._repository.mark_failed(
                    delivery.id,
                    now,
                    type(exc).__name__,
                    max_attempts=self._settings.notification_delivery_max_attempts,
                )
                failed += 1
        return delivered, failed
