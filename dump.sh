#!/bin/bash
# Dump the local Postgres database to a custom-format file that restore.sh can load.
set -o errexit

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/.render.env"

PG_DUMP=/opt/homebrew/opt/postgresql@17/bin/pg_dump
DUMP_FILE="$HOME/Desktop/uc_transfer.dump"

echo "Dumping local database to $DUMP_FILE ..."
"$PG_DUMP" -Fc "$LOCAL_DB_URL" -f "$DUMP_FILE"

echo "Done! Run ./restore.sh to push it to Render production."
