"""Transactional, repeatable billing foundation migration; never run on import.

SQLite rebuilds only subscriptions to remove UNIQUE(user_id), retaining every
row and ID. PostgreSQL drops only that unique constraint. Conflicting ownership
or unexpected SQLite schema dependencies abort rather than silently lose data.
"""
import re


def postgres_migration_complete(db, version):
    """Bound lock waits and skip completed DDL without locking subscriptions.

    SET LOCAL resets at commit/rollback. The authoritative version check still
    runs under the migration's table lock when work is required, so concurrent
    startup workers cannot both apply the same migration.
    """
    db.execute("SET LOCAL lock_timeout = '5s'")
    db.execute("SET LOCAL statement_timeout = '60s'")
    exists = db.execute("SELECT to_regclass('billing_migrations') AS name").fetchone()
    if exists and exists['name']:
        if db.execute('SELECT id FROM billing_migrations WHERE id=?', (version,)).fetchone():
            db.commit()
            return True
    return False


def migrate_billing(db, postgres=False):
    try:
        if postgres:
            if postgres_migration_complete(db, 1):
                return
            db.execute('LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE')
        else:
            db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS billing_migrations (id INTEGER PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        if db.execute('SELECT id FROM billing_migrations WHERE id=1').fetchone():
            db.commit()
            return
        if postgres:
            constraints = db.execute("""SELECT conname, pg_get_constraintdef(oid) AS definition
                FROM pg_constraint WHERE conrelid='subscriptions'::regclass AND contype='u'""").fetchall()
            if sum(row['definition'].replace('"', '').strip() == 'UNIQUE (user_id)' for row in constraints) != 1:
                raise RuntimeError('Unexpected subscription uniqueness; manual migration review required')
            for row in constraints:
                if row['definition'].replace('"', '').strip() == 'UNIQUE (user_id)':
                    name = row['conname'].replace('"', '""')
                    db.execute('ALTER TABLE subscriptions DROP CONSTRAINT "' + name + '"')
            db.execute('ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP')
        else:
            schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='subscriptions'").fetchone()['sql']
            # Preserve other schema details; refuse an unfamiliar unique declaration.
            updated, count = re.subn(r'(user_id\s+INTEGER\s+NOT\s+NULL)\s+UNIQUE', r'\1', schema, flags=re.I)
            if count != 1:
                raise RuntimeError('Unexpected subscription schema; manual migration review required')
            sequence = db.execute("SELECT seq FROM sqlite_sequence WHERE name='subscriptions'").fetchone()
            extras = db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='subscriptions' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
            for table in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                name = table['name'].replace('"', '""')
                if any(r['table'] == 'subscriptions' for r in db.execute('PRAGMA foreign_key_list("' + name + '")').fetchall()):
                    raise RuntimeError('Inbound subscription references require migration review')
            updated = re.sub(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?["`\[]?subscriptions["`\]]?',
                             'CREATE TABLE subscriptions_billing_new', updated, count=1, flags=re.I)
            db.execute(updated)
            db.execute('INSERT INTO subscriptions_billing_new SELECT * FROM subscriptions')
            db.execute('DROP TABLE subscriptions')
            db.execute('ALTER TABLE subscriptions_billing_new RENAME TO subscriptions')
            if sequence:
                db.execute("UPDATE sqlite_sequence SET seq = ? WHERE name='subscriptions'", (sequence['seq'],))
            for extra in extras:
                db.execute(extra['sql'])
            db.execute('ALTER TABLE subscriptions ADD COLUMN verified_at TIMESTAMP')
        # Only infer Stripe from Stripe-shaped identifiers, not from paid access alone.
        db.execute("""UPDATE subscriptions SET provider = CASE
            WHEN substr(provider_subscription_id, 1, 4) = 'sub_' OR substr(provider_customer_id, 1, 4) = 'cus_'
            THEN 'stripe' ELSE 'legacy' END WHERE provider IS NULL OR provider=''""")
        db.execute("""CREATE UNIQUE INDEX subscriptions_provider_identity
            ON subscriptions(provider, provider_subscription_id)
            WHERE provider_subscription_id IS NOT NULL AND provider_subscription_id <> ''""")
        db.execute("""CREATE UNIQUE INDEX subscriptions_provider_legacy_user
            ON subscriptions(user_id, provider)
            WHERE provider_subscription_id IS NULL OR provider_subscription_id = ''""")
        serial = 'SERIAL PRIMARY KEY' if postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        db.execute(f"""CREATE TABLE IF NOT EXISTS apple_original_transactions (
            id {serial}, original_transaction_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            last_signed_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(original_transaction_id, user_id))""")
        # Matches the existing uncommitted SQLite transaction table, adds PG parity.
        db.execute(f"""CREATE TABLE IF NOT EXISTS apple_transactions (
            id {serial}, user_id INTEGER NOT NULL REFERENCES users(id),
            transaction_id TEXT NOT NULL UNIQUE, original_transaction_id TEXT NOT NULL,
            product_id TEXT NOT NULL, plan TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
            purchased_at TIMESTAMP, expires_at TIMESTAMP, revoked_at TIMESTAMP,
            environment TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        # Conflicting historical ownership fails the unique constraint and rolls back.
        db.execute("""INSERT INTO apple_original_transactions (original_transaction_id, user_id)
            SELECT DISTINCT original_transaction_id, user_id FROM apple_transactions WHERE 1=1
            ON CONFLICT (original_transaction_id, user_id) DO NOTHING""")
        db.execute('ALTER TABLE apple_transactions ADD COLUMN signed_at TIMESTAMP')
        db.execute('CREATE INDEX IF NOT EXISTS idx_apple_transactions_user_id ON apple_transactions(user_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_apple_transactions_original_transaction_id ON apple_transactions(original_transaction_id)')
        db.execute(f"""CREATE TABLE IF NOT EXISTS apple_notifications (
            id {serial}, notification_uuid TEXT NOT NULL UNIQUE,
            original_transaction_id TEXT, signed_at TIMESTAMP NOT NULL,
            notification_type TEXT NOT NULL, processed_at TIMESTAMP,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        if postgres:
            db.execute("""ALTER TABLE apple_transactions ADD CONSTRAINT apple_transaction_owner
                FOREIGN KEY(original_transaction_id, user_id)
                REFERENCES apple_original_transactions(original_transaction_id, user_id)""")
            db.execute("""CREATE FUNCTION nova_apple_owner_immutable() RETURNS trigger
                LANGUAGE plpgsql AS $$ BEGIN
                RAISE EXCEPTION 'Apple transaction ownership is bound'; END; $$""")
            db.execute("""CREATE TRIGGER apple_original_owner_immutable
                BEFORE UPDATE OF original_transaction_id, user_id OR DELETE ON apple_original_transactions
                FOR EACH ROW EXECUTE FUNCTION nova_apple_owner_immutable()""")
        else:
            for event in ('INSERT', 'UPDATE'):
                db.execute(f"""CREATE TRIGGER apple_transaction_owner_{event.lower()}
                    BEFORE {event} ON apple_transactions FOR EACH ROW
                    WHEN NOT EXISTS (SELECT 1 FROM apple_original_transactions
                        WHERE original_transaction_id=NEW.original_transaction_id AND user_id=NEW.user_id)
                    BEGIN SELECT RAISE(ABORT, 'Apple transaction ownership mismatch'); END""")
            for event in ('UPDATE OF original_transaction_id, user_id', 'DELETE'):
                suffix = 'update' if event.startswith('UPDATE') else 'delete'
                db.execute(f"""CREATE TRIGGER apple_original_owner_{suffix}
                    BEFORE {event} ON apple_original_transactions FOR EACH ROW
                    BEGIN SELECT RAISE(ABORT, 'Apple transaction ownership is bound'); END""")
        db.execute('INSERT INTO billing_migrations (id) VALUES (1)')
        db.commit()
    except Exception:
        db.rollback()
        raise
