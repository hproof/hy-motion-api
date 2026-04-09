"""T2MRuntime 单例模块"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

# 确保 HY-Motion-1.0 在 Python 路径中
_current_file = Path(__file__).resolve()
# src/hy_motion_api/core/runtime.py -> src/hy_motion_api -> src -> 项目根目录
_project_root = _current_file.parent.parent.parent

_runtime: T2MRuntime | None = None


def get_runtime() -> T2MRuntime:
    """获取 T2MRuntime 全局单例"""
    global _runtime

    if _runtime is None:
        from .config import get_settings

        settings = get_settings()
        hy_motion_path = settings.hy_motion_path

        # 添加到 Python 路径
        if hy_motion_path not in sys.path:
            sys.path.insert(0, hy_motion_path)

        # 导入 T2MRuntime
        from hymotion.utils.t2m_runtime import T2MRuntime  # noqa: F401

        # 构建 config 路径
        config_path = str(Path(hy_motion_path) / settings.model_config_path)
        # 构建 checkpoint 完整路径（避免相对路径导致找不到文件）
        ckpt_dir = Path(config_path).parent
        ckpt_name = str(ckpt_dir / settings.model_ckpt_name)

        # 确保输出目录存在
        output_dir = Path(hy_motion_path) / settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        _runtime = T2MRuntime(
            config_path=config_path,
            ckpt_name=ckpt_name,
            disable_prompt_engineering=settings.disable_prompt_engineering,
            device_ids=list(range(torch.cuda.device_count()) if torch.cuda.is_available() else []),
        )

    return _runtime


def is_gpu_available() -> bool:
    """检查 GPU 是否可用"""
    return torch.cuda.is_available()


def is_model_loaded() -> bool:
    """检查模型是否已加载"""
    global _runtime
    return _runtime is not None and _runtime._loaded
