"""Independent social migration 2. Does not change AI or billing tables."""


def migrate_nova_chat(db, postgres=False):
    try:
        if postgres:
            db.execute("SET LOCAL lock_timeout = '5s'")
            db.execute("SET LOCAL statement_timeout = '60s'")
            db.execute('SELECT pg_advisory_xact_lock(1313822274, 1)')
        else:
            db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT id FROM nova_social_migrations WHERE id=1').fetchone():
            raise RuntimeError('Nova profile migration must run first')
        if db.execute('SELECT id FROM nova_social_migrations WHERE id=2').fetchone():
            db.commit()
            return
        serial = 'SERIAL PRIMARY KEY' if postgres else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        stamp = 'TIMESTAMPTZ' if postgres else 'TEXT'
        statements = [
            f'''CREATE TABLE nova_chat_conversations (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL CHECK(kind IN ('direct','group')),
                creator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                direct_low INTEGER REFERENCES users(id) ON DELETE RESTRICT,
                direct_high INTEGER REFERENCES users(id) ON DELETE RESTRICT,
                last_seq BIGINT NOT NULL DEFAULT 0 CHECK(last_seq >= 0),
                last_message_seq BIGINT NOT NULL DEFAULT 0 CHECK(last_message_seq BETWEEN 0 AND last_seq),
                created_at {stamp} NOT NULL, updated_at {stamp} NOT NULL, expires_at {stamp},
                UNIQUE(direct_low,direct_high),
                CHECK((kind='direct' AND direct_low IS NOT NULL AND direct_high IS NOT NULL AND direct_low < direct_high)
                   OR (kind='group' AND direct_low IS NULL AND direct_high IS NULL))
            )''',
            f'''CREATE TABLE nova_chat_members (
                id {serial},
                conversation_id TEXT NOT NULL REFERENCES nova_chat_conversations(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('invited','active','left','removed')),
                role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('owner','admin','member')),
                visible_from_seq BIGINT NOT NULL DEFAULT 1 CHECK(visible_from_seq >= 1),
                joined_at {stamp} NOT NULL, left_at {stamp},
                last_delivered_seq BIGINT NOT NULL DEFAULT 0 CHECK(last_delivered_seq >= 0),
                last_read_seq BIGINT NOT NULL DEFAULT 0 CHECK(last_read_seq BETWEEN 0 AND last_delivered_seq),
                muted INTEGER NOT NULL DEFAULT 0 CHECK(muted IN (0,1)),
                UNIQUE(conversation_id,user_id)
            )''',
            f'''CREATE TABLE nova_chat_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES nova_chat_conversations(id) ON DELETE CASCADE,
                seq BIGINT NOT NULL CHECK(seq > 0),
                sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                client_message_id TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type='text'),
                text TEXT NOT NULL CHECK(length(text) BETWEEN 1 AND 4000),
                created_at {stamp} NOT NULL, edited_at {stamp}, deleted_at {stamp},
                UNIQUE(conversation_id,seq),
                UNIQUE(conversation_id,sender_id,client_message_id)
            )''',
            f'''CREATE TABLE nova_chat_blocks (
                id {serial},
                blocker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                blocked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at {stamp} NOT NULL,
                UNIQUE(blocker_id,blocked_id), CHECK(blocker_id <> blocked_id)
            )''',
            'CREATE INDEX nova_chat_member_user ON nova_chat_members(user_id,state,conversation_id)',
            'CREATE INDEX nova_chat_conversation_created ON nova_chat_conversations(created_at,id)',
            'CREATE INDEX nova_chat_blocks_reverse ON nova_chat_blocks(blocked_id,blocker_id)',
            'CREATE INDEX nova_profiles_discovery ON nova_profiles(discoverable,status,handle)',
        ]
        for statement in statements:
            db.execute(statement)
        db.execute('INSERT INTO nova_social_migrations(id) VALUES(2)')
        db.commit()
    except Exception:
        db.rollback()
        raise
