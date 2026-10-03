
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services import workspace_confirmations as wc
from services import workspace_schema


class WorkspaceSecurityTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(
            self.temp.name, "test_workspace.db"
        )

        def connect():
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            return db

        self.connect = connect

        db = connect()
        db.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY
            );

            CREATE TABLE connections (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL
            );

            INSERT INTO users VALUES (1);
            INSERT INTO users VALUES (2);

            INSERT INTO connections
            VALUES (10, 1, 'google', 'connected');

            INSERT INTO connections
            VALUES (20, 2, 'google', 'connected');
        """)
        db.commit()
        db.close()

        self.schema_patch = patch.object(
            __import__("database"), "get_db", connect
        )
        self.confirm_patch = patch.object(
            wc, "get_db", connect
        )

        self.schema_patch.start()
        self.confirm_patch.start()

        workspace_schema.initialize_workspace_schema()

    def tearDown(self):
        self.confirm_patch.stop()
        self.schema_patch.stop()
        self.temp.cleanup()

    def stage(self):
        return wc.stage_workspace_action(
            1,
            10,
            "calendar.create",
            {
                "summary": "Security test",
                "start": "2026-10-01T10:00:00Z",
                "end": "2026-10-01T11:00:00Z",
            },
        )

    def approve(self, proposal, user=1, account=10):
        return wc.approve_workspace_action(
            user,
            account,
            proposal["id"],
            proposal["confirmationToken"],
            proposal["requestId"],
        )

    def test_single_use(self):
        proposal = self.stage()

        result = self.approve(proposal)
        self.assertEqual(result["status"], "claimed")

        with self.assertRaises(
            wc.WorkspaceConfirmationError
        ):
            self.approve(proposal)

    def test_wrong_account(self):
        proposal = self.stage()

        with self.assertRaises(
            wc.WorkspaceConfirmationError
        ):
            self.approve(proposal, user=2, account=20)

        self.assertEqual(
            self.approve(proposal)["status"],
            "claimed",
        )

    def test_expired_proposal(self):
        proposal = self.stage()

        db = self.connect()
        db.execute(
            """
            UPDATE workspace_proposals
            SET expires_at = 1
            WHERE proposal_id = ?
            """,
            (proposal["id"],),
        )
        db.commit()
        db.close()

        with self.assertRaises(
            wc.WorkspaceConfirmationError
        ):
            self.approve(proposal)

    def test_status_is_private(self):
        proposal = self.stage()

        with self.assertRaises(
            wc.WorkspaceConfirmationError
        ):
            wc.get_workspace_request_status(
                2, proposal["requestId"]
            )

        status = wc.get_workspace_request_status(
            1, proposal["requestId"]
        )
        self.assertEqual(status["status"], "pending")

    def test_expiration_format(self):
        proposal = self.stage()

        self.assertRegex(
            proposal["expiresAt"],
            r"^\d{4}-\d{2}-\d{2}T.*Z$",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
