# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

hy-motion-api 是 HY-Motion-1.0 的 HTTP API 封装项目，提供 RESTful 接口访问 HY-Motion-1.0 的文本生成动作功能。

## 目录结构

```
hy-motion-api/
├── src/
│   └── hy_motion_api/       # 主包
│       ├── main.py          # FastAPI 应用
│       ├── core/            # 核心模块
│       │   ├── config.py    # 配置管理 (config.toml)
│       │   ├── auth.py      # Token 认证
│       │   ├── runtime.py   # T2MRuntime 单例
│       │   └── queue.py     # 任务队列
│       ├── routes/          # API 路由
│       └── schemas/         # Pydantic 模型
├── data/                    # 数据目录
│   └── queue.db             # SQLite 任务队列
├── config.toml              # 配置文件
├── docs/                    # 文档
└── pyproject.toml
```

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（无需额外参数）
uvicorn src.hy_motion_api.main:app

# 开发模式（热重载）
uvicorn src.hy_motion_api.main:app --reload

# 健康检查
curl http://localhost:8000/health
```

## 配置说明

所有配置集中在 `config.toml`：

```toml
# 服务配置
[server]
host = "0.0.0.0"
port = 8000

# HY-Motion-1.0 路径配置
[hy_motion]
path = "G:/git_proj/HY-Motion-1.0"
config_path = "ckpts/tencent/HY-Motion-1.0/config.yml"
checkpoint_name = "latest.ckpt"

# 认证配置
[auth]
user1 = "token1"
user2 = "token2"
```

## 架构

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/tasks` | 提交任务 |
| `GET` | `/tasks/{task_id}` | 查询任务 |
| `GET` | `/queue` | 队列统计 |
| `GET` | `/download/{task_id}` | 下载结果 |

### 认证方式

所有业务接口需要 Header：
- `X-Id`: 用户标识
- `X-Token`: 用户令牌

凭证配置在 `config.toml` 的 `[auth]` 节，支持热更新（重启后生效）。

### T2MRuntime 集成

- HY-Motion-1.0 作为独立依赖安装
- 通过 `config.toml` 的 `hy_motion.path` 指定路径
- `src/hy_motion_api/core/runtime.py` 负责 T2MRuntime 单例管理
- `generate_motion()` 是核心调用接口

### 任务队列

- 基于 `data/queue.db` (SQLite)
- 后台 worker 串行处理，任务领取使用原子 claim
- 状态：`pending` → `running` → `completed` / `failed`

## 开发注意事项

1. **配置文件**: `config.toml` 包含敏感信息，不应提交到 Git
2. **队列文件**: `data/queue.db*` 不应提交到 Git
3. **PYTHONPATH**: 生产部署需设置 `PYTHONPATH` 指向 HY-Motion-1.0 目录
4. **GPU 独占**: GPU 推理同时只能处理一个任务
