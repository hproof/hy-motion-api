# HY-Motion API

HTTP API 服务，基于 [HY-Motion-1.0](https://github.com/Tencent-Hunyuan/HY-Motion-1.0) 提供文本生成 3D 人体动作的 RESTful 接口。

## 功能特性

- **文本生成动作**：通过 HTTP API 调用 HY-Motion-1.0 模型
- **Token 认证**：安全的 API 访问控制
- **任务队列**：异步任务提交和状态查询
- **文件下载**：直接获取生成的 FBX 文件

## 快速开始

### 1. 配置

```bash
cp config.example.toml config.toml
# 编辑 config.toml，配置 HY-Motion-1.0 路径和认证
```

开发环境如果没有 GPU，可在 `config.toml` 的 `[server]` 中设置 `test_mode = true`，此时不执行真实推理，固定等待 3 秒模拟 LLM 调用，其它流程照常执行。

### 2. 安装依赖

```bash
./hy-motion.sh install
```

依赖会安装到 HY-Motion-1.0 的 `venv` 虚拟环境中。

### 3. 启动服务

```bash
./hy-motion.sh start
```

Windows:
```powershell
.\hy-motion.ps1 start
```

### 运行注意

- 当前后台 worker 未做跨进程互斥控制，请不要使用多进程模式启动（例如 `uvicorn --workers >1` 或 Gunicorn 多 worker）。多进程会导致多个 worker 并行领取不同任务，违反 GPU 独占/串行处理要求，可能触发并发 GPU 使用或 OOM。

### 4. 验证

```bash
curl http://localhost:8000/health
```

## API 文档

详细 API 接口说明请查看 [docs/api.md](docs/api.md)。

## 项目结构

```
hy-motion-api/
├── src/hy_motion_api/     # 主包
├── data/                   # 数据目录
├── docs/                   # 文档
├── config.example.toml     # 配置模板
├── hy-motion.sh            # 服务管理脚本 (Linux)
├── hy-motion.bat           # 服务管理脚本 (Windows)
└── requirements.txt
```

## 服务管理

```bash
./hy-motion.sh start     # 启动
./hy-motion.sh stop      # 停止
./hy-motion.sh restart  # 重启
./hy-motion.sh reload   # 重载配置
./hy-motion.sh status   # 查看状态
./hy-motion.sh logs    # 查看日志 (Linux)
```

### 开机自启

```bash
# Linux (systemd)
sudo ./hy-motion.sh enable
```

Windows:
```powershell
.\hy-motion.ps1 enable
```

## 安全建议

- API 通过 Token 认证，生产环境请使用 HTTPS 传输
- 建议在防火墙层配置 IP 白名单
- Token 泄露后请及时更新 `config.toml`

## 许可

MIT License
