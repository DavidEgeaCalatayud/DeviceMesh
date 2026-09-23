import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "protocol" / "schemas"
FIXTURES = ROOT / "protocol" / "fixtures"


def validate(schema_name: str, fixture: Path) -> list[object]:
    schema = json.loads((SCHEMAS / schema_name).read_text())
    payload = json.loads(fixture.read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return list(validator.iter_errors(payload))


def test_valid_protocol_fixtures() -> None:
    assert not validate("heartbeat.schema.json", FIXTURES / "valid" / "heartbeat-v1.json")
    assert not validate("telemetry.schema.json", FIXTURES / "valid" / "telemetry-v1.json")
    assert not validate("event.schema.json", FIXTURES / "valid" / "event-v1.json")


def test_invalid_telemetry_fixture_is_rejected() -> None:
    assert validate("telemetry.schema.json", FIXTURES / "invalid" / "telemetry-missing-agent.json")
