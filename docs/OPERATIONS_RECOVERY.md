# PrediBeacon Operations and Recovery Runbook

## Safe operating state

PrediBeacon is informational and outbound-only. Keep social distribution, paid partner routing, automated editorial publication and billing disabled until their corresponding credentials, contracts and production verification exist.

## Health and diagnosis

1. Check `/health` for HTTP 200 and the expected release version.
2. Check `/api/v1/status` for freshness, venue counts and storage state.
3. Use the authenticated `/api/v1/admin/operations` endpoint for critical and warning checks.
4. Treat unavailable/future-dated freshness, missing persistent storage or both venues at zero as release blockers.

## Database backup

The production SQLite database must live on the mounted `/data` volume. The application performs an online backup at worker startup and every 24 hours when the database is on `/data` and `MP_DATABASE_BACKUPS=true`. Copies are integrity-checked before they count as successful and retention defaults to seven. Operators can trigger a verified copy through the protected `POST /api/v1/admin/database/backups` endpoint and check the active database with `GET /api/v1/admin/database/integrity`. Never copy only the WAL file. Retain the database, WAL and SHM together when performing a cold filesystem copy.

Verify every backup by opening it read-only, running `PRAGMA integrity_check`, and confirming expected tables and row counts. Keep at least one recovery copy outside the active Railway volume.

## Recovery

1. Disable automated publishing and external distribution flags.
2. Stop application writes.
3. Preserve the damaged database and its WAL/SHM files for investigation.
4. Restore the most recent integrity-checked backup to a new path.
5. Run `PRAGMA integrity_check`.
6. Start one instance against the restored database.
7. Verify health, storage identity, startup count, market snapshots, draft states, schedules and revenue audit records.
8. Re-enable workers individually only after their checks pass.

## Rollback

Revert to the last known-good GitHub release through a new PR or Railway deployment rollback. Do not delete database migrations or audit history. Confirm the application version at `/health` and execute smoke checks for home, market detail, outbound eligibility, editorial admin and the protected operations endpoint.

## Incident priorities

- Critical: database integrity failure, secret exposure, incorrect external redirect, duplicated/replayed partner revenue, public internal-brand leakage.
- High: both venue feeds unavailable, stale data without warning, publication bypassing approval.
- Medium: one source unavailable, incomplete related-market results, local notification failure.

Record incident time, affected release, detection, containment, data impact, recovery evidence and follow-up test.
