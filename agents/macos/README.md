# DeviceMesh macOS Agent

Native Swift host agent for macOS. It implements the same DeviceMesh Agent Protocol v1 and host-agent security boundary used by Windows and Linux while keeping its dedicated credential in the macOS Keychain.

## Parity status

The macOS host agent is maintained at the same current functional level as the Windows and Linux host agents:

- one-time enrollment and persistent dedicated agent credential
- authenticated heartbeat with host/network identity
- portable host telemetry
- controlled pull-based remote operations
- background service integration
- dedicated CI build/tests
- no arbitrary command execution

Platform-specific implementation details remain native: Swift + Keychain + Mach/BSD APIs + `launchd` on macOS, .NET/Windows Service semantics on Windows, and Python + `systemd` on Linux.

## Capabilities

Identity reported in heartbeat:

- hostname
- `macOS` and OS version
- CPU architecture
- manufacturer (`Apple Inc.`)
- IPv4/IPv6 addresses
- interface MAC addresses

Portable metrics:

- `host.cpu.utilization.percent`
- `host.memory.total.bytes`
- `host.memory.used.bytes`
- `host.memory.utilization.percent`
- `host.disk.total.bytes`
- `host.disk.free.bytes`
- `host.disk.used.bytes`
- `host.disk.utilization.percent`
- `host.network.received.bytes`
- `host.network.sent.bytes`
- `host.uptime.seconds`

The remote-operation executor accepts only:

- `telemetry.collect`
- `inventory.refresh`
- `agent.health_check`

The agent intentionally has **no shell, AppleScript, arbitrary executable path, subprocess or generic process-execution operation**. Operation arguments are rejected in the current protocol implementation.

## Credential model

The enrollment credential is stored as a generic-password item in Keychain under service:

```text
io.github.davidegeacalatayud.devicemesh.macos-agent
```

The item uses `AfterFirstUnlockThisDeviceOnly`: it remains usable by the user-scoped LaunchAgent after login but is not synchronizable or portable to another device.

`DEVICEMESH_AGENT_CREDENTIAL` exists only as an explicit runtime override for CI/debugging. Normal installations should use Keychain.

## Build and test

```bash
cd agents/macos
swift build -c release
swift test
```

The test suite covers:

- configuration and protocol limits
- wire payload shape
- live macOS identity/metric collection
- Keychain save/load/replace/remove
- enrollment and stored-credential reuse
- authenticated HTTP request headers and endpoint paths
- `204 No Content` operation claims
- remote-operation allowlist and lifecycle

The release executable is:

```text
.build/release/devicemesh-macos-agent
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `DEVICEMESH_SERVER` | DeviceMesh API URL | `http://localhost:8000` |
| `DEVICEMESH_AGENT_ID` | stable agent identifier (max 128 chars) | current host name |
| `DEVICEMESH_INTERVAL_SECONDS` | heartbeat/telemetry interval | `30` (minimum `5`) |
| `DEVICEMESH_ENROLLMENT_TOKEN` | one-time enrollment token | none |
| `DEVICEMESH_AGENT_CREDENTIAL` | explicit runtime override, CI/debug only | none |

`DEVICEMESH_SERVER` must be an absolute HTTP/HTTPS URL. Embedded URL credentials, query strings and fragments are rejected so the server base cannot accidentally become a secret carrier or ambiguous endpoint root.

For normal installations, use `DEVICEMESH_ENROLLMENT_TOKEN` only for the first launch. After enrollment succeeds, remove it; subsequent requests use the Keychain credential.

## Install as a user LaunchAgent

The current agent is intentionally user-scoped so it can use that user's Keychain without a privileged helper.

```bash
sudo install -m 0755 .build/release/devicemesh-macos-agent /usr/local/libexec/devicemesh-macos-agent
mkdir -p ~/Library/LaunchAgents
cp launchd/io.github.davidegeacalatayud.devicemesh.macos-agent.plist ~/Library/LaunchAgents/
```

Edit the plist server URL, then bootstrap it:

```bash
plutil -lint ~/Library/LaunchAgents/io.github.davidegeacalatayud.devicemesh.macos-agent.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/io.github.davidegeacalatayud.devicemesh.macos-agent.plist
launchctl kickstart -k gui/$(id -u)/io.github.davidegeacalatayud.devicemesh.macos-agent
```

For first enrollment, launch the executable once from a terminal with `DEVICEMESH_ENROLLMENT_TOKEN` set, verify the device appears in DeviceMesh, then start the LaunchAgent without the token.

The agent handles `SIGINT` and `SIGTERM` explicitly and cancels its worker cleanly before exit.

## Logging and troubleshooting

The agent uses macOS Unified Logging rather than plaintext files in `/tmp`.

Stream logs live:

```bash
log stream --style compact --predicate 'subsystem == "io.github.davidegeacalatayud.devicemesh"'
```

Inspect recent logs:

```bash
log show --last 30m --style compact --predicate 'subsystem == "io.github.davidegeacalatayud.devicemesh"'
```

Check launchd state:

```bash
launchctl print gui/$(id -u)/io.github.davidegeacalatayud.devicemesh.macos-agent
```

Restart the agent:

```bash
launchctl kickstart -k gui/$(id -u)/io.github.davidegeacalatayud.devicemesh.macos-agent
```

Unload it:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/io.github.davidegeacalatayud.devicemesh.macos-agent.plist
```

## Current boundary

The agent does not require root, EndpointSecurity, system extensions or privileged helpers. This deliberately keeps its trust surface comparable to the current Windows/Linux host-agent feature set. Signed `.pkg` distribution, notarization and automatic updates remain release/productization work shared conceptually with MSI/DEB/RPM packaging on the other desktop agents.
