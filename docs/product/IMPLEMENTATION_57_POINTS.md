# Seguimiento de los 57 puntos de DeviceMesh

Primera entrega: `feat/production-platform-foundations`. Base revisada: `9a23733` (post-PR #66).

Este documento conserva el alcance completo. **Implementado en main** significa que el criterio explícito que mantenía el punto abierto está implementado y validado por CI/acceptance dentro del alcance actual del producto. **Pendiente** significa que el punto todavía requiere implementación sustancial. Los scaffolds móviles y ESP32 siguen siendo scaffolds. Tras la reconciliación de septiembre de 2026 no quedan filas marcadas como **Parcial** ni **Parcial avanzado**.

| Nº | Área | Estado | Evidencia / siguiente criterio |
|---|---|---|---|
| 1 | Lo primero: terminar de verdad la V1 como producto instalable | Implementado en main | Compose productivo, migraciones, install, backup/restore, timer, retención, restore/restart y upgrade/smoke automatizados. Release Validation construye MSI, DEB/RPM y paquete macOS para los componentes productivos; Production acceptance levanta el stack completo en runner limpio y valida el borde HTTPS/Caddy con CA confiable, reinicio y persistencia. |
| 2 | Backend: evolucionarlo de backend funcional a plataforma | Implementado en main | Catálogo persistente con propietario, entorno, criticidad, tags y dispositivo; relación muchos-a-muchos con monitores; grupos de servicios; dependencias hard/soft con detección de ciclos y exposición de dependents/dependencies. |
| 3 | Service Incidents tiene que convertirse en Incident Management | Implementado en main | ACK, asignación, severidad, notas, causa, resolución, reapertura y timeline automática/manual; correlación temporal multimonitor a través de servicios/dependencias relacionados; impacto y postmortem editables. |
| 4 | SLO, SLI y Error Budgets | Implementado en main | SLI por éxito de checks y por disponibilidad temporal, ventanas 7/30/90, error budget en checks o segundos, estado unknown/stale, burn-rates 1h/6h/24h y política critical/warning. |
| 5 | Notificaciones y routing de alertas | Implementado en main | PR #66 añade canales webhook/Slack/email, routing por transición/métrica/dispositivo, supresión durante mantenimiento, secretos externos mediante `secretRef`, outbox PostgreSQL deduplicado, leases, backoff exponencial, dead-letter/retry manual y entrega desde el scheduler-worker. Backend, Integration, Security, HA, Failure, Performance, Production, Release y Documentation CI verdes. |
| 6 | Autenticación humana y RBAC | Implementado en main | Argon2id, roles viewer/operator/administrator, sesiones y refresh rotatorios, revocación, usuarios, desactivación, throttling y auditoría. PR #64 añade segundo factor de posesión con sólo SHA-256 persistido, rotación, revocación de sesiones, recuperación administrativa auditada y flujo web. OIDC/LDAP quedan como federación opcional futura, fuera del criterio V1 local. |
| 7 | Audit Log global | Implementado en main | Auditoría transaccional de operaciones de dominio y UI admin, más middleware transversal para toda mutación humana autenticada heredada/actual que aún no tenga evento semántico propio; captura actor, ruta, método, estado, IP y request ID. |
| 8 | Alta disponibilidad y escalado horizontal del backend | Implementado en main | APIs stateless sobre PostgreSQL, Pub/Sub Redis para fan-out/reconexión y workers con advisory lock/failover. HA acceptance ejecuta dos réplicas API detrás de Caddy, verifica estado compartido, WebSocket cross-instance y continuidad/recuperación tras partición de red de una réplica. |
| 9 | Separar workers del proceso API | Implementado en main | Worker independiente con elección mediante advisory lock; API productiva desactiva jobs embebidos; offline sweep, synthetics y retention se ejecutan en el scheduler; integración PostgreSQL prueba líder único y failover al perder la sesión. |
| 10 | Distributed Probes: V1.3 está hecha, pero todavía falta bastante | Implementado en main | Dockerfile y systemd endurecidos, liveness local, cola SQLite acotada, concurrencia limitada, backpressure, backoff/jitter, rotación transaccional de bearer token con sólo hash persistido, expiración de credenciales a 90 días y runtime heartbeat con versión, uptime, cola/capacidad y concurrencia; operator API expone estado/lifecycle. |
| 11 | Synthetic monitoring mucho más profundo | Pendiente | HTTP/TCP/DNS/TLS e ICMP distribuido ya existen, junto a SLA/latencia y validación de destino. Falta profundizar assertions/configuración HTTP y autenticación/headers mediante referencias secretas, además de cerrar la UX/contrato correspondiente. |
| 12 | Consenso distribuido V2: rondas/quorum | Implementado en main | `RoundAwareSyntheticRepository` agrupa sólo observaciones de la misma ronda temporal, calcula mayoría estricta sobre probes activos/asignados y devuelve `insufficient_data` antes de quorum. Integración prueba rondas parciales, aislamiento de resultados de rondas anteriores y quorum 2/3 sin abrir incidentes prematuros. |
| 13 | Network Monitoring / NMS: aquí hay un campo enorme todavía | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 14 | LLDP/CDP y topología automática | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 15 | Más información de red | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 16 | Syslog | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 17 | Web: aún le falta convertirse en una aplicación completa de operaciones | Implementado en main | Navegación, Dashboard, Services, Incidents, detalle, Administration, Audit, login y búsqueda global Ctrl/Cmd+K. PR #61 convierte Maintenance, Operations, Synthetics y Probes en rutas de primera clase, conserva la vista agregada y alinea la allowlist web con diagnósticos DNS/route snapshot del backend; Playwright cubre las rutas reales. |
| 18 | UX web | Implementado en main | Estados de carga/error/vacío, búsqueda, URLs de detalle, formularios etiquetados, diseño adaptable y navegación operativa. PR #63 añade preferencia ES/EN persistente y vistas guardadas de deep-links con deduplicación, límite, validación y recuperación ante almacenamiento corrupto. |
| 19 | Android: prácticamente toda la aplicación real está pendiente | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 20 | Android: push notifications | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 21 | Android: seguridad | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 22 | Android testing/release | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 23 | iOS: también es fundamentalmente scaffold | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 24 | BLE provisioning desde Android/iOS | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 25 | ESP32: prácticamente todo el firmware real queda por desarrollar | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 26 | ESP32: sensores | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 27 | ESP32 como probe de red | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 28 | ESP32 production-ready | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 29 | Windows Agent | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 30 | Windows telemetry | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 31 | Windows remote operations | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 32 | Linux Agent | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 33 | Agente macOS | Implementado en main | Main incorporó el agente nativo y la paridad Windows/Linux en f199492; se conserva al integrar esta rama. |
| 34 | Observabilidad del propio DeviceMesh | Implementado en main | `/metrics` protegido cubre HTTP, ingesta, WS, devices/probes, incidentes, DB y jobs; Prometheus scrapea API y worker. Reglas evaluadas cubren disponibilidad, líder, jobs estancados, error ratio y p95 HTTP/DB; production acceptance verifica targets y rules. |
| 35 | Grafana | Implementado en main | Provisioning automático de datasource y dashboards `DeviceMesh / Overview` y `DeviceMesh / Workers & Synthetics`; production acceptance exige al menos dos dashboards provisionados. |
| 36 | Logging estructurado | Implementado en main | JSON común para API y scheduler-worker, `service/component/process_id`, propagación segura de `X-Request-ID`, contexto allow-listed de dominio/jobs, acceso Uvicorn crudo desactivado, tests y guía operativa. |
| 37 | OpenTelemetry | Diferido según propuesta | Traces OTel posteriores a métricas y logging, tal como indica la propuesta. |
| 38 | Base de datos y escalabilidad | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 39 | Retention policy completa | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 40 | Production Docker deployment | Implementado en main | Caddy HTTPS, roles separados app/migración, secrets files, non-root app/web, readonly/cap_drop, límites, healthchecks, volúmenes y rotación de logs. Production acceptance levanta API/worker/web/Prometheus/Grafana/Caddy, importa la CA interna y valida HTTPS, HSTS/frame/content-type, bloqueo de `/metrics`, restore, restart y persistencia. |
| 41 | Kubernetes: no todavía | Diferido según propuesta | Kubernetes/Helm posteriores a demostrar necesidad de HA; no requisito actual. |
| 42 | Seguridad adicional | Implementado en main | Lecturas privadas en producción, RBAC, throttling persistente, refresh/WS revocables, protección timestamp/replay, dependency locks y auditorías. PR #55 fija todas las GitHub Actions por SHA y añade SBOM/attestations; PR #60 añade fuzzing determinista Hypothesis sobre contratos, JSON arbitrario, IDs, request IDs y compatibilidad. |
| 43 | Synthetic secrets | Pendiente | Implementar referencias secretas para credenciales/headers de checks sintéticos sin persistir secretos en claro, con resolución segura en backend/probes, redacción API/logs y pruebas de no filtración. |
| 44 | Testing: backend bien, sistema completo todavía no | Implementado en main | Harness enrollment→heartbeat→Redis/WS→inventory, telemetry→threshold alert→recovery, producción/restore/reinicio, integración y contratos. PR #52 añade Playwright sobre la aplicación Vite real para login, navegación Services, filtro, Ctrl/Cmd+K, incidents/detail y sign-out; PR #61 extiende el browser flow a las rutas operativas dedicadas. |
| 45 | Chaos/failure testing | Implementado en main | Revocación, refresh usado, readiness DB caída, replay de cola y failover de scheduler, más Failure acceptance productivo: caída/recuperación PostgreSQL, caída/recuperación Redis con WS, restart API con estado persistente y restart worker con recuperación del liderazgo. |
| 46 | Performance/soak tests | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 47 | Testing móvil | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 48 | Testing ESP32 | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 49 | Releases y distribución | Implementado en main | Release Validation construye y prueba MSI, DEB/RPM y archivo macOS, valida imágenes API/web/probe y publica artefactos productivos con checksums. Los tags publican imágenes GHCR y GitHub Release sólo después de los jobs requeridos; móvil/firmware se excluyen hasta que sus puntos propios sean productivos. |
| 50 | Supply-chain | Implementado en main | Locks Python con hashes y `npm ci`, SHA256SUMS, CycloneDX SBOM y attestations/provenance para paquetes e imágenes. Todas las acciones remotas están fijadas a SHA inmutable y Security CI impide reintroducir referencias mutables. |
| 51 | Versionado y compatibilidad | Implementado en main | `GET /api/v1/system/version` publica versión/API/protocolo/esquema y matriz de componentes. `GET /api/v1/system/compatibility/{component}` aplica mínimos explícitos y protocolos soportados para Windows/Linux/macOS/probe, con razones estables; integración cubre clientes válidos, antiguos, protocolo incorrecto y versiones inválidas. |
| 52 | Auto-update de agentes | Diferido según propuesta | Actualización automática posterior a firma y canales de release. |
| 53 | Documentación | Implementado en main | README y guías de despliegue, recuperación, seguridad, HA, logging, probes y releases, junto con vistas C4 de contexto, contenedores, componentes y deployment que documentan trust boundaries, persistencia y failover. |
| 54 | API documentation | Implementado en main | Guía de autenticación/convenciones y catálogo exhaustivo generado desde OpenAPI, incluyendo endpoints fuera de schema (`/metrics`, `/ws/events`). Documentation CI regenera el catálogo y falla si el Markdown comprometido deriva del contrato real. |
| 55 | Documentation for hardware | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 56 | GitHub hygiene | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 57 | Inteligencia/anomaly detection | Diferido según propuesta | Baselines/anomalías posteriores a benchmark, retención y fiabilidad. |
| 58 | Correlación / Root Cause Analysis | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 59 | Cómo debería quedar el ecosistema completo | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |

## Orden de continuación

1. Synthetic secrets y assertions avanzadas (#43/#11), y después red/NMS (#13–#16).
2. Base de datos/retención/performance (#38, #39, #46), cerrando benchmarks y soak prolongado antes de anomaly detection.
3. Auditar y cerrar el estado real de Windows/Linux (#29–#32) y después Android/iOS (#19–#24), incluyendo seguridad, pruebas y distribución propias.
4. ESP32/hardware (#25–#28, #48, #55) con identidad, provisioning, sensores y pruebas físicas antes de OTA.
5. GitHub hygiene (#56), RCA (#58) y el cierre del ecosistema completo (#59) una vez sus dependencias estén implementadas.

## Límites verificables

- HA acceptance certifica dos réplicas API compartiendo PostgreSQL/Redis, balanceo Caddy, realtime cross-instance y recuperación de una partición de réplica; no equivale a certificar HA multi-host de PostgreSQL/Redis o del proveedor de infraestructura.
- Production acceptance valida el proxy Caddy con TLS confiable mediante CA interna en runner limpio; la emisión ACME con DNS público/certificado externo pertenece al entorno de despliegue, no al contrato de CI.
- Releases cubren los componentes actualmente productivos (API/web/probe y paquetes Windows/Linux/macOS). Android, iOS y firmware ESP32 no se publican mientras sus puntos propios sigan pendientes.
- La autenticación V1 local ya incluye MFA; OIDC/LDAP permanecen como adaptadores de federación opcionales futuros y no se presentan como implementados.
- No se han ejecutado soak de 24/48 h, validación de hardware real ni publicación móvil/firmware en tiendas/canales finales.
