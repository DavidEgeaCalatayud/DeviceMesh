#!/usr/bin/env python3
"""Strict deployment validation; environment values are never executed as shell."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parents[2]
SECRET_NAMES = ("postgres_password", "application_password", "application_url", "migration_url", "operator_token")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("invalid env line; expected KEY=value")
        if key in values or "$" in value or "`" in value or "\x00" in value:
            raise ValueError("duplicate keys and env interpolation are not allowed")
        values[key] = value.strip()
    return values


def validate(values: dict[str, str], check_secrets: bool = True) -> Path:
    domain = values.get("DEVICEMESH_DOMAIN", "")
    if not re.fullmatch(r"(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", domain):
        raise ValueError("domain must be a DNS hostname, without scheme, port or path")
    if domain in {"mesh.example.com", "example.com"}:
        raise ValueError("replace the example domain with your deployment hostname")
    origins = json.loads(values.get("DEVICEMESH_CORS_ORIGINS", "[]"))
    if origins != [f"https://{domain}"]:
        raise ValueError("CORS origins must contain exactly the HTTPS deployment origin")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", values.get("COMPOSE_PROJECT_NAME", "devicemesh")):
        raise ValueError("invalid compose project name")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", values.get("DEVICEMESH_IMAGE_TAG", "")):
        raise ValueError("set an explicit image tag")
    if not 1 <= int(values.get("BACKUP_RETENTION_DAYS", "30")) <= 3650:
        raise ValueError("backup retention must be between 1 and 3650 days")
    directory = Path(values.get("DEVICEMESH_SECRETS_DIR", ".secrets"))
    if not directory.is_absolute():
        directory = ROOT / directory
    if check_secrets:
        if directory.stat().st_mode & 0o077:
            raise ValueError("secrets directory must have mode 0700")
        for name in SECRET_NAMES:
            file = directory / name
            if not file.is_file() or len(file.read_text().strip()) < 32:
                raise ValueError(f"missing or invalid secret file: {name}")
    return directory


def initialize(directory: Path) -> None:
    if directory.exists() and any(directory.iterdir()):
        if not all((directory / name).is_file() for name in SECRET_NAMES):
            raise ValueError("partial secrets directory: restore it before continuing")
        return
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    owner, application = secrets.token_hex(32), secrets.token_hex(32)
    values = {"postgres_password": owner, "application_password": application,
              "operator_token": secrets.token_hex(32),
              "application_url": f"postgresql+psycopg://devicemesh_app:{application}@postgres:5432/devicemesh",
              "migration_url": f"postgresql+psycopg://devicemesh_owner:{owner}@postgres:5432/devicemesh"}
    for name, value in values.items():
        file = directory / name
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as stream:
            stream.write(value + "\n")
        # Parent is private. Compose grants each container only the requested files;
        # file modes must allow the container's unprivileged application UID to read.
        file.chmod(0o644)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.production")
    parser.add_argument("--init-secrets", action="store_true")
    parser.add_argument("--get")
    args = parser.parse_args()
    try:
        values = read_env(args.env_file)
        if args.get:
            print(values.get(args.get, ""))
            return
        directory = validate(values, check_secrets=False)
        if args.init_secrets:
            initialize(directory)
        validate(values)
        print("Deployment configuration is valid.")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Configuration error: {exc}\n")


if __name__ == "__main__":
    main()
