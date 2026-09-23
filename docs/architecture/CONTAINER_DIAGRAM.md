# Container Diagram

| Container | Technology | Responsibility |
|---|---|---|
| API | Python/FastAPI | Commands, queries, auth, ingestion, realtime |
| Database | PostgreSQL | Durable state and event history |
| Cache/coordination | Redis | Ephemeral coordination and fanout |
| Web | React/TypeScript | Main operator interface |
| Windows Agent | .NET | Host telemetry collection and publishing |
| Android | Kotlin/Compose | Mobile operations client |
| iOS | SwiftUI | Mobile operations client |
| ESP32 | C/ESP-IDF | Edge probe and sensor telemetry |
