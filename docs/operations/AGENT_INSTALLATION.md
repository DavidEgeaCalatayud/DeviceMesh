# Native agent installation

DeviceMesh distributes host agents as operating-system-native packages so an operator does not need a development toolchain on monitored machines.

## Windows

Release validation publishes `DeviceMesh-Agent-<version>-x64.msi` plus `SHA256SUMS`.

The MSI installs the self-contained .NET 8 executable under `Program Files\DeviceMesh\Agent` and registers `DeviceMeshAgent` as an automatic Windows Service using the Generic Host Windows Service lifetime. Upgrade handling is MSI major-upgrade based and rejects downgrades.

Before broad deployment, configure the service with the intended server/enrollment settings using the supported `DeviceMesh__...` environment variables or a managed `appsettings.json`. The credential issued on first enrollment is protected by the Windows credential store/DPAPI implementation already used by the agent.

Example unattended installation:

```powershell
msiexec /i DeviceMesh-Agent-1.4.0-x64.msi /qn /norestart
Get-Service DeviceMeshAgent
```

Uninstall:

```powershell
msiexec /x DeviceMesh-Agent-1.4.0-x64.msi /qn /norestart
```

Signing is intentionally separate from package construction. A production release must Authenticode-sign the executable/MSI before publication and publish the signature/checksum evidence.

## Linux

Release validation produces both `.deb` and `.rpm` packages. The package vendors Python dependencies under `/opt/devicemesh/lib`, installs a stable launcher at `/opt/devicemesh/bin/devicemesh-linux-agent`, installs the hardened `devicemesh-agent.service`, and creates the locked-down `devicemesh` service account when needed.

The package deliberately does not auto-start an unconfigured agent. Configure `/etc/devicemesh/agent.env` first, then enable it:

```bash
sudo install -m 0640 /etc/devicemesh/agent.env.example /etc/devicemesh/agent.env
sudo editor /etc/devicemesh/agent.env
sudo systemctl enable --now devicemesh-agent
sudo systemctl status devicemesh-agent
```

For Debian/Ubuntu:

```bash
sudo apt install ./devicemesh-linux-agent_<version>_amd64.deb
```

For RPM-family systems:

```bash
sudo rpm -U ./devicemesh-linux-agent-<version>-1.x86_64.rpm
```

State and the enrolled credential remain under `/var/lib/devicemesh` across package upgrades/removal by design. Remove them explicitly only when decommissioning the device and revoke the server-side credential as part of the same procedure.

## Release acceptance

For every package version:

1. verify `SHA256SUMS`;
2. install on a clean supported OS image;
3. enroll with a one-time token;
4. verify heartbeat, telemetry, remote allowlisted operations and credential persistence across reboot;
5. upgrade from the previous supported version and confirm identity/credential continuity;
6. uninstall and confirm the service is removed while state retention matches the documented policy.

The CI jobs prove build/test/package reproducibility. They do not replace clean-VM installation acceptance or code-signing verification.
