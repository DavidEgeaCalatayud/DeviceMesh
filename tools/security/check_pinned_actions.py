#!/usr/bin/env python3
"""Fail when a GitHub Actions workflow uses a mutable remote action reference."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
PINNED = re.compile(r"^[^@]+@[0-9a-fA-F]{40}$")


def main() -> None:
    failures: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        for match in USES.finditer(text):
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            if not PINNED.fullmatch(reference):
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(ROOT)}:{line}: {reference}")
    if failures:
        raise SystemExit(
            "Remote GitHub Actions must be pinned to an immutable 40-character commit SHA:\n"
            + "\n".join(failures)
        )


if __name__ == "__main__":
    main()
