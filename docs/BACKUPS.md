# Friss backup and recovery

Available from v1.32.0 under **Settings → Backup and restore** (Deutsch: **Einstellungen → Datensicherung und Wiederherstellung**).

## Download

Choose **Download backup** and save the ZIP in Files on your iPhone or another device. It contains:

- `backup.json`: versioned `friss-backup-v1` JSON with the effective BLS/food database, diary entries and nutrient snapshots, food/drink recipes, own foods, favorites, settings/goals/BAC profile, quick-add definitions and base64-encoded images, learned searches, JSON-import batches and Apple Health export records/status.
- `files/originals/`: original input JSON/text/photos and preserved AI requests.
- `files/bls/`: source BLS JSON files, if present.
- An attachment manifest in the JSON with byte lengths and SHA-256 checksums.

Login sessions, login-attempt records, passwords, API keys/environment configuration, application code and previous recovery ZIPs are excluded. The backup is not encrypted and contains personal nutrition data and photographs; store it accordingly. Effective defaults are still defaults if you never saved settings.

## Restore

1. Select a Friss ZIP in the same Settings section.
2. Choose **Check backup**. Friss validates format, table columns, ZIP paths and attachment checksums. The preview shows creation date, app version, record and file counts; nothing is changed.
3. Choose **Restore data**, then confirm replacement. This replaces the current Friss datasets and original/BLS files; it does not merge them.
4. Friss first saves the current state under `data/recovery/before-restore-<time>-<id>.zip`. On success the app reloads. Current server credentials and sessions remain unchanged.

Restore on another server: install Friss v1.32.0 or a compatible newer version, configure its password/API key as usual, sign in and restore the ZIP. No separate BLS upload is needed because the backup includes the effective food table. Matching v1 backup schema and database columns are required; unknown/incompatible formats are rejected rather than partially imported.

**Apple Health is not restored or modified.** Export status is restored to the state at backup time. If you exported meals after creating that backup, those samples may still exist on the iPhone despite their older status in Friss. Check Health before exporting those days again. Restored prepared/uncertain exports require the same manual review as before; Friss never assumes Health was written successfully.

## Safety and limits

- Use the standard single API worker supplied by the Docker setup. For a custom multi-worker deployment, stop the other workers before an in-app backup/restore; the maintenance gate is per process.
- Export/restore temporarily put the API in maintenance mode and wait for existing requests to finish. Other requests receive HTTP 503 with Retry-After; retry after the operation. Do not run separate database/file import scripts at the same time.
- ZIP uploads are limited to 128 MiB, expanded contents to 512 MiB and attachments to 30,000. Unknown files, unsafe ZIP paths, duplicate names, symlinks, missing manifest entries and checksum errors are rejected. Server data containing symlinks cannot be exported.
- Database changes use a transaction. If inserts or filesystem replacement fail, the existing database and original folders are rolled back. The pre-restore ZIP is kept independently in `data/recovery` and excluded from later backups to avoid recursive growth. These recovery files are not automatically deleted.
- Keep the downloaded ZIP until you have checked the restored diary, recipes and settings. For abrupt process/power failure or filesystem damage during replacement, the pre-restore ZIP is the recovery source; normal exception rollback does not guarantee power-loss atomicity across SQLite and files.
- The ZIP must come from a trusted Friss instance. Checksums detect damage, not who created the archive. Configuration (`.env`, compose setup), source code and any independently stored server data need their own server backup.

## API

All endpoints require the existing Friss authentication (Bearer API key or same-origin authenticated browser session).

- `GET /backups/export`: ZIP attachment; `Cache-Control: no-store`.
- `POST /backups/inspect`: raw ZIP body, `Content-Type: application/zip`; returns metadata/counts, no mutation.
- `POST /backups/restore`: same raw ZIP, plus `X-Friss-Restore: replace`. Returns `restored: true`, counts and relative `recovery_backup` path. This header is explicit replacement intent, not a second authentication factor.

These ZIP backups are separate from nutrition JSON imports and Apple Health day exports. A `friss-meal-v1` or AI-meal JSON cannot be used as a full backup.
