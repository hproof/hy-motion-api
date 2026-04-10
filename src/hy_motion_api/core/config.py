"""配置管理模块

从 config.toml 读取所有配置。
"""
import os
import sys
from pathlib import Path
from functools import lru_cache

# Python 3.11+ 内置 tomllib，否则使用 tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class Settings:
    """应用配置"""

    def __init__(self, config: dict):
        # 服务器配置
        self.host = config.get("server", {}).get("host", "0.0.0.0")
        self.port = config.get("server", {}).get("port", 8000)
        self.log_level = config.get("server", {}).get("log_level", "info")
        self.test_mode = config.get("server", {}).get("test_mode", False)

        # HY-Motion 配置
        hy_motion = config.get("hy_motion", {})
        self.hy_motion_path = str(Path(hy_motion.get("path", "G:/git_proj/HY-Motion-1.0")).expanduser())
        self.model_config_path = hy_motion.get("config_path", "ckpts/tencent/HY-Motion-1.0/config.yml")
        self.model_ckpt_name = hy_motion.get("checkpoint_name", "latest.ckpt")
        self.output_dir = hy_motion.get("output_dir", "output/gradio")
        self.disable_prompt_engineering = hy_motion.get("disable_prompt_engineering", True)

        # 认证配置
        self.auth = config.get("auth", {})

        # 队列数据库路径（固定在 data 目录下）
        self.queue_path = "data/queue.db"

        # 数据保留天数（默认 7 天）
        self.retention_days = config.get("server", {}).get("retention_days", 7)


def _find_config_file() -> Path:
    """查找配置文件"""
    # 优先查找项目根目录
    current = Path(__file__).resolve()
    # src/hy_motion_api/core/config.py -> src/hy_motion_api -> src -> 项目根目录
    project_root = current.parent.parent.parent

    config_path = project_root / "config.toml"
    if config_path.exists():
        return config_path

    # 回退到当前目录
    return Path("config.toml")


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    config_path = _find_config_file()

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    return Settings(config)


def get_credentials() -> dict[str, str]:
    """获取凭证字典，每次调用重新读取（支持热更新）

    Returns:
        dict: {id: token}
    """
    settings = get_settings()
    return settings.auth
