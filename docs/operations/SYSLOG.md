# Syslog receiver

DeviceMesh runs Syslog as a dedicated UDP process rather than inside the HTTP API. The receiver
accepts bounded single-datagram messages, parses RFC5424 and a conservative RFC3164 fallback,
normalizes PRI into facility (0-23) and severity (0-7), and persists at most 4096 message
characters.

The default production listener is UDP/5514. Use a firewall or network ACL so only managed
network segments can reach it. The receiver does not interpret structured data as executable
content and never accepts multi-line or NUL payloads.

Messages are correlated to a DeviceMesh device first by the datagram source IP found in stable
device-interface identity and then by normalized hostname. Unmatched messages remain searchable
by source address.

The GET /api/v1/syslog endpoint supports bounded filters for device, source, severity, facility,
time and text. Syslog history is subject to DEVICEMESH_SYSLOG_RETENTION_DAYS and is deleted by
the elected scheduler worker; device and incident records are not cascaded by this retention job.
