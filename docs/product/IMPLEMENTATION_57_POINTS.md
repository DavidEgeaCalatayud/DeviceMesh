# Seguimiento de los 57 puntos de DeviceMesh

Primera entrega: `feat/production-platform-foundations`. Base revisada: `6990542` (V1.3).

Este documento conserva el alcance completo. **Parcial** significa que hay código ejecutable y faltan subpuntos o validación; no equivale a production-ready. **Pendiente** significa que no se ha implementado en esta entrega. Los scaffolds móviles y ESP32 siguen siendo scaffolds.

| Nº | Área | Estado | Evidencia / siguiente criterio |
|---|---|---|---|
| 1 | Lo primero: terminar de verdad la V1 como producto instalable | Parcial | Compose, validación, install, backup/restore, timer, retención, ensayo y upgrade/smoke. Falta ejecutar aceptación Docker/host limpio y completar instaladores. |
| 2 | Backend: evolucionarlo de backend funcional a plataforma | Parcial | Catálogo persistente con propietario, entorno, criticidad, tags, dispositivo y relación muchos-a-muchos con monitores. Dependencias de servicios y grupos pendientes. |
| 3 | Service Incidents tiene que convertirse en Incident Management | Parcial | ACK, asignación, severidad, notas, causa, resolución, reapertura y timeline automática/manual. Correlación multimonitor y postmortem pendiente. |
| 4 | SLO, SLI y Error Budgets | Parcial | SLI por éxito de checks, SLO 7/30/90, presupuesto en checks, burn 1h/6h, datos desconocidos/stale. SLI por tiempo y avisos de burn pendientes. |
| 5 | Notificaciones y routing de alertas | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 6 | Autenticación humana y RBAC | Parcial | Argon2id, roles, sesiones/refresh rotatorios, revocación, usuarios, desactivación y login web. MFA/OIDC/LDAP pendientes. |
| 7 | Audit Log global | Parcial | Auditoría transaccional de usuarios, servicios, SLO y cambios manuales de incidente; UI admin. Falta integrar todas las operaciones heredadas. |
| 8 | Alta disponibilidad y escalado horizontal del backend | Parcial | Pub/Sub Redis para fan-out y reconexión; PostgreSQL conserva timeline. Falta demostrar dos APIs, balanceador y recuperación ante particiones. |
| 9 | Separar workers del proceso API | Parcial | Worker independiente con elección mediante advisory lock. Proceso API puede desactivar jobs. Distribución de todos los jobs y pruebas de failover pendientes. |
| 10 | Distributed Probes: V1.3 está hecha, pero todavía falta bastante | Parcial | Dockerfile, systemd, cola SQLite acotada, concurrencia limitada, backpressure y backoff/jitter. Expiración/rotación y telemetría del probe pendientes. |
| 11 | Synthetic monitoring mucho más profundo | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 12 | Consenso distribuido V2: rondas/quorum | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 13 | Network Monitoring / NMS: aquí hay un campo enorme todavía | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 14 | LLDP/CDP y topología automática | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 15 | Más información de red | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 16 | Syslog | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 17 | Web: aún le falta convertirse en una aplicación completa de operaciones | Parcial | Navegación, Services, Incidents, detalle y Administration con login. Probes/maintenance/operations conservan consola actual. |
| 18 | UX web | Parcial | Estados de carga/error/vacío, búsqueda de servicios, páginas de incidentes, URLs de detalle, formularios etiquetados, diseño adaptable. ES/EN, vistas guardadas y resto pendiente. |
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
| 34 | Observabilidad del propio DeviceMesh | Parcial | /metrics protegido: HTTP, ingesta, WS, online devices/probes, incidentes, latencia DB y contadores internos de jobs. Falta scrape de worker y evaluaciones de alertas/checks. |
| 35 | Grafana | Parcial | Dashboard importable DeviceMesh / Overview. Dashboards específicos y provisioning automático pendientes. |
| 36 | Logging estructurado | Parcial | Logs JSON y request ID; no cuerpos, headers, query strings ni mensajes de excepción en formatter. Extender contexto de dominio y todos los procesos pendiente. |
| 37 | OpenTelemetry | Diferido según propuesta | Traces OTel posteriores a métricas y logging, tal como indica la propuesta. |
| 38 | Base de datos y escalabilidad | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 39 | Retention policy completa | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 40 | Production Docker deployment | Parcial | Caddy HTTPS, roles separados app/migración, secrets files, non-root app/web, readonly/cap_drop, límites, healthchecks, volúmenes y rotación logs. Ensayo de despliegue pendiente. |
| 41 | Kubernetes: no todavía | Diferido según propuesta | Kubernetes/Helm posteriores a demostrar necesidad de HA; no requisito actual. |
| 42 | Seguridad adicional | Parcial | Lecturas privadas en producción, RBAC, throttling persistente, refresh/WS revocables y protección de timestamps/replay de resultados. Fuzzing y supply-chain completa pendientes. |
| 43 | Synthetic secrets | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 44 | Testing: backend bien, sistema completo todavía no | Parcial | Harness de enrollment→heartbeat→Redis/WS→inventory y CI de producción/restore/reinicio. Telemetría→alerta y Playwright de operador pendientes. |
| 45 | Chaos/failure testing | Parcial | Tests de revocación, refresh usado, readiness DB caída y replay de cola. Matriz completa de fallos no ejecutada. |
| 46 | Performance/soak tests | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 47 | Testing móvil | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 48 | Testing ESP32 | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 49 | Releases y distribución | Parcial | Empaquetador desde commit con manifiesto y checksums. MSI/deb/rpm, publicación de imágenes y releases móviles/firmware pendientes. |
| 50 | Supply-chain | Parcial | Locks Python con hashes y npm ci; bundle SHA256SUMS. SBOM existente, attestations, firmas y pin de todas las acciones pendientes. |
| 51 | Versionado y compatibilidad | Parcial | GET /api/v1/system/version con versión de paquete, protocolo soportado y revisión de esquema. Matriz multicliente y mínimos por componente pendientes. |
| 52 | Auto-update de agentes | Diferido según propuesta | Actualización automática posterior a firma y canales de release. |
| 53 | Documentación | Parcial | README actualizado, seguimiento de los 57 puntos y guías de despliegue, recuperación, seguridad/API y probes. Diagramas C4 completos pendientes. |
| 54 | API documentation | Parcial | Guía de auth, contratos nuevos, unidades SLO y códigos de error junto a OpenAPI. Guía exhaustiva de endpoints heredados pendiente. |
| 55 | Documentation for hardware | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 56 | GitHub hygiene | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 57 | Inteligencia/anomaly detection | Diferido según propuesta | Baselines/anomalías posteriores a benchmark, retención y fiabilidad. |
| 58 | Correlación / Root Cause Analysis | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |
| 59 | Cómo debería quedar el ecosistema completo | Pendiente | Implementar y validar después de sus dependencias; sin dar por completo el scaffold existente. |

