
"""Persistent Google Workspace security tables.

Compatible with Nova's SQLite and PostgreSQL database wrappers.
Does not execute Google Workspace actions.
"""



def initialize_workspace_schema(db_factory=None, postgres=None):
    if db_factory is None:
        from database import get_db, USE_POSTGRES
        db_factory = get_db
        postgres = USE_POSTGRES
    db = db_factory()

    id_type = (
        "SERIAL PRIMARY KEY"
        if postgres
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS workspace_proposals (
            id {id_type},
            proposal_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            connection_id INTEGER NOT NULL,
            operation TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            arguments_hash TEXT NOT NULL,
            confirmation_hash TEXT NOT NULL UNIQUE,
            expected_version TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            confirmed_at INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (connection_id)
                REFERENCES connections(id),
            CHECK (
                status IN (
                    'pending',
                    'confirmed',
                    'cancelled',
                    'expired'
                )
            )
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS workspace_requests (
            id {id_type},
            request_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            connection_id INTEGER NOT NULL,
            proposal_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            arguments_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result_json TEXT,
            error_code TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (connection_id)
                REFERENCES connections(id),
            FOREIGN KEY (proposal_id)
                REFERENCES workspace_proposals(proposal_id),
            UNIQUE (user_id, request_id),
            CHECK (
                status IN (
                    'pending',
                    'executing',
                    'succeeded',
                    'failed',
                    'uncertain'
                )
            )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_workspace_proposals_user
        ON workspace_proposals (
            user_id,
            connection_id,
            status
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_workspace_requests_proposal
        ON workspace_requests (
            proposal_id,
            status
        )
        """,
    ]

    try:
        for statement in statements:
            db.execute(statement)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    initialize_workspace_schema()
    print("Workspace security tables initialized.")