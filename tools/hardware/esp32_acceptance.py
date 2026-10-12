#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

import serial


REQUIRED_MARKERS = ("DeviceMesh ESP32 agent ",)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout_seconds
    seen: set[str] = set()
    with serial.Serial(args.port, args.baud, timeout=1) as stream:
        while time.monotonic() < deadline:
            line = stream.readline().decode("utf-8", errors="replace").strip()
            if line:
                print(line, flush=True)
            for marker in REQUIRED_MARKERS:
                if marker in line:
                    seen.add(marker)
            if "Guru Meditation Error" in line or "Task watchdog got triggered" in line:
                print("firmware crash/watchdog failure detected", file=sys.stderr)
                return 2
            if len(seen) == len(REQUIRED_MARKERS):
                return 0

    missing = sorted(set(REQUIRED_MARKERS) - seen)
    print(f"missing serial markers: {missing}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
