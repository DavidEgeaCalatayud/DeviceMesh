# Component Diagrams

## Backend

```text
API adapters -> Application use cases -> Domain
                    |                   ^
                    v                   |
              Repository ports -> Infrastructure adapters
```

## Agent

```text
Host -> collectors -> telemetry snapshot -> protocol serializer -> authenticated transport
```
