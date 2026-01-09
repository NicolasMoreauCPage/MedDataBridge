#!/usr/bin/env bash
# Remote helper script to be run on the server.
# Usage: remote_deploy.sh meddatabridge-deployment-YYYYMMDD-HHMMSS.zip


set -euo pipefail

usage() {
  echo "Usage: $0 <zip-file-in-/tmp> [--rollback]" >&2
  echo "  --rollback    : restore last backup instead of deploying" >&2
  exit 2
}

if [ "${1-}" = "--rollback" ]; then
  # If first arg is --rollback, we expect to restore latest backup
  ROLLBACK=true
  ZIPNAME=""
else
  ROLLBACK=false
  ZIPNAME="$1"
fi

DESTDIR="/opt/meddata-bridge"
BACKUPDIR="/opt/meddata-bridge-backups"

if [ "$ROLLBACK" = true ]; then
  echo "Rollback requested — restoring latest backup from $BACKUPDIR"
  LATEST=$(ls -1t "$BACKUPDIR" 2>/dev/null | head -n1 || true)
  if [ -z "$LATEST" ]; then
    echo "No backup found in $BACKUPDIR" >&2
    exit 3
  fi
  echo "Restoring backup: $LATEST"
  sudo rm -rf "$DESTDIR"
  sudo cp -a "$BACKUPDIR/$LATEST" "$DESTDIR"
  sudo chown -R root:root "$DESTDIR"
  sudo systemctl restart meddata-bridge
  echo "Rollback complete." && exit 0
fi

if [ -z "$ZIPNAME" ]; then
  usage
fi

TMPFILE="/tmp/$ZIPNAME"

echo "Creating backup of current deployment (if present)"
sudo mkdir -p "$BACKUPDIR"
# ensure backup dir is writable by root but intended owner for DB files is 'meddata'
sudo chown root:root "$BACKUPDIR" || true
sudo chmod 0755 "$BACKUPDIR" || true
if [ -d "$DESTDIR" ]; then
  TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
  BACKUPNAME="meddata-bridge-backup-$TIMESTAMP"
  echo "Backing up $DESTDIR -> $BACKUPDIR/$BACKUPNAME"
  sudo cp -a "$DESTDIR" "$BACKUPDIR/$BACKUPNAME"
  # keep backup readable by root, and make DB files owned by meddata inside the backup
  if id meddata >/dev/null 2>&1; then
    sudo find "$BACKUPDIR/$BACKUPNAME" -type f \( -name "medbridge.db" -o -name "medbridge.db-wal" -o -name "medbridge.db-shm" \) -exec chown meddata:meddata {} + || true
    sudo find "$BACKUPDIR/$BACKUPNAME" -type f -name "medbridge.db" -exec chmod 0640 {} + || true
    sudo find "$BACKUPDIR/$BACKUPNAME" -type f \( -name "medbridge.db-wal" -o -name "medbridge.db-shm" \) -exec chmod 0660 {} + || true
  fi
fi

# Rotate backups: keep only the N most recent backups
KEEP_BACKUPS=7
echo "Pruning backups to keep last $KEEP_BACKUPS entries"
if [ -d "$BACKUPDIR" ]; then
  # list backups sorted by time, skip the most recent $KEEP_BACKUPS and remove the rest
  cd "$BACKUPDIR" || true
  ls -1t | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r sudo rm -rf -- || true
fi

echo "Unzipping $TMPFILE to $DESTDIR"
sudo mkdir -p "$DESTDIR"
sudo unzip -o "$TMPFILE" -d "$DESTDIR"

echo "Applying ownership and permissions"
sudo chown -R root:root "$DESTDIR"
sudo chmod -R g-w "$DESTDIR"

# Ensure the backups directory exists and has expected ownership for later operations
sudo mkdir -p "$BACKUPDIR"
sudo chown root:root "$BACKUPDIR" || true
sudo chmod 0755 "$BACKUPDIR" || true

echo "Restoring SQLite database files from latest backup if present"
# Look for the latest backup directory name
LATEST_BACKUP_DIR=$(ls -1t "$BACKUPDIR" 2>/dev/null | head -n1 || true)
if [ -n "$LATEST_BACKUP_DIR" ]; then
  SQLITE_FILES=(medbridge.db medbridge.db-wal medbridge.db-shm)
  for f in "${SQLITE_FILES[@]}"; do
    SRC="$BACKUPDIR/$LATEST_BACKUP_DIR/$f"
    DST="$DESTDIR/$f"
    if [ -f "$SRC" ]; then
      echo "Restoring $f from backup ($LATEST_BACKUP_DIR)"
      sudo cp -a "$SRC" "$DST"
      # set the DB files to the application user if it exists
      if id meddata >/dev/null 2>&1; then
        sudo chown meddata:meddata "$DST" || true
        if [ "$f" = "medbridge.db" ]; then
          sudo chmod 0640 "$DST" || true
        else
          sudo chmod 0660 "$DST" || true
        fi
      else
        sudo chown root:root "$DST" || true
        sudo chmod 0640 "$DST" || true
      fi
    fi
  done
else
  echo "No backups found in $BACKUPDIR — skipping DB restore"
fi

echo "Restarting service meddata-bridge"
sudo systemctl restart meddata-bridge

echo "Cleaning up"
rm -f "$TMPFILE"

echo "Remote deployment finished successfully."
