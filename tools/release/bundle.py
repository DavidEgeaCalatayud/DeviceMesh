#!/usr/bin/env python3
"""Package a committed source tree; no runtime configuration or secret directories."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "release-bundle")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    archive = args.output / f"devicemesh-server-{sha[:12]}.tar.gz"
    subprocess.run(["git", "archive", "--format=tar.gz", f"--prefix=devicemesh-{sha[:12]}/", "-o", str(archive), "HEAD"], cwd=ROOT, check=True)
    with tarfile.open(archive) as bundle:
        forbidden = [m.name for m in bundle if "/.secrets/" in m.name or m.name.endswith("/.env.production")]
        if forbidden:
            raise SystemExit("Refusing to package secrets or live environment configuration")
    manifest = args.output / "release.json"
    manifest.write_text(json.dumps({"commit": sha, "protocolVersion": 1, "sourceArchive": archive.name,
                                    "buildsRequired": ["server container", "web container"],
                                    "signed": False}, indent=2) + "\n")
    with (args.output / "SHA256SUMS").open("w") as checksums:
        for path in sorted(args.output.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                with path.open("rb") as stream:
                    checksums.write(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {path.name}\n")
    print(archive)


if __name__ == "__main__":
    main()