## Orden de continuación

1. Ejecutar y corregir CI de PostgreSQL/Docker, probar HTTPS en host limpio y restauración real. Medir 10/100/1.000 dispositivos antes de optimizar.
2. Completar incidentes de servicio, notificaciones/routing, SLO por tiempo, auditoría heredada, lifecycle de credenciales y diagnóstico DNS/TLS/HTTP.
3. Android/iOS: sesiones seguras, caché offline, pantallas reales y pruebas; después push y distribución firmada.
4. Agentes: MSI/deb/rpm, inventario ampliado y operaciones declarativas; NMS: SNMPv3, interfaces, LLDP y syslog.
5. ESP32: definir placa/sensor soportados, identidad, Wi-Fi/NVS/HTTPS, provisioning BLE y pruebas de hardware antes de OTA firmada.

## Límites verificables

- Las pruebas unitarias/API nuevas usan SQLite para aislar la lógica de auth y workflow. No certifican locking, permisos ni recuperación de PostgreSQL.
- El workflow `production-acceptance.yml` está preparado; su resultado remoto depende de poder publicar la rama.
- No se han ejecutado soak 24/48 h, host limpio, hardware real, firma de releases ni distribución a tiendas.
- La publicación y el merge han sido autorizados expresamente. La validación de CI y el commit integrado se comunicarán con la entrega; no se despliegan servicios de producción.
