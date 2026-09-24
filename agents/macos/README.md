# DeviceMesh macOS Agent

Native Swift host agent for macOS. It implements the same DeviceMesh Agent Protocol v1 used by Windows and Linux while keeping credentials in the macOS Keychain.

## Capabilities

- one-time enrollment and persistent dedicated agent credential in Keychain
- authenticated heartbeat with macOS host/network identity
- CPU, memory, root-volume, network and uptime telemetry
- pull-based remote operations restricted to:
  - `telemetry.collect`
  - `inventory.refresh`
  - `agent.health_check`
- user-scoped `launchd` reference configuration

The agent intentionally has **no shell, AppleScript, arbitrary executable path or process-execution operation**.

## Build and test

```bash
cd agents/macos
swift build -c release
swift test
```

The release executable is `.build/release/devicemesh-macos-agent`.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `DEVICEMESH_SERVER` | DeviceMesh API URL | `http://localhost:8000` |
| `DEVICEMESH_AGENT_ID` | stable agent identifier | current host name |
| `DEVICEMESH_INTERVAL_SECONDS` | heartbeat/telemetry interval | `30` (minimum `5`) |
| `DEVICEMESH_ENROLLMENT_TOKEN` | one-time enrollment token | none |
| `DEVICEMESH_AGENT_CREDENTIAL` | explicit runtime override, mainly for CI/debug | none |

For normal installations, use `DEVICEMESH_ENROLLMENT_TOKEN` only for the first launch. After enrollment succeeds, remove it: the issued credential is stored as a generic-password item in Keychain under service `io.github.davidegeacalatayud.devicemesh.macos-agent`.

## Install as a user LaunchAgent

V1 is intentionally user-scoped so the process can use that user's Keychain without root privileges.

```bash
sudo install -m 0755 .build/release/devicemesh-macos-agent /usr/local/libexec/devicemesh-macos-agent
mkdir -p ~/Library/LaunchAgents
cp launchd/io.github.davidegeacalatayud.devicemesh.macos-agent.plist ~/Library/LaunchAgents/
```

Edit the plist server URL, then bootstrap it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/io.github.davidegeacalatayud.devicemesh.macos-agent.plist
launchctl kickstart -k gui/$(id -u)/io.github.davidegeacalatayud.devicemesh.macos-agent
```

For first enrollment, launch the executable once from a terminal with `DEVICEMESH_ENROLLMENT_TOKEN` set, verify the device appears in DeviceMesh, then start the LaunchAgent without the token.

## Current boundary

This first native macOS agent does not require root, EndpointSecurity, system extensions or privileged helpers. That keeps the trust surface small. A future signed `.pkg` can add richer installation/update flows without changing Agent Protocol v1.
