#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
exec 9>.git/friss-update.lock
flock -n 9 || { echo 'Another update is running.'; exit 1; }
[[ $(git branch --show-current) == server ]] || { echo 'Switch to branch server first.'; exit 1; }
[[ -z $(git status --porcelain) ]] || { echo 'Local code changes found. Commit or back them up before updating.'; exit 1; }
[[ -f .env ]] || { echo 'Create .env first.'; exit 1; }
backup_dir="${XDG_DATA_HOME:-$HOME/.local/share}/friss-backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
cp .env "$backup_dir/env"
git rev-parse HEAD > "$backup_dir/commit"
# Consistent SQLite snapshot. Original files remain in the persistent data mount.
if docker compose ps --status running --services | grep -q '^api$'; then
  docker compose exec -T api python -c 'import sqlite3; from pathlib import Path; from datetime import datetime, timezone; p=Path("/data/backups"); p.mkdir(exist_ok=True); source=sqlite3.connect("/data/friss.sqlite3"); target=sqlite3.connect(p / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".sqlite3")); source.backup(target); target.close(); source.close()'
fi
git fetch origin server
git merge --ff-only origin/server
docker compose build api
docker compose up -d --no-build api
for attempt in {1..30}; do
  if docker compose exec -T api python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/", timeout=3)' >/dev/null 2>&1; then
    echo "Friss $(cat VERSION) is running. Refresh the app on your phone."
    echo "Previous commit and environment saved in $backup_dir"
    exit 0
  fi
  sleep 2
done
echo 'Startup check failed. Inspect docker compose logs --tail=100.'
echo "Previous commit: $(cat "$backup_dir/commit"). Environment backup: $backup_dir/env"
exit 1
