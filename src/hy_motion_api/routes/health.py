"""健康检查路由"""
import torch

from fastapi import APIRouter

from ..core.runtime import is_gpu_available, is_model_loaded
from ..schemas.task import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        gpu_available=is_gpu_available(),
        model_loaded=is_model_loaded(),
    )
