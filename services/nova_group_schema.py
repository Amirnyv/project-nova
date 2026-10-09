"""Social migration 3: group metadata and ordered membership history."""


def migrate_nova_groups(db, postgres=False):
    try:
        if postgres:
            db.execute("SET LOCAL lock_timeout = '5s'")
            db.execute("SET LOCAL statement_timeout = '60s'")
            db.execute('SELECT pg_advisory_xact_lock(1313822274, 1)')
        else:
            db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT id FROM nova_social_migrations WHERE id=2').fetchone():
            raise RuntimeError('Direct messaging migration must run first')
        if db.execute('SELECT id FROM nova_social_migrations WHERE id=3').fetchone():
            db.commit()
            return
        stamp = 'TIMESTAMPTZ' if postgres else 'TEXT'
        statements = [
            "ALTER TABLE nova_chat_conversations ADD COLUMN name TEXT CHECK(name IS NULL OR length(name) BETWEEN 1 AND 80)",
            'ALTER TABLE nova_chat_conversations ADD COLUMN last_event_seq BIGINT NOT NULL DEFAULT 0 CHECK(last_event_seq >= 0)',
            f'ALTER TABLE nova_chat_conversations ADD COLUMN closed_at {stamp}',
            'ALTER TABLE nova_chat_members ADD COLUMN invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL',
            'ALTER TABLE nova_chat_members ADD COLUMN visible_event_from BIGINT NOT NULL DEFAULT 1 CHECK(visible_event_from >= 1)',
            "CREATE UNIQUE INDEX nova_chat_one_active_owner ON nova_chat_members(conversation_id) WHERE role='owner' AND state='active'",
            f'''CREATE TABLE nova_chat_events (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES nova_chat_conversations(id) ON DELETE CASCADE,
                seq BIGINT NOT NULL CHECK(seq > 0),
                kind TEXT NOT NULL CHECK(kind IN ('created','invited','joined','declined','removed','left','role_changed','ownership_transferred','renamed','closed')),
                actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                target_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                detail TEXT CHECK(detail IS NULL OR length(detail)<=80),
                created_at {stamp} NOT NULL,
                UNIQUE(conversation_id,seq)
            )''',
        ]
        for statement in statements:
            db.execute(statement)
        db.execute('INSERT INTO nova_social_migrations(id) VALUES(3)')
        db.commit()
    except Exception:
        db.rollback()
        raise
