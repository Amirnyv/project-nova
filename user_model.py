from flask_login import UserMixin
from database import get_db


class User(UserMixin):
    def __init__(self, user_id, username, email):
        self.id = str(user_id)
        self.username = username
        self.email = email


def get_user_by_id(user_id):
    connection = get_db()

    user = connection.execute(
        """
        SELECT id, username, email
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    connection.close()

    if user is None:
        return None

    return User(
        user["id"],
        user["username"],
        user["email"]
    )