# ADR-0009: Append-only device timeline

**Status:** Accepted

DeviceMesh stores both current device state and meaningful append-only events. Current state answers “what is true now”; events answer “what changed and when”. Alerts and audit views build on the event stream.
