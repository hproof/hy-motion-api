"""任务路由"""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
import time

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import auth_dependency
from ..core.queue import get_queue
from ..core.runtime import get_runtime, get_runtime_lock
from ..core.worker import notify_worker
from ..schemas.task import (
    OutputFormat,
    TaskCreate,
    TaskCreateResponse,
    TaskDetailResponse,
    TaskResult,
    TaskStatus,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def process_task(task_id: str, task: dict | None = None):
    """处理单个任务，由后台 worker 线程串行调用。"""
    queue = get_queue()
    task = task or queue.get_task(task_id)

    if not task:
        return

    # 非 worker claim 场景下，补齐 running 状态。
    if task.get("status") != "running":
        queue.update_task(task_id, "running")
        task["status"] = "running"

    # 打印任务参数
    params = task["params"]
    print(f"[task] {task_id}: Processing: text='{params.get('text')}', duration={params.get('duration')}, seeds={params.get('seeds')}, cfg_scale={params.get('cfg_scale')}", flush=True)

    # 检查是否需要输出详细日志
    from ..core.config import get_settings
    settings = get_settings()
    verbose = settings.log_level == "debug"

    try:
        if settings.test_mode:
            # 测试模式：模拟 LLM 调用耗时，不执行真实推理
            time.sleep(3.0)

            output_format = params.get("output_format", "fbx")
            output_dir = Path(settings.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            dummy_fbx = output_dir / f"{task_id}.fbx"
            dummy_fbx.write_text("HY-Motion API test mode placeholder", encoding="utf-8")

            queue.update_task(
                task_id,
                "completed",
                result={
                    "fbx_files": [str(dummy_fbx)],
                    "html_content": "<html><body>HY-Motion API test mode</body></html>"
                    if output_format == "dict"
                    else None,
                    "message": "test mode",
                },
            )
            return

        runtime = get_runtime()

        # 生成随机种子（如果不提供）
        seeds = params.get("seeds")
        if not seeds:
            import random
            seeds = [random.randint(0, 999999)]

        # 转换 seeds 为逗号分隔字符串
        seeds_csv = ",".join(str(s) for s in seeds)
        output_format = params.get("output_format", "fbx")

        output_dir = settings.output_dir

        # T2MRuntime 和 stdout/stderr 捕获都依赖进程级全局状态，并发执行会互相干扰。
        capture_buffer = StringIO()

        with get_runtime_lock():
            with redirect_stdout(capture_buffer), redirect_stderr(capture_buffer):
                html_content, fbx_files, _ = runtime.generate_motion(
                    text=params["text"],
                    seeds_csv=seeds_csv,
                    duration=params["duration"],
                    cfg_scale=params.get("cfg_scale", 5.0),
                    output_format=output_format,
                    output_dir=output_dir,
                    original_text=params["text"],
                )

        captured = capture_buffer.getvalue()
        if verbose and captured:
            print(f"[task] {task_id}: --- HY-Motion-1.0 output start ---", flush=True)
            for line in captured.strip().splitlines():
                print(f"[task] {task_id}: {line}", flush=True)
            print(f"[task] {task_id}: --- HY-Motion-1.0 output end ---", flush=True)

        # 提取输出文件路径（fbx_files 是 [fbx, txt, fbx, txt, ...] 格式）
        # 只保留 fbx 文件（偶数索引）
        all_fbx_files = [f for i, f in enumerate(fbx_files) if i % 2 == 0] if fbx_files else []

        # 更新任务为完成
        queue.update_task(
            task_id,
            "completed",
            result={
                "fbx_files": all_fbx_files,
                "html_content": html_content if output_format == "dict" else None,
            },
        )

    except Exception as e:
        print(f"[task] {task_id}: Task processing error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        queue.update_task(task_id, "failed", error=str(e))


@router.post("", response_model=TaskCreateResponse, status_code=202)
async def create_task(
    task_data: TaskCreate,
    _: str = Depends(auth_dependency),
):
    """提交新任务"""
    queue = get_queue()

    # 构建参数字典
    params = {
        "text": task_data.text,
        "duration": task_data.duration,
        "seeds": task_data.seeds,
        "cfg_scale": task_data.cfg_scale,
        "output_format": task_data.output_format.value,
    }

    # 添加到队列
    task_id = queue.add_task(params)

    print(f"[task] {task_id}: Task submitted: text='{task_data.text}', duration={task_data.duration}, seeds={task_data.seeds}, cfg_scale={task_data.cfg_scale}", flush=True)

    # 唤醒单后台 worker 处理队列
    notify_worker()

    return TaskCreateResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=datetime.utcnow(),
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str, _: str = Depends(auth_dependency)):
    """查询任务状态和结果"""
    queue = get_queue()
    task = queue.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 解析时间字符串
    created_at = None
    updated_at = None
    completed_at = None

    if task.get("created_at"):
        created_at = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00"))
    if task.get("updated_at"):
        updated_at = datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00"))

    if task.get("status") == "completed" and updated_at:
        completed_at = updated_at

    return TaskDetailResponse(
        task_id=task["task_id"],
        status=TaskStatus(task["status"]),
        text=task.get("params", {}).get("text"),
        created_at=created_at,
        updated_at=updated_at,
        completed_at=completed_at,
        result=TaskResult(**task["result"]) if task.get("result") else None,
        error=task.get("error"),
    )
