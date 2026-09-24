# V1.2 acceptance checklist

- [ ] Synthetic monitor definitions persist through Alembic.
- [ ] Probe observations are immutable and attributable to probe + monitor.
- [ ] HTTP/TCP/ICMP executors are protocol-native and bounded by timeout.
- [ ] Service availability 24h/7d/30d is calculated independently of agent availability.
- [ ] Service outages and latency are visible in API and web UI.
- [ ] Operator UI can create/cancel maintenance windows.
- [ ] Operator UI can queue only allowlisted remote operations and inspect their history/results.
- [ ] No shell/process execution primitive is introduced.
- [ ] Backend, Web, Integration, Security and Network Probe CI are green.
