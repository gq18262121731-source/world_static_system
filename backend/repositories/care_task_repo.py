from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from backend.repositories.sqlite_base import SQLiteRepositoryBase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CareTaskRepository(SQLiteRepositoryBase):
    """Persist community care tasks (inspection / follow-up / handover)."""

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS care_tasks (
                    id TEXT PRIMARY KEY,
                    community_id TEXT NOT NULL,
                    elder_id TEXT,
                    family_ids TEXT NOT NULL DEFAULT '[]',
                    task_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    title TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    due_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    done_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_care_tasks_community ON care_tasks (community_id, status)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_care_tasks_elder ON care_tasks (elder_id)"
            )

    def _row_to_task(self, row: Any) -> dict[str, Any]:
        family_ids = self.load_json(row["family_ids"])
        return {
            "id": row["id"],
            "community_id": row["community_id"],
            "elder_id": row["elder_id"] or None,
            "family_ids": family_ids if isinstance(family_ids, list) else [],
            "task_type": row["task_type"],
            "priority": row["priority"],
            "title": row["title"],
            "note": row["note"] or "",
            "owner": row["owner"] or "",
            "due_at": row["due_at"] or None,
            "status": row["status"],
            "created_by": row["created_by"] or "",
            "created_at": row["created_at"],
            "done_at": row["done_at"] or None,
        }

    def list_tasks(
        self,
        *,
        community_id: str,
        elder_ids: list[str] | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List tasks newest-first. elder_ids=[] means "no visible scope" and yields nothing."""
        if elder_ids is not None and not elder_ids:
            return []

        clauses = ["community_id = ?"]
        params: list[Any] = [community_id]

        if elder_ids is not None:
            placeholders = ",".join("?" for _ in elder_ids)
            clauses.append(f"elder_id IN ({placeholders})")
            params.extend(elder_ids)
        if status:
            clauses.append("status = ?")
            params.append(status)

        query = (
            "SELECT * FROM care_tasks WHERE "
            + " AND ".join(clauses)
            + " ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END,"
            + " CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 ELSE 2 END,"
            + " datetime(created_at) DESC LIMIT ?"
        )
        params.append(int(limit))

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM care_tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def create_task(
        self,
        *,
        community_id: str,
        title: str,
        task_type: str = "followup",
        priority: str = "P2",
        elder_id: str | None = None,
        family_ids: list[str] | None = None,
        note: str = "",
        owner: str = "",
        due_at: str | None = None,
        created_by: str = "",
    ) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO care_tasks (
                    id, community_id, elder_id, family_ids, task_type, priority,
                    title, note, owner, due_at, status, created_by, created_at, done_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, NULL)
                """,
                (
                    task_id,
                    community_id,
                    elder_id,
                    self.dump_json(family_ids or []),
                    task_type,
                    priority,
                    title,
                    note,
                    owner,
                    due_at,
                    created_by,
                    _now_iso(),
                ),
            )
        created = self.get_task(task_id)
        if created is None:
            raise RuntimeError("CARE_TASK_CREATE_FAILED")
        return created

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        title: str | None = None,
        note: str | None = None,
        priority: str | None = None,
        owner: str | None = None,
        due_at: str | None = None,
    ) -> dict[str, Any] | None:
        assignments: list[str] = []
        params: list[Any] = []

        if status is not None:
            assignments.append("status = ?")
            params.append(status)
            # 完成时间随状态联动，避免前端各自维护
            assignments.append("done_at = ?")
            params.append(_now_iso() if status == "done" else None)
        for column, value in (
            ("title", title),
            ("note", note),
            ("priority", priority),
            ("owner", owner),
            ("due_at", due_at),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                params.append(value)

        if not assignments:
            return self.get_task(task_id)

        params.append(task_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE care_tasks SET {', '.join(assignments)} WHERE id = ?",
                params,
            )
            if cursor.rowcount == 0:
                return None
        return self.get_task(task_id)

    def delete_task(self, task_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM care_tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0
