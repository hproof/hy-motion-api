"""FastAPI 主应用"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, Header
from fastapi.responses import FileResponse, StreamingResponse

from .core.config import get_settings
from .core.queue import get_queue
from .core.runtime import get_runtime
from .core.worker import start_worker, stop_worker
from .routes import health, queue, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 切换到 HY-Motion-1.0 目录（HY-Motion-1.0 内部使用相对路径）
    settings = get_settings()
    hy_motion_path = settings.hy_motion_path
    original_cwd = os.getcwd()
    os.chdir(hy_motion_path)
    print(f">>> Changed working directory to: {hy_motion_path}")

    # 清理过期任务和文件
    queue = get_queue()
    deleted_tasks, deleted_files = queue.cleanup_old_tasks(settings.retention_days)
    if deleted_tasks > 0:
        print(f">>> Cleaned up {deleted_tasks} old tasks and {len(deleted_files)} files")

    # 启动时预加载模型
    if settings.test_mode:
        print(">>> Test mode enabled, skip loading T2MRuntime")
    else:
        print(">>> Loading T2MRuntime...")
        try:
            runtime = get_runtime()
            print(f">>> T2MRuntime loaded, GPU available: {runtime.device_ids}")
        except Exception as e:
            print(f">>> Failed to load T2MRuntime: {e}")

    start_worker()
    print(">>> Background worker started")

    yield

    stop_worker()

    # 关闭时恢复工作目录
    os.chdir(original_cwd)
    print(">>> Shutting down...")


app = FastAPI(
    title="HY-Motion API",
    description="HTTP API for HY-Motion-1.0 text-to-motion generation",
    version="0.1.0",
    lifespan=lifespan,
)

# 注册路由
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(queue.router)


@app.get("/")
async def root():
    """根路径"""
    return {"message": "HY-Motion API", "docs": "/docs"}


@app.get("/download/{task_id}")
async def download_file(
    task_id: str,
    version: int | None = None,
    format: str = "fbx",
    x_id: str | None = Header(None),
    x_token: str | None = Header(None),
):
    """下载任务结果文件

    Query Parameters:
        version: 版本号（0-3），默认下载第一个版本
        format: 下载格式，fbx（默认）或 dict
    """
    from .core.auth import verify_token

    # 验证凭证
    verify_token(x_id, x_token)

    queue = get_queue()
    task = queue.get_task(task_id)

    if not task:
        return {"error": "Task not found"}, 404

    if task["status"] != "completed":
        return {"error": "Task not completed", "status": task["status"]}, 400

    result = task.get("result", {})

    if format == "dict":
        # 返回 HTML 内容
        html_content = result.get("html_content")
        if html_content:
            return Response(content=html_content, media_type="text/html")
        return {"error": "No dict output available"}, 404

    # 返回 FBX 文件
    fbx_files = result.get("fbx_files", [])
    if not fbx_files:
        return {"error": "No FBX files available"}, 404

    # 根据 version 选择文件，默认选第一个
    idx = version if version is not None and 0 <= version < len(fbx_files) else 0
    output_file = fbx_files[idx]

    if not os.path.exists(output_file):
        return {"error": f"Output file not found: {output_file}"}, 404

    return FileResponse(
        path=output_file,
        filename=os.path.basename(output_file),
        media_type="application/octet-stream",
    )
