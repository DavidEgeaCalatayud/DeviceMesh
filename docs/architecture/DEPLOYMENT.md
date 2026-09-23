# Deployment

The default deployment target is a local machine, NAS or home server using Docker Compose. PostgreSQL and Redis are private services; only the web/API edge is exposed.

Production deployments should terminate TLS at a reverse proxy, rotate secrets, restrict discovery scopes and persist database volumes with tested backups.
