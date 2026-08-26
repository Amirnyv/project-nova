import os
import re
import sqlite3

from pathlib import Path


# -------------------------------------------------
# DATABASE CONFIG
# -------------------------------------------------

DB_PATH = (
    Path(__file__).resolve().parent
    / "nova.db"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    ""
).strip()

USE_POSTGRES = bool(
    DATABASE_URL
)


# -------------------------------------------------
# POSTGRES IMPORTS
# -------------------------------------------------

if USE_POSTGRES:

    import psycopg

    from psycopg.rows import dict_row


# -------------------------------------------------
# CURSOR WRAPPER
# -------------------------------------------------

class DatabaseCursor:

    def __init__(
        self,
        cursor,
        lastrowid=None
    ):

        self.cursor = cursor

        self.lastrowid = (
            lastrowid
        )


    @property
    def rowcount(self):

        return self.cursor.rowcount


    def fetchone(self):

        return self.cursor.fetchone()


    def fetchall(self):

        return self.cursor.fetchall()


# -------------------------------------------------
# POSTGRES CONNECTION WRAPPER
# -------------------------------------------------

class PostgresConnection:

    def __init__(self):

        self.connection = (
            psycopg.connect(
                DATABASE_URL,
                row_factory=dict_row
            )
        )


    def _translate_sql(
        self,
        sql
    ):

        # Convert SQLite placeholders:
        #
        # WHERE id = ?
        #
        # into PostgreSQL:
        #
        # WHERE id = %s

        sql = sql.replace(
            "?",
            "%s"
        )


        # Convert SQLite current-month
        # date expression used by Nova.

        sql = re.sub(
            r"""
            datetime\s*\(
                \s*'now'\s*,
                \s*'start\sof\smonth'\s*
            \)
            """,
            (
                "date_trunc("
                "'month', "
                "CURRENT_TIMESTAMP"
                ")"
            ),
            sql,
            flags=(
                re.IGNORECASE
                |
                re.VERBOSE
            )
        )


        return sql


    def execute(
        self,
        sql,
        parameters=()
    ):

        translated_sql = (
            self._translate_sql(
                sql
            )
        )

        cursor = (
            self.connection.cursor()
        )


        try:

            upper_sql = (
                translated_sql
                .strip()
                .upper()
            )


            # Nova relies on SQLite's
            # cursor.lastrowid.
            #
            # PostgreSQL normally uses
            # RETURNING id instead.

            is_insert = (
                upper_sql.startswith(
                    "INSERT"
                )
            )

            has_returning = (
                " RETURNING "
                in upper_sql
            )


            if (
                is_insert
                and not has_returning
            ):

                translated_sql = (
                    translated_sql
                    .rstrip()
                    .rstrip(";")
                    + " RETURNING id"
                )


                cursor.execute(
                    translated_sql,
                    parameters
                )


                row = (
                    cursor.fetchone()
                )


                lastrowid = None


                if row:

                    if isinstance(
                        row,
                        dict
                    ):

                        lastrowid = (
                            row.get("id")
                        )

                    else:

                        lastrowid = (
                            row[0]
                        )


                return DatabaseCursor(
                    cursor,
                    lastrowid
                )


            cursor.execute(
                translated_sql,
                parameters
            )


            return DatabaseCursor(
                cursor
            )


        except psycopg.IntegrityError as error:

            self.connection.rollback()

            raise sqlite3.IntegrityError(
                str(error)
            ) from error


        except psycopg.OperationalError as error:

            self.connection.rollback()

            raise sqlite3.OperationalError(
                str(error)
            ) from error


    def commit(self):

        self.connection.commit()


    def rollback(self):

        self.connection.rollback()


    def close(self):

        self.connection.close()


# -------------------------------------------------
# GET DATABASE CONNECTION
# -------------------------------------------------

def get_db():

    if USE_POSTGRES:

        return PostgresConnection()


    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


# -------------------------------------------------
# DATABASE INITIALIZATION
# -------------------------------------------------

def init_db():

    if USE_POSTGRES:

        init_postgres_db()

    else:

        init_sqlite_db()


# -------------------------------------------------
# SQLITE DATABASE
# -------------------------------------------------

def init_sqlite_db():

    connection = get_db()


    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            cash REAL NOT NULL DEFAULT 10000.00,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );


        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            shares REAL NOT NULL,
            average_price REAL NOT NULL,
            UNIQUE(user_id, symbol),
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );


        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            symbol TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL,
            total REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );


        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );


        CREATE TABLE IF NOT EXISTS project_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL UNIQUE,
            content TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        );


        CREATE TABLE IF NOT EXISTS project_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        );


        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            mime_type TEXT DEFAULT '',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        );


        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            plan TEXT NOT NULL DEFAULT 'none',
            status TEXT NOT NULL DEFAULT 'inactive',
            provider TEXT DEFAULT '',
            provider_customer_id TEXT DEFAULT '',
            provider_subscription_id TEXT DEFAULT '',
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );


        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER,
            title TEXT NOT NULL DEFAULT 'New Conversation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        );


        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id),
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        );


        CREATE TABLE IF NOT EXISTS ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            conversation_id INTEGER,
            model TEXT NOT NULL DEFAULT '',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
        );
        """
    )


    connection.commit()

    connection.close()


# -------------------------------------------------
# POSTGRESQL DATABASE
# -------------------------------------------------

def init_postgres_db():

    connection = get_db()


    statements = [

        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS portfolios (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            cash DOUBLE PRECISION NOT NULL DEFAULT 10000.00,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS positions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            shares DOUBLE PRECISION NOT NULL,
            average_price DOUBLE PRECISION NOT NULL,
            UNIQUE(user_id, symbol),
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            symbol TEXT NOT NULL,
            shares DOUBLE PRECISION NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            total DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS project_notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL UNIQUE,
            content TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS project_tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS project_files (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            mime_type TEXT DEFAULT '',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        )
        """,


                      """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            plan TEXT NOT NULL DEFAULT 'none',
            status TEXT NOT NULL DEFAULT 'inactive',
            provider TEXT DEFAULT '',
            provider_customer_id TEXT DEFAULT '',
            provider_subscription_id TEXT DEFAULT '',
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            project_id INTEGER,
            title TEXT NOT NULL DEFAULT 'New Conversation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id),
            FOREIGN KEY (user_id)
                REFERENCES users(id)
        )
        """,


        """
        CREATE TABLE IF NOT EXISTS ai_usage (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            conversation_id INTEGER,
            model TEXT NOT NULL DEFAULT '',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
        )
        """
    ]


    try:

        for statement in statements:

            connection.execute(
                statement
            )


        connection.commit()


    except Exception:

        connection.rollback()

        raise


    finally:

        connection.close()