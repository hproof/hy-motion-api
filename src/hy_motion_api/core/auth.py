"""认证模块

基于 X-Id + X-Token 的简单认证。
"""
from fastapi import HTTPException, Header

from .config import get_credentials


def verify_token(x_id: str | None, x_token: str | None) -> str:
    """验证凭证

    Args:
        x_id: X-Id header
        x_token: X-Token header

    Returns:
        str: 验证通过的用户 ID

    Raises:
        HTTPException: 凭证无效时
    """
    if not x_id or not x_token:
        raise HTTPException(status_code=401, detail="Missing X-Id or X-Token header")

    credentials = get_credentials()
    expected_token = credentials.get(x_id)

    if expected_token is None or expected_token != x_token:
        raise HTTPException(status_code=401, detail="Invalid credentials")


async def auth_dependency(x_id: str | None = Header(None), x_token: str | None = Header(None)) -> str:
    """FastAPI 依赖项，用于需要认证的路由"""
    verify_token(x_id, x_token)
    return x_id
