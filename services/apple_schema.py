"""Billing migration 2: account tokens and environment/state metadata only."""

from services.billing_schema import postgres_migration_complete


def migrate_apple_billing(db, postgres=False):
    try:
        if postgres and postgres_migration_complete(db, 2):
            return
        db.execute('LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE' if postgres else 'BEGIN IMMEDIATE')
        if db.execute('SELECT id FROM billing_migrations WHERE id=2').fetchone():
            db.commit()
            return
        serial = 'SERIAL PRIMARY KEY' if postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        db.execute(f"""CREATE TABLE apple_account_tokens (
            id {serial}, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
            app_account_token TEXT NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("ALTER TABLE apple_original_transactions ADD COLUMN environment TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE apple_notifications ADD COLUMN environment TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE apple_notifications ADD COLUMN outcome TEXT NOT NULL DEFAULT 'pending'")
        db.execute("ALTER TABLE subscriptions ADD COLUMN apple_environment TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE subscriptions ADD COLUMN apple_state TEXT NOT NULL DEFAULT ''")
        db.execute('ALTER TABLE subscriptions ADD COLUMN apple_renewal_at TIMESTAMP')
        db.execute('ALTER TABLE subscriptions ADD COLUMN apple_auto_renews INTEGER')
        db.execute('INSERT INTO billing_migrations(id) VALUES(2)')
        db.commit()
    except Exception:
        db.rollback()
        raise
