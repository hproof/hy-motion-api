# API 文档

## 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://{host}:8000` |
| Content-Type | `application/json` |
| 认证方式 | Token (Header) |

## 认证

所有业务接口均需携带认证 Header：

| Header | 说明 |
|--------|------|
| `X-Id` | 用户标识 |
| `X-Token` | 用户令牌 |

凭证在 `config.toml` 的 `[auth]` 节中配置，支持热更新。

---

## 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/tasks` | 提交任务 |
| `GET` | `/tasks/{task_id}` | 查询任务 |
| `GET` | `/queue` | 队列统计 |
| `GET` | `/download/{task_id}` | 下载结果 |

---

## 健康检查

### `GET /health`

检查服务健康状态。

**认证**: 不需要

**响应**:

```json
{
  "status": "healthy",
  "gpu_available": true,
  "model_loaded": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `"healthy"` 或 `"unhealthy"` |
| `gpu_available` | boolean | GPU 是否可用 |
| `model_loaded` | boolean | 模型是否已加载 |

---

## 提交任务

### `POST /tasks`

提交一个新的动作生成任务。

**认证**: 需要

**请求体**:

```json
{
  "text": "A person walks forward.",
  "duration": 5.0,
  "seeds": [42],
  "cfg_scale": 5.0,
  "output_format": "fbx"
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 动作描述文本（英文），建议 60 词以内 |
| `duration` | float | 否 | `5.0` | 动作时长（秒），有效范围 `0.5 ~ 12.0` |
| `seeds` | array[int] | 否 | `null` | 随机种子列表，不提供则自动生成一个随机种子 |
| `cfg_scale` | float | 否 | `5.0` | CFG 引导强度，范围 `1.0 ~ 20.0` |
| `output_format` | string | 否 | `"fbx"` | 输出格式：`"fbx"` 或 `"dict"` |

**响应** (202 Accepted):

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2026-04-09T10:00:00Z"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务唯一标识符 (UUID) |
| `status` | string | 任务状态，始终为 `"pending"` |
| `created_at` | string | ISO 8601 时间戳 |

**错误响应**:

| 状态码 | 说明 |
|--------|------|
| `401` | 认证失败 |
| `422` | 请求参数校验失败 |

---

## 查询任务

### `GET /tasks/{task_id}`

查询任务状态和结果。

**认证**: 需要

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID (UUID) |

**响应**:

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "text": "A person walks forward.",
  "created_at": "2026-04-09T10:00:00Z",
  "updated_at": "2026-04-09T10:00:15Z",
  "completed_at": "2026-04-09T10:00:15Z",
  "result": {
    "fbx_files": [
      "output/api/20260409_100000123_abc_000.fbx",
      "output/api/20260409_100000123_abc_001.fbx",
      "output/api/20260409_100000123_abc_002.fbx",
      "output/api/20260409_100000123_abc_003.fbx"
    ]
  },
  "error": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |
| `status` | string | 任务状态：`pending` \| `running` \| `completed` \| `failed` |
| `text` | string | 原始输入文本 |
| `created_at` | string | 任务创建时间 |
| `updated_at` | string | 最后更新时间 |
| `completed_at` | string | 任务完成时间（仅 completed 时有值） |
| `result.fbx_files` | array[string] | 所有版本的 FBX 文件路径列表 |
| `result.html_content` | string | HTML 可视化内容（仅 dict 格式有值） |
| `error` | string | 错误信息（仅 failed 时有值） |

**错误响应**:

| 状态码 | 说明 |
|--------|------|
| `401` | 认证失败 |
| `404` | 任务不存在 |

---

## 队列统计

### `GET /queue`

查询当前队列状态统计。

**认证**: 需要

**响应**:

```json
{
  "pending": 5,
  "running": 1,
  "completed": 10,
  "failed": 2
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `pending` | int | 等待执行的任务数 |
| `running` | int | 正在执行的任务数 |
| `completed` | int | 已完成的任务数 |
| `failed` | int | 失败的任务数 |

---

## 下载结果

### `GET /download/{task_id}`

下载任务生成的 FBX 文件或 HTML 内容。

**认证**: 需要

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID (UUID) |

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `version` | int | `0` | FBX 版本号（0 ~ 3），对应不同随机种子生成的结果 |
| `format` | string | `"fbx"` | 下载格式：`"fbx"` 或 `"dict"` |

**响应**:

- `format=fbx`: 文件二进制流，Content-Type 为 `application/octet-stream`
- `format=dict`: HTML 内容，Content-Type 为 `text/html`

**错误响应**:

| 状态码 | 说明 |
|--------|------|
| `401` | 认证失败 |
| `404` | 任务不存在或文件不存在 |
| `400` | 任务未完成 |

---

## 调用示例

### cURL

```bash
# 健康检查
curl http://localhost:8000/health

# 提交任务
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -H "X-Id: user1" \
  -H "X-Token: token1" \
  -d '{"text": "A person walks forward.", "duration": 5.0}'

# 查询任务状态
curl http://localhost:8000/tasks/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-Id: user1" \
  -H "X-Token: token1"

# 下载结果 (FBX)
curl -O -J http://localhost:8000/download/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-Id: user1" \
  -H "X-Token: token1"

# 下载结果 (HTML/dict)
curl http://localhost:8000/download/550e8400-e29b-41d4-a716-446655440000?format=dict \
  -H "X-Id: user1" \
  -H "X-Token: token1"

# 查询队列统计
curl http://localhost:8000/queue \
  -H "X-Id: user1" \
  -H "X-Token: token1"

# 下载指定版本（version=1）
curl -O -J "http://localhost:8000/download/550e8400-e29b-41d4-a716-446655440000?version=1" \
  -H "X-Id: user1" \
  -H "X-Token: token1"
```

### Python

```python
import requests

BASE_URL = "http://localhost:8000"
HEADERS = {
    "X-Id": "user1",
    "X-Token": "token1"
}

# 提交任务（不提供 seeds 则自动生成随机种子）
def create_task(text: str, duration: float = 5.0, seeds: list = None):
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={
            "text": text,
            "duration": duration,
            "seeds": seeds,
            "cfg_scale": 5.0,
            "output_format": "fbx"
        },
        headers=HEADERS
    )
    response.raise_for_status()
    return response.json()

# 查询任务
def get_task(task_id: str):
    response = requests.get(
        f"{BASE_URL}/tasks/{task_id}",
        headers=HEADERS
    )
    response.raise_for_status()
    return response.json()

# 下载文件
def download_file(task_id: str, format: str = "fbx", version: int = 0):
    response = requests.get(
        f"{BASE_URL}/download/{task_id}",
        params={"format": format, "version": version},
        headers=HEADERS,
        stream=True
    )
    response.raise_for_status()

    filename = response.headers.get("content-disposition", "").split("filename=")[-1]
    with open(filename, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return filename
```

---

## 任务生命周期

```
┌─────────┐
│ pending │
└────┬────┘
     │ 任务被调度
     ▼
┌─────────┐
│ running │
└────┬────┘
     │ 成功
     ▼
┌───────────┐
│ completed │───► 可下载结果
└───────────┘

     │ 失败
     ▼
┌─────────┐
│  failed │
└─────────┘
```

---

## 注意事项

1. **GPU 独占**: GPU 推理期间同一时间只能处理一个任务
2. **队列顺序**: 任务按提交顺序执行
3. **文件清理**: 服务不自动清理历史输出文件，请定期清理 `output/gradio` 目录
4. **Prompt Engineering**: 默认禁用（节省显存），启用需部署 vLLM 服务并修改配置
