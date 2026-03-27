#!/bin/bash
DB_URL="postgresql://uc_transfer_user:xogCtmlr6VA6kxHfj4rSPnOiDTRLKAo3@dpg-d73ft18gjchc738no670-a.oregon-postgres.render.com/uc_transfer"

echo "Step 1: Dropping all tables..."
/opt/homebrew/opt/postgresql@17/bin/psql "$DB_URL" -c "
DO \$\$ DECLARE r RECORD;
BEGIN
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
  END LOOP;
END \$\$;
"

echo "Step 2: Restoring dump..."
/opt/homebrew/opt/postgresql@17/bin/pg_restore -f - ~/Desktop/uc_transfer.dump | grep -v transaction_timeout | /opt/homebrew/opt/postgresql@17/bin/psql "$DB_URL"

echo "Done!"
