# AlphaFold 3 推理服务 API 接口文档

## 基本信息

| 字段 | 值 |
|---|---|
| 服务地址 | `http://<host>:8015` |
| API 前缀 | `/api/v1` |
| 协议 | HTTP |
| 数据格式 | JSON |
| 交互式文档 | `http://<host>:8015/docs`（Swagger UI） |

---

## 接口总览

| 方法 | 路径 | 说明 | 章节 |
|------|------|------|------|
| GET | `/health` | 健康检查 | 1 |
| POST | `/api/v1/predict` | 上传 JSON 文件推理 | 2 |
| POST | `/api/v1/predict/dna` | DNA 序列推理（EVO2 专用） | 3 |
| GET | `/api/v1/tasks` | 任务列表（分页） | 4 |
| GET | `/api/v1/tasks/{task_id}` | 任务详情 | 5 |
| GET | `/api/v1/tasks/{task_id}/results` | 推理结果详情 | 6 |
| GET | `/api/v1/tasks/{task_id}/download/{filename}` | 下载结果文件 | 7 |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务 | 8 |
| GET | `/api/v1/stats` | 系统统计 | 9 |

---

## 1. 健康检查

### `GET /health`

检查系统各组件运行状态。

**响应示例（200）**

```json
{
  "status": "healthy",
  "timestamp": "2026-06-25T12:00:00.000000Z",
  "components": {
    "api": {"status": "up"},
    "database": {"status": "up"},
    "storage": {"status": "up"}
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| status | string | `healthy` 或 `degraded` |
| components.api | object | API 服务状态 |
| components.database | object | 数据库连接状态 |
| components.storage | object | 存储目录状态 |

---

## 2. 提交预测任务

### `POST /api/v1/predict`

接收 AlphaFold 3 格式的 JSON 文件，**同步阻塞**执行推理并返回完整结果。无超时限制，客户端需等待推理完成。

**请求**

- Content-Type: `multipart/form-data`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | file | 是 | AlphaFold 3 格式的 JSON 文件（最大 10MB） |

**输入 JSON 格式**

```json
{
  "name": "test_protein",
  "modelSeeds": [42],
  "sequences": [
    {
      "protein": {
        "id": "A",
        "sequence": "MAKGTR..."
      }
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | string | 是 | 任务名称 |
| modelSeeds | int[] | 是 | 随机种子列表 |
| sequences | object[] | 是 | 序列定义列表，每个包含 protein/rna/dna/ligand 之一 |
| dialect | string | 否 | 固定值 `"alphafold3"` |

**响应示例（200）**

```json
{
  "id": "32513492-f47a-48c9-bf3b-353d87a5da6a",
  "name": "test_protein",
  "status": "completed",
  "created_at": "2026-06-25T12:10:55.445662Z",
  "completed_at": "2026-06-25T12:12:57.261029Z",
  "best_ptm": 0.35,
  "best_iptm": null,
  "ranking_score": 0.8508,
  "error_message": null,
  "predictions": [
    {
      "id": 1,
      "seed": 42,
      "sample_idx": 0,
      "cif_url": "/app/storage/outputs/.../test_protein_seed-42_sample-0_model.cif",
      "confidences_url": "/app/storage/outputs/.../test_protein_seed-42_sample-0_confidences.json",
      "summary_url": "/app/storage/outputs/.../test_protein_seed-42_sample-0_summary_confidences.json",
      "ranking_score": 0.8238,
      "ptm": null,
      "iptm": null
    }
  ]
}
```

**响应字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | 任务 UUID |
| name | string | 任务名称 |
| status | string | `completed` 或 `failed` |
| created_at | datetime | 创建时间 |
| completed_at | datetime | 完成时间 |
| best_ptm | float \| null | 最佳预测 pTM 分数（0-1） |
| best_iptm | float \| null | 最佳预测 ipTM 分数（0-1） |
| ranking_score | float \| null | 最佳预测排名分数（0-1） |
| error_message | string \| null | 失败时的错误信息 |
| predictions | array | 所有预测结果列表 |

**predictions 字段说明**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 预测记录 ID |
| seed | int | 随机种子 |
| sample_idx | int | 样本索引 |
| cif_url | string \| null | CIF 结构文件路径 |
| confidences_url | string \| null | 置信度 JSON 文件路径 |
| summary_url | string \| null | 置信度摘要 JSON 文件路径 |
| ranking_score | float \| null | 排名分数（0-1） |
| ptm | float \| null | pTM 分数 |
| iptm | float \| null | ipTM 分数 |

**错误响应**

| 状态码 | code | 说明 |
|---|---|---|
| 400 | INVALID_JSON | 文件不是有效 JSON |
| 400 | INVALID_INPUT | JSON 格式不符合 AlphaFold 3 规范 |
| 413 | FILE_TOO_LARGE | 文件超过 10MB |
| 500 | INFERENCE_FAILED | 推理执行失败 |

---

## 3. DNA 结构预测（EVO2 输出专用）

### `POST /api/v1/predict/dna`

接收 EVO2 生成的 DNA 序列，自动生成反向互补链（B 链），构建双链 DNA 输入 JSON 并执行结构预测推理。适用于前端先调用 EVO2 生成序列、再调用此接口完成结构预测的场景。

**请求**

```json
{
  "sequence": "ATCGATCGATCGATCGATCG",
  "name": "dna_evo2_prediction",
  "modelSeeds": [42]
}
```

**请求参数**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| sequence | string | 是 | DNA 正向链序列（5'→3'），仅包含 A/T/C/G，最大 10000 字符。反向互补链自动生成 |
| name | string | 否 | 任务名称，不填则自动生成 `dna_evo2_{随机ID}` |
| modelSeeds | array[int] | 否 | 随机种子列表，默认 `[42]` |

**响应**

与 `POST /api/v1/predict` 相同的 `TaskDetail` 格式。

**cURL 示例**

```bash
curl -X POST http://localhost:8015/api/v1/predict/dna \
  -H "Content-Type: application/json" \
  -d '{
    "sequence": "ATCGATCGATCGATCGATCGATCGATCG",
    "name": "my_dna_prediction"
  }'
```

**Python 示例**

```python
import requests

resp = requests.post(
    "http://localhost:8015/api/v1/predict/dna",
    json={
        "sequence": "ATCGATCGATCGATCGATCGATCGATCG",
        "name": "my_dna_prediction",
    },
)
print(resp.json())
```

**错误响应**

| 状态码 | code | 说明 |
|---|---|---|
| 400 | INVALID_INPUT | DNA 序列包含非法字符（仅允许 A/T/C/G） |
| 500 | INFERENCE_FAILED | 推理执行失败 |

---

## 4. 获取历史任务列表

### `GET /api/v1/tasks`

分页查询历史任务，按创建时间倒序排列。

**查询参数**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| page | int | 1 | 页码（从 1 开始） |
| page_size | int | 20 | 每页数量（1-100） |

**请求示例**

```
GET /api/v1/tasks?page=1&page_size=10
```

**响应示例（200）**

```json
{
  "items": [
    {
      "id": "32513492-f47a-48c9-bf3b-353d87a5da6a",
      "name": "test_protein",
      "status": "completed",
      "created_at": "2026-06-25T12:10:55.445662Z",
      "completed_at": "2026-06-25T12:12:57.261029Z",
      "best_ptm": 0.35,
      "best_iptm": null,
      "ranking_score": 0.8508
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

---

## 5. 查询任务详情

### `GET /api/v1/tasks/{task_id}`

根据任务 ID 查询完整详情，包含所有预测结果。

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务 UUID |

**响应**：同 [提交预测任务](#2-提交预测任务) 的响应格式。

**错误响应**

| 状态码 | code | 说明 |
|---|---|---|
| 404 | TASK_NOT_FOUND | 任务不存在 |

---

## 6. 获取推理结果详情

### `GET /api/v1/tasks/{task_id}/results`

获取任务的完整推理结果，包含所有预测的排名和置信度指标。

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务 UUID |

**响应**：同 [查询任务详情](#4-查询任务详情)。

---

## 7. 下载结果文件

### `GET /api/v1/tasks/{task_id}/download/{filename}`

下载指定任务的结果文件。

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务 UUID |
| filename | string | 文件名 |

**支持的文件类型**

| 文件名 | Content-Type | 说明 |
|---|---|---|
| `{name}_model.cif` | chemical/x-mmcif | 蛋白质结构文件 |
| `{name}_confidences.json` | application/json | 完整置信度数据 |
| `{name}_summary_confidences.json` | application/json | 置信度摘要 |
| `{name}_data.json` | application/json | 输入数据副本 |
| `{name}_ranking_scores.csv` | text/csv | 排名分数表 |

**请求示例**

```
GET /api/v1/tasks/32513492-.../download/test_protein_model.cif
```

**响应**：文件下载（FileResponse）。

**错误响应**

| 状态码 | code | 说明 |
|---|---|---|
| 400 | INVALID_INPUT | 文件名包含非法路径字符 |
| 404 | TASK_NOT_FOUND | 任务不存在 |
| 404 | FILE_NOT_FOUND | 文件不存在 |

---

## 8. 删除任务

### `DELETE /api/v1/tasks/{task_id}`

删除指定任务及其所有结果文件和数据库记录。

**路径参数**

| 参数 | 类型 | 说明 |
|---|---|---|
| task_id | string | 任务 UUID |

**响应示例（200）**

```json
{
  "message": "任务已删除",
  "task_id": "32513492-f47a-48c9-bf3b-353d87a5da6a"
}
```

**错误响应**

| 状态码 | code | 说明 |
|---|---|---|
| 404 | TASK_NOT_FOUND | 任务不存在 |

---

## 9. 获取系统统计信息

### `GET /api/v1/stats`

获取系统运行统计。

**响应示例（200）**

```json
{
  "tasks": {
    "total": 10,
    "completed": 8,
    "failed": 2
  }
}
```

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "error": {
    "code": "INVALID_JSON",
    "message": "输入文件不是有效的 JSON 格式",
    "details": "Expecting value: line 1 column 1 (char 0)"
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| error.code | string | 机器可读的错误码 |
| error.message | string | 人类可读的错误信息 |
| error.details | string \| null | 附加错误上下文 |

---

## 使用示例

### cURL

```bash
# 提交预测任务
curl -X POST http://localhost:8015/api/v1/predict \
  -F "file=@input.json"

# 查询任务列表
curl http://localhost:8015/api/v1/tasks?page=1&page_size=10

# 查询任务详情
curl http://localhost:8015/api/v1/tasks/{task_id}

# 下载结构文件
curl -O http://localhost:8015/api/v1/tasks/{task_id}/download/test_protein_model.cif

# 删除任务
curl -X DELETE http://localhost:8015/api/v1/tasks/{task_id}

# 系统统计
curl http://localhost:8015/api/v1/stats

# 健康检查
curl http://localhost:8015/health
```

### Python

```python
import requests

# 提交预测
with open("input.json", "rb") as f:
    resp = requests.post(
        "http://localhost:8015/api/v1/predict",
        files={"file": ("input.json", f, "application/json")},
    )
result = resp.json()
print(f"Status: {result['status']}, Score: {result['ranking_score']}")

# 查询列表
resp = requests.get("http://localhost:8015/api/v1/tasks", params={"page": 1})
tasks = resp.json()
```
