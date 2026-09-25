# Backup and Restore

Backups cover PostgreSQL and non-secret deployment settings. Runtime secrets and Caddy certificate state are not included: store the secret directory separately in your protected recovery storage. Backups include credential hashes and operational data; the bundle is not encrypted by this script. The deployment operator controls off-host storage and encryption.

```bash
tools/deployment/backup.sh
tools/deployment/verify-backup.sh
```

`backup.sh` uses a PostgreSQL custom-format dump, verifies its table of contents, records a SHA-256 digest and commits the tarball through an atomic rename. It uses a private directory/umask and applies retention only after the new dump succeeds. `BACKUP_RETENTION_DAYS` defaults to 30; only complete `devicemesh-*.tar.gz` bundles are eligible. Checksums detect corruption, not a malicious replacement of both dump and manifest.

`verify-backup.sh` restores a fresh backup into a separate temporary database and checks the Alembic revision. It never replaces the live database and drops only its temporary database on exit. Successful restore execution is a rehearsal, not proof of every application invariant or your recovery time objective.

For daily backups, install the service/timer in `infra/systemd/` after reviewing its `/opt/devicemesh` path:

```bash
sudo cp infra/systemd/devicemesh-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now devicemesh-backup.timer
```

## Restore / rollback

Use a trusted backup, restore the matching secret files, and select the intended application release before running:

```bash
tools/deployment/restore.sh /path/to/devicemesh-backup.tar.gz --replace-database
```

The explicit flag acknowledges replacement of the active dataset. The script validates members and the checksum without extracting arbitrary paths, takes a fresh recovery backup, restores into a new database, stops API/worker, renames the original database, switches the restored database to the live name, migrates to the checked-out release and runs API/HTTPS smoke checks. The original database is retained as `devicemesh_before_restore_*` until the operator verifies recovery and removes it deliberately. A failed dump restore leaves the live name unchanged; failures during the rename/migration/start phase leave writers stopped for inspection. Check `pg_database` and the command output before resuming.

For schema rollback, run this from the matching earlier release. Restoring an old dump under a newer release intentionally reapplies the newer migrations. Never use `docker compose down -v` on a live deployment for an upgrade or restore.
