"""Additive paper-trading state; no existing balances/history are rewritten."""

def initialize_paper_schema(factory, postgres=False):
    db = factory()
    try:
        if postgres:
            db.execute("SET LOCAL lock_timeout = '5s'")
            db.execute("SET LOCAL statement_timeout = '60s'")
            db.execute('SELECT pg_advisory_xact_lock(73190214)')
        else:
            db.execute('BEGIN IMMEDIATE')
        serial = 'SERIAL PRIMARY KEY' if postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        db.execute(f'''CREATE TABLE IF NOT EXISTS paper_previews (
            id {serial}, preview_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at DOUBLE PRECISION NOT NULL, payload TEXT NOT NULL,
            result TEXT, invalidated INTEGER NOT NULL DEFAULT 0)''')
        db.execute('CREATE INDEX IF NOT EXISTS paper_previews_user ON paper_previews(user_id)')
        db.execute(f'''CREATE TABLE IF NOT EXISTS paper_trade_details (
            id {serial}, trade_id INTEGER NOT NULL UNIQUE REFERENCES trades(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id), realized TEXT NOT NULL)''')
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
