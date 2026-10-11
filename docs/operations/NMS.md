# Network Management (SNMPv3, LLDP/CDP, routes, ARP and VLAN)

DeviceMesh polls explicitly configured network devices with SNMPv3 USM. Production targets use
HMAC-SHA-256 authentication and store only an opaque `authSecretRef` in PostgreSQL. The
authentication passphrase is resolved by the scheduler worker at runtime from
`/run/secrets/devicemesh-nms/<ref>` or `DEVICEMESH_NMS_SECRET_<REF>`.

## Data collected

The NMS worker records interface operational state, MTU, physical address, nominal speed,
64-bit octet counters and error counters. It also snapshots IPv4 routes, ARP entries and
Q-BRIDGE VLAN names. LLDP is the preferred physical-neighbor source; Cisco CDP is accepted as
a fallback. Missing rows in a completed poll are marked non-present rather than deleted, so
link and inventory changes remain observable.

Physical neighbors are persisted independently from approximate discovery segments. When a
remote chassis MAC or system name matches a known DeviceMesh device, the neighbor is linked to
that stable device identity.

## Security boundaries

- No SNMP community string is persisted or exposed.
- The API returns secret references, never resolved values.
- NMS targets are literal IP addresses to avoid DNS target pivoting.
- Poll errors are normalized to `poll_failed`; credential values never enter API or worker logs.
- SNMP SET is not implemented. The NMS plane is read-only.
- Strong SNMPv3 privacy is not claimed in this release; the implemented baseline is
  authenticated SNMPv3 with HMAC-SHA-256.

## Operator API

Create and control targets through `/api/v1/operator/network/targets`. Read inventory through
`/api/v1/network/interfaces`, `/neighbors`, `/routes`, `/arp`, `/vlans` and
`/interface-counters`.
