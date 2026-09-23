# Data Flow

1. A device is discovered or an agent enrolls.
2. Identity observations are correlated into a stable device record.
3. Agent heartbeats update liveness.
4. Telemetry samples are validated and persisted.
5. State transitions append device events.
6. Alert rules evaluate incoming telemetry/events.
7. Realtime updates are broadcast to connected clients.
