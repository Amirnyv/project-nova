"""Independent, transactional Nova social schema. No configuration reads."""


def migrate_nova_profiles(db, postgres=False):
    try:
        if postgres:
            db.execute("SET LOCAL lock_timeout = '5s'")
            db.execute("SET LOCAL statement_timeout = '60s'")
            db.execute('SELECT pg_advisory_xact_lock(1313822274, 1)')
        else:
            db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS nova_social_migrations (id INTEGER PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        if db.execute('SELECT id FROM nova_social_migrations WHERE id=1').fetchone():
            db.commit()
            return
        serial = 'SERIAL PRIMARY KEY' if postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        timestamp = 'TIMESTAMPTZ' if postgres else 'TIMESTAMP'
        alphabet = "handle !~ '[^a-z0-9_]'" if postgres else "handle NOT GLOB '*[^a-z0-9_]*'"
        db.execute(f'''CREATE TABLE nova_profiles (
            id {serial},
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
            handle TEXT NOT NULL UNIQUE CHECK(length(handle) BETWEEN 3 AND 30 AND {alphabet}),
            display_name TEXT NOT NULL CHECK(length(display_name) BETWEEN 1 AND 80),
            discoverable INTEGER NOT NULL DEFAULT 0 CHECK(discoverable IN (0,1)),
            allow_group_invites INTEGER NOT NULL DEFAULT 0 CHECK(allow_group_invites IN (0,1)),
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','deactivated')),
            created_at {timestamp} NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at {timestamp} NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        db.execute('INSERT INTO nova_social_migrations(id) VALUES(1)')
        db.commit()
    except Exception:
        db.rollback()
        raise
