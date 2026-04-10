"""单后台 worker 线程，按顺序消费 pending 任务。"""
from __future__ import annotations

import threading

from .queue import get_queue

_wake_event = threading.Event()
_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None


def notify_worker() -> None:
    """唤醒后台 worker 处理新任务。"""
    _wake_event.set()


def _worker_main(poll_interval: float) -> None:
    """串行处理所有 pending 任务。"""
    from ..routes.tasks import process_task

    print("[worker] started", flush=True)
    try:
        while not _stop_event.is_set():
            queue = get_queue()
            task = queue.claim_next_task()

            if task:
                task_id = task["task_id"]
                print(f"[worker] dispatching task: {task_id}", flush=True)
                process_task(task_id, task=task)
                continue

            _wake_event.wait(timeout=poll_interval)
            _wake_event.clear()
    finally:
        print("[worker] stopped", flush=True)


def start_worker(poll_interval: float = 1.0) -> None:
    """启动单后台 worker 线程。"""
    global _worker_thread

    if _worker_thread is not None and _worker_thread.is_alive():
        return

    _stop_event.clear()
    _wake_event.clear()
    _worker_thread = threading.Thread(
        target=_worker_main,
        args=(poll_interval,),
        name="hy-motion-worker",
        daemon=True,
    )
    _worker_thread.start()


def stop_worker(timeout: float = 5.0) -> None:
    """请求后台 worker 停止并等待线程退出。"""
    global _worker_thread

    _stop_event.set()
    _wake_event.set()

    if _worker_thread is not None:
        _worker_thread.join(timeout=timeout)
        _worker_thread = None
