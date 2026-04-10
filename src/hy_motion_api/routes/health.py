"""健康检查路由"""
import torch

from fastapi import APIRouter

from ..core.config import get_settings
from ..core.runtime import is_gpu_available, is_model_loaded
from ..schemas.task import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    if get_settings().test_mode:
        return HealthResponse(
            status="healthy",
            gpu_available=False,
            model_loaded=False,
        )
    return HealthResponse(
        status="healthy",
        gpu_available=is_gpu_available(),
        model_loaded=is_model_loaded(),
    )
