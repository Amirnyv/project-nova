from database import get_db


def create_project(user_id, name, description=""):
    name = name.strip()
    description = description.strip()

    if not name:
        return {
            "error": "Project name is required."
        }

    connection = get_db()

    cursor = connection.execute(
        """
        INSERT INTO projects (
            user_id,
            name,
            description
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            name,
            description
        )
    )

    connection.commit()

    project_id = cursor.lastrowid

    connection.close()

    return {
        "success": True,
        "id": project_id,
        "name": name,
        "description": description
    }


def get_projects(user_id):
    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            id,
            name,
            description,
            created_at,
            updated_at
        FROM projects
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]