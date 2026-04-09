"""任务相关的 Pydantic 模型"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def to_iso(dt: datetime) -> str:
    """将 datetime 转为 ISO 格式字符串，确保包含时区信息"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


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
    seeds: list[int] | None = Field(default=None, max_length=10, description="随机种子列表，不提供则自动生成")
    cfg_scale: float = Field(default=5.0, ge=1.0, le=20.0, description="CFG 引导强度")
    output_format: OutputFormat = Field(default=OutputFormat.FBX, description="输出格式")


# ============ 响应模型 ============

class TaskCreateResponse(BaseModel):
    """创建任务的响应"""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime

    @field_serializer('created_at')
    def serialize_created_at(self, dt: datetime) -> str:
        return to_iso(dt)


class TaskResult(BaseModel):
    """任务结果"""
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

    @field_serializer('created_at', 'updated_at', 'completed_at')
    def serialize_dates(self, dt: datetime | None) -> str | None:
        return to_iso(dt) if dt else None


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
