"""任务队列管理模块

基于 JSON Lines 文件的任务队列，支持并发访问。
"""
import json
import uuid
import fcntl
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import get_settings


class TaskQueue:
    """任务队列"""

    def __init__(self, queue_path: str | None = None):
        self.queue_path = queue_path or get_settings().queue_path
        self._ensure_file()

    def _ensure_file(self):
        """确保队列文件存在"""
        Path(self.queue_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(self.queue_path).exists():
            Path(self.queue_path).touch()

    def _read_all(self) -> list[dict]:
        """读取所有任务"""
        tasks = []
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            tasks.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except FileNotFoundError:
            pass
        return tasks

    def _append(self, task: dict):
        """追加任务到队列"""
        with open(self.queue_path, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(json.dumps(task, ensure_ascii=False) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def add_task(self, params: dict) -> str:
        """添加新任务

        Args:
            params: 任务参数字典

        Returns:
            str: 任务 ID
        """
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "status": "pending",
            "params": params,
            "result": None,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        self._append(task)
        return task_id

    def get_task(self, task_id: str) -> dict | None:
        """获取任务（最新状态）"""
        tasks = self._read_all()
        for task in reversed(tasks):
            if task["task_id"] == task_id:
                return task
        return None

    def update_task(self, task_id: str, status: str, result: Any = None, error: str | None = None):
        """更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            result: 结果数据
            error: 错误信息
        """
        tasks = self._read_all()

        # 找到并更新任务
        found = False
        for task in tasks:
            if task["task_id"] == task_id:
                task["status"] = status
                task["updated_at"] = datetime.utcnow().isoformat() + "Z"
                if result is not None:
                    task["result"] = result
                if error is not None:
                    task["error"] = error
                found = True

        if not found:
            return

        # 重写整个文件
        with open(self.queue_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            for task in tasks:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_pending_tasks(self) -> list[dict]:
        """获取所有 pending 任务（按创建时间排序）"""
        tasks = self._read_all()
        pending = [t for t in tasks if t["status"] == "pending"]
        return sorted(pending, key=lambda x: x["created_at"])

    def get_queue_stats(self) -> dict[str, int]:
        """获取队列统计"""
        tasks = self._read_all()

        # 只保留每个 task_id 的最新状态
        latest_tasks: dict[str, dict] = {}
        for task in tasks:
            latest_tasks[task["task_id"]] = task

        stats = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        for task in latest_tasks.values():
            status = task.get("status", "unknown")
            if status in stats:
                stats[status] += 1

        return stats

    def get_output_file(self, task_id: str) -> str | None:
        """获取任务输出文件路径"""
        task = self.get_task(task_id)
        if task and task.get("status") == "completed":
            result = task.get("result", {})
            return result.get("output_file")
        return None

    def cleanup_old_tasks(self, days: int) -> tuple[int, list[str]]:
        """清理 N 天前的任务和对应的输出文件

        Args:
            days: 保留天数

        Returns:
            tuple: (删除的任务数, 删除的文件列表)
        """
        if days <= 0:
            return 0, []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        tasks = self._read_all()
        deleted_tasks = 0
        deleted_files = []

        # 过滤出需要保留的任务
        remaining_tasks = []
        for task in tasks:
            try:
                created_at_str = task.get("created_at", "")
                # 处理可能的 Z 后缀
                created_at_str = created_at_str.replace("Z", "+00:00")
                if created_at_str:
                    # 尝试解析 ISO 格式
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                    except ValueError:
                        # 尝试简单解析
                        created_at = datetime.strptime(created_at_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                else:
                    remaining_tasks.append(task)
                    continue
            except (ValueError, AttributeError):
                remaining_tasks.append(task)
                continue

            if created_at < cutoff:
                # 收集需要删除的文件
                result = task.get("result", {})
                fbx_files = result.get("fbx_files", [])
                for fbx_file in fbx_files:
                    if fbx_file and os.path.exists(fbx_file):
                        try:
                            os.remove(fbx_file)
                            deleted_files.append(fbx_file)
                        except OSError:
                            pass
                # 同时删除同名的 .txt 文件
                for fbx_file in fbx_files:
                    if fbx_file:
                        txt_file = fbx_file.replace(".fbx", ".txt")
                        if os.path.exists(txt_file):
                            try:
                                os.remove(txt_file)
                                deleted_files.append(txt_file)
                            except OSError:
                                pass
                deleted_tasks += 1
            else:
                remaining_tasks.append(task)

        # 重写队列文件
        with open(self.queue_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            for task in remaining_tasks:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return deleted_tasks, deleted_files


# 全局队列实例
_queue: TaskQueue | None = None


def get_queue() -> TaskQueue:
    """获取全局队列实例"""
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue
