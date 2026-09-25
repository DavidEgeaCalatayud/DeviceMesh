import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.repositories.synthetics import (
    SyntheticProbeNotFoundError,
    SyntheticProbeRow,
)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RotatedProbeCredential:
    probe_id: str
    token: str
    rotated_at: datetime


class ProbeCredentialService:
    """Rotate probe bearer credentials without retaining plaintext tokens."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def rotate(self, probe_id: str, *, now: datetime | None = None) -> RotatedProbeCredential:
        current = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        with self._session_factory.begin() as session:
            row = session.get(SyntheticProbeRow, probe_id)
            if row is None:
                raise SyntheticProbeNotFoundError(probe_id)
            row.token_hash = _token_hash(token)
            row.updated_at = current
        return RotatedProbeCredential(probe_id=probe_id, token=token, rotated_at=current)
