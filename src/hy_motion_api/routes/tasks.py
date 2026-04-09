"""任务路由"""
import asyncio
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..core.auth import auth_dependency
from ..core.queue import get_queue
from ..core.runtime import get_runtime
from ..schemas.task import (
    OutputFormat,
    TaskCreate,
    TaskCreateResponse,
    TaskDetailResponse,
    TaskResult,
    TaskStatus,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def process_task_background(task_id: str):
    """后台处理任务（在线程池中运行，避免阻塞事件循环）"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_process_task(task_id))
    finally:
        loop.close()


async def _process_task(task_id: str):
    """异步处理单个任务"""
    queue = get_queue()
    task = queue.get_task(task_id)

    if not task:
        return

    # 更新状态为 running
    queue.update_task(task_id, "running")

    try:
        runtime = get_runtime()
        params = task["params"]

        # 转换 seeds 为逗号分隔字符串
        seeds_csv = ",".join(str(s) for s in params["seeds"])
        output_format = params.get("output_format", "fbx")

        # 调用 T2MRuntime 生成动作
        from ..core.config import get_settings
        settings = get_settings()
        output_dir = os.path.join(settings.hy_motion_path, settings.output_dir)

        html_content, fbx_files, _ = runtime.generate_motion(
            text=params["text"],
            seeds_csv=seeds_csv,
            duration=params["duration"],
            cfg_scale=params.get("cfg_scale", 5.0),
            output_format=output_format,
            output_dir=output_dir,
            original_text=params["text"],
        )

        # 提取输出文件路径
        output_file = None
        if fbx_files:
            # fbx_files 是 [fbx_path, txt_path, fbx_path, txt_path, ...] 格式
            output_file = fbx_files[0] if fbx_files else None

        # 更新任务为完成
        queue.update_task(
            task_id,
            "completed",
            result={
                "output_file": output_file,
                "html_content": html_content if output_format == "dict" else None,
            },
        )

    except Exception as e:
        queue.update_task(task_id, "failed", error=str(e))


@router.post("", response_model=TaskCreateResponse, status_code=202)
async def create_task(
    task_data: TaskCreate,
    _: str = Depends(auth_dependency),
    background_tasks: BackgroundTasks = None,
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

    # 启动后台处理
    if background_tasks:
        background_tasks.add_task(process_task_background, task_id)

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
