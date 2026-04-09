"""队列路由"""
from fastapi import APIRouter, Depends

from ..core.auth import auth_dependency
from ..core.queue import get_queue
from ..schemas.task import QueueStatsResponse

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("", response_model=QueueStatsResponse)
async def get_queue_stats(_: str = Depends(auth_dependency)):
    """获取队列统计信息"""
    queue = get_queue()
    stats = queue.get_queue_stats()
    return QueueStatsResponse(**stats)
