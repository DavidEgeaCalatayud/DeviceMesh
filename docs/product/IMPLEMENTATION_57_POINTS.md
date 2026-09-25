# Seguimiento de los 57 puntos de DeviceMesh

Primera entrega: `feat/production-platform-foundations`. Base revisada: `6990542` (V1.3).

Este documento conserva el alcance completo. **Parcial** significa que hay código ejecutable y faltan subpuntos o validación; no equivale a production-ready. **Pendiente** significa que no se ha implementado en esta entrega. Los scaffolds móviles y ESP32 siguen siendo scaffolds.

| Nº | Área | Estado | Evidencia / siguiente criterio |
|---|---|---|---|
| 1 | Lo primero: terminar de verdad la V1 como producto instalable | Parcial | Compose productivo, validación, install, backup/restore, timer, retención, ensayo de producción, restore/restart y upgrade/smoke automatizados. Production acceptance ya arranca el stack real en runner limpio. Faltan completar instaladores/distribución y validar HTTPS en host limpio. |
| 2 | Backend: evolucionarlo de backend funcional a plataforma | Implementado en main | Catálogo persistente con propietario, entorno, criticidad, tags y dispositivo; relación muchos-a-muchos con monitores; grupos de servicios; dependencias hard/soft con detección de ciclos y exposición de dependents/dependencies. |
| 3 | Service Incidents tiene que convertirse en Incident Management | Implementado en main | ACK, asignación, severidad, notas, causa, resolución, reapertura y timeline automática/manual; correlación temporal multimonitor a través de servicios/dependencias relacionados; impacto y postmortem editables. |
| 4 | SLO, SLI y Error Budgets | Implementado en main | SLI por éxito de checks y por disponibilidad temporal, ventanas 7/30/90, error budget en checks o segundos, estado unknown/stale, burn-rates 1h/6h/24h y política critical/warning. |
| 5 | Notificaciones y routing de alertas | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 6 | Autenticación humana y RBAC | Parcial | Argon2id, roles, sesiones/refresh rotatorios, revocación, usuarios, desactivación y login web. MFA/OIDC/LDAP pendientes. |
| 7 | Audit Log global | Implementado en main | Auditoría transaccional de operaciones de dominio y UI admin, más middleware transversal para toda mutación humana autenticada heredada/actual que aún no tenga evento semántico propio; captura actor, ruta, método, estado, IP y request ID. |
| 8 | Alta disponibilidad y escalado horizontal del backend | Parcial | Pub/Sub Redis para fan-out y reconexión; APIs stateless sobre PostgreSQL; workers con advisory lock y failover probado. Falta aceptación con dos APIs detrás de balanceador y recuperación de particiones/fallos de red. |
| 9 | Separar workers del proceso API | Implementado en main | Worker independiente con elección mediante advisory lock; API productiva desactiva jobs embebidos; offline sweep, synthetics y retention se ejecutan en el scheduler; integración PostgreSQL prueba líder único y failover al perder la sesión. |
| 10 | Distributed Probes: V1.3 está hecha, pero todavía falta bastante | Parcial | Dockerfile, systemd, cola SQLite acotada, concurrencia limitada, backpressure, backoff/jitter y rotación transaccional de bearer token con almacenamiento sólo del hash. Expiración y telemetría propia del probe pendientes. |
| 11 | Synthetic monitoring mucho más profundo | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 12 | Consenso distribuido V2: rondas/quorum | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 13 | Network Monitoring / NMS: aquí hay un campo enorme todavía | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 14 | LLDP/CDP y topología automática | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 15 | Más información de red | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 16 | Syslog | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 17 | Web: aún le falta convertirse en una aplicación completa de operaciones | Parcial | Navegación, Services, Incidents, detalle, Administration con login y búsqueda global por dispositivos/servicios/incidentes con Ctrl/Cmd+K. Probes/maintenance/operations conservan consola actual. |
| 18 | UX web | Parcial | Estados de carga/error/vacío, búsqueda de servicios y búsqueda global, páginas de incidentes, URLs de detalle, formularios etiquetados, diseño adaptable. ES/EN, vistas guardadas y resto pendiente. |
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
| 40 | Production Docker deployment | Parcial | Caddy HTTPS, roles separados app/migración, secrets files, non-root app/web, readonly/cap_drop, límites, healthchecks, volúmenes y rotación logs. Production acceptance ya levanta API/worker/web/Prometheus/Grafana, migra, restaura backup y prueba restart; falta validar el proxy HTTPS completo en host limpio. |
| 41 | Kubernetes: no todavía | Diferido según propuesta | Kubernetes/Helm posteriores a demostrar necesidad de HA; no requisito actual. |
| 42 | Seguridad adicional | Parcial | Lecturas privadas en producción, RBAC, throttling persistente, refresh/WS revocables y protección de timestamps/replay de resultados. Fuzzing y supply-chain completa pendientes. |
| 43 | Synthetic secrets | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 44 | Testing: backend bien, sistema completo todavía no | Parcial | Harness enrollment→heartbeat→Redis/WS→inventory, integración telemetry→threshold alert→recovery y CI de producción/restore/reinicio. Playwright de operador pendiente. |
| 45 | Chaos/failure testing | Parcial | Tests de revocación, refresh usado, readiness DB caída, replay de cola y failover del scheduler por pérdida de sesión. Matriz completa de fallos no ejecutada. |
| 46 | Performance/soak tests | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 47 | Testing móvil | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 48 | Testing ESP32 | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 49 | Releases y distribución | Parcial | Empaquetador desde commit con manifiesto y checksums. MSI/deb/rpm, publicación de imágenes y releases móviles/firmware pendientes. |
| 50 | Supply-chain | Parcial | Locks Python con hashes y npm ci; bundle SHA256SUMS. SBOM existente, attestations, firmas y pin de todas las acciones pendientes. |
| 51 | Versionado y compatibilidad | Parcial | `GET /api/v1/system/version` publica versión de paquete, API/protocolo, revisión de esquema y matriz de protocolos para Windows/Linux/macOS/probe. Faltan mínimos explícitos de versión de paquete y validación multicliente contra esa política. |
| 52 | Auto-update de agentes | Diferido según propuesta | Actualización automática posterior a firma y canales de release. |
| 53 | Documentación | Parcial | README actualizado, seguimiento de los 57 puntos y guías de despliegue, recuperación, seguridad/API, HA, logging y probes. Diagramas C4 completos pendientes. |
| 54 | API documentation | Parcial | Guía de auth, contratos nuevos, unidades SLO y códigos de error junto a OpenAPI. Guía exhaustiva de endpoints heredados pendiente. |
| 55 | Documentation for hardware | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 56 | GitHub hygiene | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 57 | Inteligencia/anomaly detection | Diferido según propuesta | Baselines/anomalías posteriores a benchmark, retención y fiabilidad. |
| 58 | Correlación / Root Cause Analysis | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 59 | Cómo debería quedar el ecosistema completo | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |

