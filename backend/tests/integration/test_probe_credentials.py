from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.synthetics.models import SyntheticMonitorKind
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticProbeAuthenticationError,
)
from app.infrastructure.security.probe_credentials import ProbeCredentialService


def test_probe_token_rotation_immediately_invalidates_previous_token() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    registration = repository.create_probe(
        name=f"rotate-{uuid4()}",
        location="Murcia",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=datetime.now(UTC),
    )

    assert repository.authenticate_probe(registration.token).id == registration.probe.id
    rotated = ProbeCredentialService(SessionFactory).rotate(registration.probe.id)
    assert rotated.probe_id == registration.probe.id
    assert rotated.token != registration.token

    with pytest.raises(SyntheticProbeAuthenticationError):
        repository.authenticate_probe(registration.token)
    assert repository.authenticate_probe(rotated.token).id == registration.probe.id
