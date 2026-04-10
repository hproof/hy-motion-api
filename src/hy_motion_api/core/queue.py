"""任务队列管理模块。

基于 SQLite 的任务队列，支持多进程安全消费。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import get_settings


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TaskQueue:
    """任务队列。"""

    def __init__(self, queue_path: str | None = None):
        self.queue_path = queue_path or get_settings().queue_path
        self._lock = threading.RLock()
        self._ensure_db()

    def _ensure_db(self) -> None:
        """确保数据库和表结构存在。"""
        db_path = Path(self.queue_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at
                ON tasks(status, created_at)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.queue_path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _row_to_task(self, row: Mapping[str, Any] | None) -> dict | None:
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "status": row["status"],
            "params": json.loads(row["params_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def add_task(self, params: dict) -> str:
        """添加新任务。"""
        with self._lock:
            task_id = str(uuid.uuid4())
            now = _utcnow_iso()
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        task_id, status, params_json, result_json, error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        "pending",
                        json.dumps(params, ensure_ascii=False),
                        None,
                        None,
                        now,
                        now,
                    ),
                )
            return task_id

    def get_task(self, task_id: str) -> dict | None:
        """获取任务。"""
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT task_id, status, params_json, result_json, error, created_at, updated_at
                    FROM tasks
                    WHERE task_id = ?
                    """,
                    (task_id,),
                ).fetchone()
            return self._row_to_task(row)

    def update_task(self, task_id: str, status: str, result: Any = None, error: str | None = None) -> None:
        """更新任务状态。"""
        with self._lock:
            assignments = ["status = ?", "updated_at = ?"]
            params: list[Any] = [status, _utcnow_iso()]

            if result is not None:
                assignments.append("result_json = ?")
                params.append(json.dumps(result, ensure_ascii=False))

            if error is not None:
                assignments.append("error = ?")
                params.append(error)
            elif status in {"running", "completed"}:
                assignments.append("error = NULL")

            params.append(task_id)

            with self._connect() as conn:
                conn.execute(
                    f"""
                    UPDATE tasks
                    SET {", ".join(assignments)}
                    WHERE task_id = ?
                    """,
                    params,
                )

    def claim_next_task(self) -> dict | None:
        """原子认领一个 pending 任务并标记为 running。"""
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT task_id, status, params_json, result_json, error, created_at, updated_at
                    FROM tasks
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """
                ).fetchone()

                if row is None:
                    conn.execute("COMMIT")
                    return None

                now = _utcnow_iso()
                cursor = conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'running', updated_at = ?, error = NULL
                    WHERE task_id = ? AND status = 'pending'
                    """,
                    (now, row["task_id"]),
                )

                if cursor.rowcount == 0:
                    conn.execute("ROLLBACK")
                    return None

                claimed = dict(row)
                claimed["status"] = "running"
                claimed["updated_at"] = now
                conn.execute("COMMIT")
                return self._row_to_task(claimed)

    def get_pending_tasks(self) -> list[dict]:
        """获取所有 pending 任务。"""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT task_id, status, params_json, result_json, error, created_at, updated_at
                    FROM tasks
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    """
                ).fetchall()
            return [self._row_to_task(row) for row in rows if row is not None]

    def get_queue_stats(self) -> dict[str, int]:
        """获取队列统计。"""
        with self._lock:
            stats = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM tasks
                    GROUP BY status
                    """
                ).fetchall()

            for row in rows:
                status = row["status"]
                if status in stats:
                    stats[status] = row["count"]
            return stats

    def get_output_file(self, task_id: str) -> str | None:
        """获取任务输出文件路径。"""
        task = self.get_task(task_id)
        if task and task.get("status") == "completed":
            result = task.get("result", {})
            return result.get("output_file")
        return None

    def cleanup_old_tasks(self, days: int) -> tuple[int, list[str]]:
        """清理 N 天前的任务和对应的输出文件。"""
        with self._lock:
            if days <= 0:
                return 0, []

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            deleted_tasks = 0
            deleted_files: list[str] = []
            to_delete: list[str] = []

            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT task_id, result_json, created_at
                    FROM tasks
                    """
                ).fetchall()

                for row in rows:
                    created_at_str = (row["created_at"] or "").replace("Z", "+00:00")
                    if not created_at_str:
                        continue

                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                    except ValueError:
                        continue

                    if created_at >= cutoff:
                        continue

                    result = json.loads(row["result_json"]) if row["result_json"] else {}
                    fbx_files = result.get("fbx_files", [])
                    for fbx_file in fbx_files:
                        if fbx_file and os.path.exists(fbx_file):
                            try:
                                os.remove(fbx_file)
                                deleted_files.append(fbx_file)
                            except OSError:
                                pass

                        if fbx_file:
                            txt_file = fbx_file.replace(".fbx", ".txt")
                            if os.path.exists(txt_file):
                                try:
                                    os.remove(txt_file)
                                    deleted_files.append(txt_file)
                                except OSError:
                                    pass

                    to_delete.append(row["task_id"])

                if to_delete:
                    placeholders = ", ".join("?" for _ in to_delete)
                    conn.execute(
                        f"DELETE FROM tasks WHERE task_id IN ({placeholders})",
                        to_delete,
                    )
                    deleted_tasks = len(to_delete)

            return deleted_tasks, deleted_files


_queue: TaskQueue | None = None


def get_queue() -> TaskQueue:
    """获取全局队列实例。"""
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue
