# WebSocket API

`/ws/events` is reserved for realtime device/event updates. V1 uses server-pushed JSON envelopes. Clients must tolerate new event types and reconnect with exponential backoff.
