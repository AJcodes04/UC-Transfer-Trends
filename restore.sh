#!/bin/bash
# Replace the Render production database with ~/Desktop/uc_transfer.dump (made by ./dump.sh).
set -o errexit

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/.render.env"
DB_URL="$RENDER_DB_URL"
PGBIN=/opt/homebrew/opt/postgresql@17/bin
DUMP_FILE="$HOME/Desktop/uc_transfer.dump"
BACKUP_FILE="$HOME/Desktop/uc_transfer-render-backup-$(date +%Y%m%d-%H%M%S).dump"

if [ ! -f "$DUMP_FILE" ]; then
  echo "No dump at $DUMP_FILE. Run ./dump.sh first."
  exit 1
fi

echo "This DROPS every table in the Render production database and reloads it from:"
echo "  $DUMP_FILE  (written $(date -r "$DUMP_FILE" '+%Y-%m-%d %H:%M'))"
echo "Deploy the matching code first: old code running against the new schema returns 500s."
read -r -p "Type 'restore' to continue: " answer
if [ "$answer" != "restore" ]; then
  echo "Aborted. Nothing was changed."
  exit 1
fi

echo "Step 0: Backing up current production to $BACKUP_FILE ..."
"$PGBIN/pg_dump" -Fc "$DB_URL" -f "$BACKUP_FILE"

echo "Step 1: Dropping all tables..."
"$PGBIN/psql" "$DB_URL" -c "
DO \$\$ DECLARE r RECORD;
BEGIN
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
  END LOOP;
END \$\$;
"

echo "Step 2: Restoring dump..."
# pg_dump 17 emits SET transaction_timeout, which Render's older Postgres rejects.
"$PGBIN/pg_restore" -f - "$DUMP_FILE" | grep -v transaction_timeout | "$PGBIN/psql" "$DB_URL"

echo "Done! Previous production data is saved at $BACKUP_FILE"
