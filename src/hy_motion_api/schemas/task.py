"""任务相关的 Pydantic 模型"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """输出格式"""
    FBX = "fbx"
    DICT = "dict"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============ 请求模型 ============

class TaskCreate(BaseModel):
    """创建任务的请求体"""
    text: str = Field(..., min_length=1, max_length=500, description="动作描述文本（英文）")
    duration: float = Field(default=5.0, gt=0, le=12.0, description="动作时长（秒），建议 0.5-12 秒")
    seeds: list[int] = Field(default=[0, 1, 2, 3], max_length=10, description="随机种子列表")
    cfg_scale: float = Field(default=5.0, ge=1.0, le=20.0, description="CFG 引导强度")
    output_format: OutputFormat = Field(default=OutputFormat.FBX, description="输出格式")


# ============ 响应模型 ============

class TaskCreateResponse(BaseModel):
    """创建任务的响应"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime


class TaskResult(BaseModel):
    """任务结果"""
    output_file: str | None = None
    fbx_files: list[str] | None = None
    html_content: str | None = None
    message: str | None = None


class TaskDetailResponse(BaseModel):
    """任务详情响应"""
    task_id: str
    status: TaskStatus
    text: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    result: TaskResult | None = None
    error: str | None = None


class QueueStatsResponse(BaseModel):
    """队列统计响应"""
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    gpu_available: bool = False
    model_loaded: bool = False


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str