## Orden de continuación

1. Completar instaladores/distribución y validar HTTPS en host limpio; después cerrar HA con dos APIs detrás de balanceador y escenarios de partición.
2. Completar notificaciones/routing, lifecycle de credenciales de probes, auth avanzada y los huecos reales de web/UX.
3. Cerrar testing de operador con Playwright, compatibilidad multicliente, supply-chain/release y documentación C4/API exhaustiva.
4. Android/iOS: sesiones seguras, caché offline, pantallas reales y pruebas; después push y distribución firmada.
5. Agentes/NMS/ESP32: paquetes y operaciones declarativas, SNMPv3/LLDP/syslog y, para hardware, identidad/provisioning/pruebas reales antes de OTA firmada.

## Límites verificables

- La integración PostgreSQL prueba locking/failover del scheduler; no certifica todavía particiones de red del despliegue HA completo.
- `production-acceptance.yml` ejecuta el stack de producción en un runner limpio y valida migración, realtime, observabilidad, restore y restart; no valida todavía el proxy HTTPS/Caddy en un host externo limpio.
- No se han ejecutado soak 24/48 h, hardware real, firma de releases ni distribución a tiendas.
- La publicación y el merge han sido autorizados expresamente. La validación de CI y el commit integrado se comunicarán con la entrega; no se despliegan servicios de producción.
