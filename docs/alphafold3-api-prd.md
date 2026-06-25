# AlphaFold 3 推理服务 API 产品需求文档 (PRD)

## 文档信息

| 字段 | 内容 |
|------|------|
| 项目名称 | AlphaFold 3 推理服务 API |
| 文档版本 | v3.0 |
| 创建日期 | 2026-06-25 |
| 最后更新 | 2026-06-25 |
| 负责人 | lvyizhuo |
| 所属项目 | 农业大模型智能体二期 - 组学智能体能力开发 |

---

## 1. 项目背景

### 1.1 业务背景

农业大模型智能体二期项目需要集成组学分析能力，其中蛋白质结构预测是核心功能之一。AlphaFold 3 是 Google DeepMind 开发的生物分子结构预测模型，能够预测蛋白质、RNA、DNA、配体及其复合物的三维结构。

### 1.2 当前状态

- AlphaFold 3 模型代码仓库已完成部署
- 模型推理所需的数据库和权重文件已下载，路径：`/data2/ntt/lvyizhuo/alphafold3/`
- Docker 镜像已在服务器上构建完成
- 模型已成功运行，验证通过
- 模型仅支持通过命令行调用，输入为 JSON 文件，输出为多个结果文件

### 1.3 问题与挑战

- 模型仅提供命令行接口，无法直接被前端或智能体调用
- 推理过程耗时较长（取决于序列长度），需要异步处理
- 输出结果包含多个文件，需要结构化处理以便前端渲染
- 需要任务状态管理和历史结果存储

---

## 2. 项目目标

### 2.1 核心目标

将 AlphaFold 3 模型的推理能力封装为标准 RESTful API 服务，支持：

1. 前端界面上传单个 JSON 文件并提交预测任务
2. 后台异步执行推理任务（单卡阻塞模式）
3. 保存历史计算结果，支持查询、预览和下载
4. 自动清理过期数据（30 天）

### 2.2 项目范围

**在范围内：**
- 单文件上传推理接口
- 任务状态查询接口
- 历史结果查询和下载接口
- 结果数据解析（置信度指标提取）
- 自动数据清理

**不在范围内：**
- 批量上传功能（后续版本考虑）
- 前端界面开发
- 用户认证系统
- 分布式部署

### 2.3 成功指标

| 指标 | 目标值 |
|------|--------|
| API 响应时间（提交任务） | < 500ms |
| 任务状态查询响应时间 | < 100ms |
| 推理任务成功率 | > 95% |
| 系统可用性 | > 99% |

---

## 3. 用户角色与场景

### 3.1 用户角色

| 角色 | 描述 | 主要操作 |
|------|------|----------|
| 前端用户 | 通过 Web 界面使用服务 | 上传 JSON、查看任务状态、下载结果 |
| 智能体 | 农业大模型智能体 | 程序化调用 API 进行结构预测 |

### 3.2 核心用户场景

#### 场景 1：提交预测任务

```
用户 -> 前端界面 -> 上传单个 AlphaFold 3 格式的 JSON 文件
                  -> 提交预测任务
                  -> 获得任务 ID
```

#### 场景 2：查询任务状态

```
用户 -> 前端界面 -> 输入任务 ID 或从历史列表选择
                  -> 查看任务状态（pending/running/completed/failed）
                  -> 查看推理进度（如有）
```

#### 场景 3：查看和下载结果

```
用户 -> 前端界面 -> 任务完成后进入结果页面
                  -> 查看置信度摘要（pTM、ipTM、ranking_score）
                  -> 预览结构数据
                  -> 下载 CIF 结构文件
                  -> 下载完整结果包（ZIP）
```

#### 场景 4：智能体集成调用

```
智能体 -> 调用 POST /api/v1/predict 提交任务
        -> 轮询 GET /api/v1/tasks/{task_id} 等待完成
        -> 调用 GET /api/v1/tasks/{task_id}/results 获取结构化结果
        -> 将结果整合到智能体工作流中
```

---

## 4. 功能需求

### 4.1 任务提交模块

#### 4.1.1 提交预测任务

**功能描述**：接收用户上传的单个 AlphaFold 3 输入 JSON 文件，创建预测任务

**接口**：`POST /api/v1/predict`

**输入参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | AlphaFold 3 格式的 JSON 文件 |

**输出**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "position_in_queue": 3,
  "created_at": "2026-06-25T10:00:00Z",
  "message": "任务已提交，当前队列位置：3"
}
```

**业务规则**：
- 每次只接收单个 JSON 文件
- 验证输入 JSON 格式是否符合 AlphaFold 3 规范
- 检查 JSON 中的 `dialect` 字段必须为 `alphafold3`
- 检查 `sequences` 字段不为空
- 单个 JSON 文件大小不超过 10MB
- 任务按照 FIFO 顺序排队处理

**任务状态枚举**：

| 状态 | 说明 |
|------|------|
| pending | 等待处理（在队列中） |
| running | 正在运行 |
| completed | 已完成 |
| failed | 失败 |

### 4.2 任务查询模块

#### 4.2.1 查询任务状态

**功能描述**：根据任务 ID 查询任务当前状态和进度

**接口**：`GET /api/v1/tasks/{task_id}`

**输出**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "job_name": "test_protein",
  "created_at": "2026-06-25T02:50:00Z",
  "started_at": "2026-06-25T02:50:05Z",
  "completed_at": "2026-06-25T02:51:32Z",
  "duration_seconds": 87,
  "position_in_queue": null,
  "input_summary": {
    "name": "test_protein",
    "sequences": [
      {
        "type": "protein",
        "id": "A",
        "length": 200
      }
    ],
    "num_seeds": 1,
    "num_samples": 5
  },
  "error_message": null
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | String | 任务唯一标识 |
| status | String | 任务状态 |
| job_name | String | 任务名称（来自 JSON 的 name 字段） |
| created_at | DateTime | 任务创建时间 |
| started_at | DateTime | 任务开始执行时间 |
| completed_at | DateTime | 任务完成时间 |
| duration_seconds | Integer | 推理耗时（秒） |
| position_in_queue | Integer | 队列位置（仅 pending 状态有值） |
| input_summary | Object | 输入摘要信息 |
| error_message | String | 错误信息（仅 failed 状态有值） |

#### 4.2.2 获取任务列表

**功能描述**：获取历史任务列表，支持分页和筛选

**接口**：`GET /api/v1/tasks`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | Integer | 否 | 页码（默认 1） |
| page_size | Integer | 否 | 每页数量（默认 20，最大 100） |
| status | String | 否 | 按状态筛选 |

**输出**：

```json
{
  "items": [
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "job_name": "test_protein",
      "created_at": "2026-06-25T02:50:00Z",
      "completed_at": "2026-06-25T02:51:32Z",
      "duration_seconds": 87,
      "best_ranking_score": 0.85
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

#### 4.2.3 取消任务

**功能描述**：取消正在等待的任务

**接口**：`DELETE /api/v1/tasks/{task_id}`

**业务规则**：
- 只能取消 `pending` 状态的任务
- `running` 状态的任务不支持取消（单卡阻塞模式）
- `completed` 和 `failed` 状态的任务不支持取消

**输出**：

```json
{
  "message": "任务已取消",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 4.3 结果查询模块

#### 4.3.1 获取推理结果摘要

**功能描述**：以 JSON 格式返回推理结果的摘要信息，包含所有预测的排名和置信度指标

**接口**：`GET /api/v1/tasks/{task_id}/results`

**输出**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_name": "test_protein",
  "status": "completed",
  "best_prediction": {
    "seed": 42,
    "sample": 0,
    "ranking_score": 0.85,
    "ptm": 0.75,
    "iptm": 0.82,
    "fraction_disordered": 0.05,
    "has_clash": false,
    "chain_ptm": [0.78],
    "chain_iptm": [0.81],
    "chain_pair_iptm": [[0.78]],
    "chain_pair_pae_min": [[0.5]]
  },
  "all_predictions": [
    {
      "seed": 42,
      "sample": 0,
      "ranking_score": 0.85,
      "ptm": 0.75,
      "iptm": 0.82
    },
    {
      "seed": 42,
      "sample": 1,
      "ranking_score": 0.82,
      "ptm": 0.73,
      "iptm": 0.80
    },
    {
      "seed": 42,
      "sample": 2,
      "ranking_score": 0.79,
      "ptm": 0.71,
      "iptm": 0.78
    },
    {
      "seed": 42,
      "sample": 3,
      "ranking_score": 0.76,
      "ptm": 0.69,
      "iptm": 0.75
    },
    {
      "seed": 42,
      "sample": 4,
      "ranking_score": 0.73,
      "ptm": 0.67,
      "iptm": 0.72
    }
  ],
  "files": {
    "best_model_cif": "/api/v1/tasks/{task_id}/files/model.cif",
    "data_json": "/api/v1/tasks/{task_id}/files/data.json",
    "ranking_scores_csv": "/api/v1/tasks/{task_id}/files/ranking_scores.csv"
  }
}
```

#### 4.3.2 获取单个预测的详细置信度

**功能描述**：获取指定 seed 和 sample 的详细置信度数据

**接口**：`GET /api/v1/tasks/{task_id}/results/confidences`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| seed | Integer | 是 | 随机种子 |
| sample | Integer | 是 | 采样索引 |

**输出**：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "seed": 42,
  "sample": 0,
  "summary": {
    "ptm": 0.75,
    "iptm": 0.82,
    "fraction_disordered": 0.05,
    "has_clash": false,
    "ranking_score": 0.85,
    "chain_ptm": [0.78],
    "chain_iptm": [0.81],
    "chain_pair_iptm": [[0.78]],
    "chain_pair_pae_min": [[0.5]]
  },
  "details": {
    "atom_plddts": [90.5, 85.2, 78.9],
    "token_chain_ids": ["A", "A", "A"],
    "atom_chain_ids": ["A", "A", "A"],
    "contact_probs": [[1.0, 0.8, 0.5], [0.8, 1.0, 0.6], [0.5, 0.6, 1.0]]
  },
  "pae": [[0.1, 0.2, 0.3], [0.2, 0.1, 0.4], [0.3, 0.4, 0.1]]
}
```

### 4.4 文件下载模块

#### 4.4.1 下载结果文件

**功能描述**：下载指定的结果文件

**接口**：`GET /api/v1/tasks/{task_id}/files/{filename}`

**支持的文件类型**：

| 文件名 | 说明 | Content-Type |
|--------|------|--------------|
| model.cif | 最佳预测的结构文件 | chemical/x-mmcif |
| confidences.json | 最佳预测的完整置信度数据 | application/json |
| summary_confidences.json | 最佳预测的置信度摘要 | application/json |
| data.json | 输入数据（含 MSA 和模板） | application/json |
| ranking_scores.csv | 所有预测的排名分数 | text/csv |

**响应示例**：

```
HTTP/1.1 200 OK
Content-Type: chemical/x-mmcif
Content-Disposition: attachment; filename="test_protein_model.cif"
Content-Length: 123456

[file content]
```

#### 4.4.2 下载指定预测的文件

**功能描述**：下载指定 seed 和 sample 的结果文件

**接口**：`GET /api/v1/tasks/{task_id}/files/seed-{seed}_sample-{sample}/{filename}`

**示例**：`GET /api/v1/tasks/{task_id}/files/seed-42_sample-0/model.cif`

#### 4.4.3 下载完整结果包

**功能描述**：下载所有结果文件的 ZIP 压缩包

**接口**：`GET /api/v1/tasks/{task_id}/download`

**响应**：

```
HTTP/1.1 200 OK
Content-Type: application/zip
Content-Disposition: attachment; filename="test_protein_results.zip"

[zip content]
```

**ZIP 包结构**：

```
test_protein_results.zip
├── test_protein_model.cif
├── test_protein_confidences.json
├── test_protein_summary_confidences.json
├── test_protein_data.json
├── test_protein_ranking_scores.csv
├── TERMS_OF_USE.md
└── seed-42_sample-0/
    ├── test_protein_seed-42_sample-0_model.cif
    ├── test_protein_seed-42_sample-0_confidences.json
    └── test_protein_seed-42_sample-0_summary_confidences.json
```

### 4.5 系统管理模块

#### 4.5.1 健康检查

**功能描述**：检查系统各组件状态

**接口**：`GET /api/v1/health`

**输出**：

```json
{
  "status": "healthy",
  "timestamp": "2026-06-25T10:00:00Z",
  "components": {
    "api": {"status": "up"},
    "database": {"status": "up"},
    "storage": {"status": "up"},
    "gpu": {"status": "up", "device": "NVIDIA A100"}
  }
}
```

#### 4.5.2 系统统计

**功能描述**：获取系统运行统计信息

**接口**：`GET /api/v1/stats`

**输出**：

```json
{
  "tasks": {
    "total": 100,
    "pending": 2,
    "running": 1,
    "completed": 95,
    "failed": 2
  },
  "queue": {
    "length": 2,
    "current_task_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "storage": {
    "used_bytes": 10737418240,
    "total_bytes": 107374182400,
    "usage_percent": 10.0
  },
  "performance": {
    "avg_inference_time_seconds": 300,
    "success_rate": 0.97
  }
}
```

---

## 5. 非功能需求

### 5.1 性能需求

| 指标 | 要求 |
|------|------|
| API 响应时间（非推理） | < 500ms |
| 任务状态查询响应时间 | < 100ms |
| 文件上传大小限制 | 10MB |
| 文件下载速度 | > 10MB/s |

### 5.2 可靠性需求

| 指标 | 要求 |
|------|------|
| 系统可用性 | > 99% |
| 任务成功率 | > 95% |
| 数据持久性 | 任务完成后数据保留 30 天 |

### 5.3 数据保留策略

- 历史计算结果保留 **30 天**
- 超过 30 天的任务数据自动清理（包括数据库记录和文件）
- 每天凌晨执行一次清理任务
- 清理时同时删除数据库记录和存储文件

### 5.4 并发处理策略

由于模型只能使用单张 GPU 进行推理，采用 **单卡阻塞模式**：

- 同一时间只运行一个推理任务
- 其他任务在队列中等待（FIFO 顺序）
- 前端可以通过轮询获取任务状态更新
- 队列长度无限制，但会在统计接口中展示

### 5.5 日志与监控需求

- 使用 loguru 进行结构化日志记录
- 日志级别：DEBUG、INFO、WARNING、ERROR、CRITICAL
- 记录关键操作：任务创建、开始、完成、失败
- 支持日志轮转（按天轮转，保留 30 天）

---

## 6. 接口设计

### 6.1 API 版本

当前版本：`v1`

基础路径：`/api/v1`

**服务地址**：`http://<server-ip>:8015`

### 6.2 接口汇总

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/predict | 提交预测任务 |
| GET | /api/v1/tasks | 获取任务列表 |
| GET | /api/v1/tasks/{task_id} | 查询任务状态 |
| DELETE | /api/v1/tasks/{task_id} | 取消任务 |
| GET | /api/v1/tasks/{task_id}/results | 获取推理结果摘要 |
| GET | /api/v1/tasks/{task_id}/results/confidences | 获取详细置信度 |
| GET | /api/v1/tasks/{task_id}/files/{filename} | 下载结果文件 |
| GET | /api/v1/tasks/{task_id}/download | 下载完整结果包 |
| GET | /api/v1/health | 健康检查 |
| GET | /api/v1/stats | 系统统计 |

### 6.3 错误码

| HTTP 状态码 | 错误码 | 说明 |
|-------------|--------|------|
| 400 | INVALID_INPUT | 输入格式错误 |
| 400 | INVALID_JSON | JSON 格式不符合 AlphaFold 3 规范 |
| 400 | INVALID_DIALECT | dialect 字段不是 alphafold3 |
| 404 | TASK_NOT_FOUND | 任务不存在 |
| 404 | FILE_NOT_FOUND | 结果文件不存在 |
| 409 | TASK_NOT_CANCELLABLE | 任务状态不支持取消 |
| 413 | FILE_TOO_LARGE | 文件超过 10MB 限制 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |
| 503 | GPU_UNAVAILABLE | GPU 资源不可用 |

错误响应格式：

```json
{
  "error": {
    "code": "INVALID_JSON",
    "message": "输入 JSON 格式不符合 AlphaFold 3 规范",
    "details": "sequences 字段不能为空"
  }
}
```

---

## 7. 数据模型

### 7.1 数据库设计

使用 SQLite 数据库，数据库文件位于容器内 `/app/data/alphafold3.db`，通过挂载持久化到宿主机。

#### tasks 表

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,                    -- UUID
    job_name TEXT NOT NULL,                 -- 任务名称（来自 JSON）
    status TEXT NOT NULL DEFAULT 'pending', -- pending/running/completed/failed
    progress INTEGER DEFAULT 0,            -- 进度 0-100

    -- 输入信息
    input_json TEXT NOT NULL,              -- 原始输入 JSON
    input_summary TEXT,                    -- 输入摘要 (JSON)

    -- 结果信息
    output_path TEXT,                      -- 输出目录路径
    best_seed INTEGER,                     -- 最佳预测的 seed
    best_sample INTEGER,                   -- 最佳预测的 sample
    best_ranking_score REAL,               -- 最佳排名分数

    -- 统计信息
    num_seeds INTEGER,                     -- 种子数量
    num_samples INTEGER,                   -- 每个种子的采样数

    -- 时间信息
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,

    -- 错误信息
    error_message TEXT
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
```

### 7.2 文件存储结构

**容器内路径**：`/app/storage/tasks/{task_id}/`

**宿主机路径**：`/data2/ntt/lvyizhuo/task06-alphafold3-agent/storage/tasks/{task_id}/`

```
storage/
└── tasks/
    └── {task_id}/
        ├── input.json                    # 用户上传的输入文件
        └── output/                       # AlphaFold 输出
            ├── {job_name}_model.cif
            ├── {job_name}_confidences.json
            ├── {job_name}_summary_confidences.json
            ├── {job_name}_data.json
            ├── {job_name}_ranking_scores.csv
            ├── TERMS_OF_USE.md
            └── seed-{seed}_sample-{sample}/
                ├── {job_name}_seed-{seed}_sample-{sample}_model.cif
                ├── {job_name}_seed-{seed}_sample-{sample}_confidences.json
                └── {job_name}_seed-{seed}_sample-{sample}_summary_confidences.json
```

### 7.3 结果解析逻辑

API 需要解析 AlphaFold 3 的输出文件，提取以下信息用于接口返回：

1. **从 `ranking_scores.csv` 解析**：
   - 所有预测的 seed、sample、ranking_score

2. **从 `summary_confidences.json` 解析**：
   - ptm、iptm、fraction_disordered、has_clash
   - chain_ptm、chain_iptm、chain_pair_iptm、chain_pair_pae_min

3. **从 `confidences.json` 解析**：
   - pae 矩阵
   - atom_plddts 数组
   - token_chain_ids、atom_chain_ids
   - contact_probs 矩阵

---

## 8. 技术架构

### 8.1 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| Web 框架 | FastAPI | 高性能异步 Web 框架 |
| 日志 | loguru | 结构化日志库 |
| 数据库 | SQLite | 轻量级关系数据库 |
| 任务队列 | asyncio.Queue | 简单的异步队列 |
| 文件存储 | 本地文件系统 | 宿主机挂载目录 |
| 容器化 | Docker | 部署和运行环境 |
| 序列化 | Pydantic | 数据验证和序列化 |

### 8.2 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker 容器 (端口 8015)                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Application                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │   │
│  │  │  API Router  │  │  Middleware  │  │  Task Worker    │ │   │
│  │  └─────────────┘  └─────────────┘  │  (单线程阻塞)    │ │   │
│  │                                     └─────────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                    │                      │           │
│         ▼                    ▼                      ▼           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐ │
│  │   SQLite     │    │   loguru     │    │  run_alphafold.py │ │
│  │   Database   │    │   Logger     │    │  (模型推理)       │ │
│  └──────────────┘    └──────────────┘    └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
        │                    │                      │
        ▼                    ▼                      ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐
│  宿主机      │    │  宿主机      │    │  宿主机              │
│  data/       │    │  logs/       │    │  alphafold3/         │
│  (数据库)    │    │  (日志)      │    │  (模型+数据库)       │
└──────────────┘    └──────────────┘    └──────────────────────┘
```

### 8.3 核心流程

#### 任务提交流程

```
1. 用户上传 JSON 文件
2. 验证 JSON 格式
3. 保存输入文件到 /app/storage/tasks/{task_id}/input.json
4. 创建数据库记录（status=pending）
5. 将 task_id 加入 asyncio.Queue
6. 返回 task_id 和队列位置
```

#### 任务执行流程

```
1. Worker 从队列取出 task_id
2. 更新数据库状态为 running
3. 调用 run_alphafold.py：
   python run_alphafold.py \
     --json_path=/app/storage/tasks/{task_id}/input.json \
     --model_dir=/root/models \
     --output_dir=/app/storage/tasks/{task_id}/output
4. 等待执行完成
5. 解析输出结果，提取置信度指标
6. 更新数据库（status=completed，结果信息）
7. 继续处理下一个任务
```

#### 结果查询流程

```
1. 前端请求 GET /api/v1/tasks/{task_id}/results
2. 从数据库读取任务信息
3. 如果任务完成，读取输出目录中的文件
4. 解析 ranking_scores.csv 和 summary_confidences.json
5. 构建响应 JSON 返回给前端
```

---

## 9. 部署方案

### 9.1 目录结构

**项目目录**：`/data2/ntt/lvyizhuo/task06-alphafold3-agent/`

```
/data2/ntt/lvyizhuo/task06-alphafold3-agent/
├── api/                              # API 服务代码
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── predict.py       # 预测接口
│   │   │       ├── tasks.py         # 任务接口
│   │   │       └── results.py       # 结果接口
│   │   ├── core/
│   │   │   ├── alphafold.py         # AlphaFold 调用
│   │   │   ├── task_manager.py      # 任务管理
│   │   │   └── storage.py           # 文件存储
│   │   ├── models/
│   │   │   ├── task.py              # 数据库模型
│   │   │   └── schemas.py           # Pydantic 模型
│   │   └── utils/
│   │       └── logger.py            # loguru 配置
│   ├── requirements.txt
│   └── Dockerfile
├── data/                             # 数据库目录（挂载）
│   └── alphafold3.db                # SQLite 数据库
├── storage/                          # 结果文件存储（挂载）
│   └── tasks/
├── logs/                             # 日志目录（挂载）
│   └── app.log
├── docker/                           # AlphaFold Docker 相关
│   └── Dockerfile
└── docs/                             # 文档
    └── alphafold3-api-prd.md
```

**模型文件目录**：`/data2/ntt/lvyizhuo/alphafold3/`

```
/data2/ntt/lvyizhuo/alphafold3/
├── alphafold3/                       # AlphaFold 代码
├── databases/                        # 搜索数据库
├── images/                           # Docker 镜像
└── weights/                          # 模型权重
```

### 9.2 Docker 部署配置

**基于现有 alphafold3 镜像**，在其中添加 FastAPI 服务。

#### Dockerfile

```dockerfile
FROM alphafold3:latest

# 安装 FastAPI 依赖
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 复制 API 代码
COPY api/ /app/api/

# 设置工作目录
WORKDIR /app

# 暴露端口
EXPOSE 8015

# 启动命令
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8015"]
```

#### docker-compose.yml

```yaml
version: '3.8'

services:
  alphafold3-api:
    build:
      context: .
      dockerfile: api/Dockerfile
    container_name: alphafold3-api
    ports:
      - "8015:8015"
    volumes:
      # 数据库和存储
      - ./data:/app/data
      - ./storage:/app/storage
      - ./logs:/app/logs
      # AlphaFold 模型文件
      - /data2/ntt/lvyizhuo/alphafold3/weights:/root/models
      - /data2/ntt/lvyizhuo/alphafold3/databases:/root/public_databases
    environment:
      - DATABASE_PATH=/app/data/alphafold3.db
      - STORAGE_PATH=/app/storage
      - LOG_LEVEL=INFO
      - LOG_FILE=/app/logs/app.log
      - MODEL_DIR=/root/models
      - DB_DIR=/root/public_databases
      - TASK_TIMEOUT=7200
      - DATA_RETENTION_DAYS=30
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
```

### 9.3 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_PATH | SQLite 数据库路径 | /app/data/alphafold3.db |
| STORAGE_PATH | 文件存储路径 | /app/storage |
| LOG_LEVEL | 日志级别 | INFO |
| LOG_FILE | 日志文件路径 | /app/logs/app.log |
| MODEL_DIR | 模型参数目录 | /root/models |
| DB_DIR | 数据库目录 | /root/public_databases |
| TASK_TIMEOUT | 任务超时时间（秒） | 7200 |
| DATA_RETENTION_DAYS | 数据保留天数 | 30 |

### 9.4 启动命令

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 9.5 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| API 服务 | 8015 | FastAPI 接口服务 |
| SQLite | - | 无需端口，文件数据库 |

---

## 10. 测试方案

### 10.1 测试用例

#### 测试输入 JSON

```json
{
    "name": "test_protein",
    "modelSeeds": [42],
    "sequences": [
        {
            "protein": {
                "id": "A",
                "sequence": "GMRESYANENQFGFKTINSDIHKIVIVGGYGKLGGLFARYLRASGYPISILDREDWAVAESILANADVVIVSVPINLTLETIERLKPYLTENMLLADLTSVKREPLAKMLEVHTGAVLGLHPMFGADIASMAKQVVVRCDGRFPERYEWLLEQIQIWGAKIYQTNATEHDHNMTYIQALRHFSTFANGLHLSKQPINLANLLALSSPIYRLELAMIGRLFAQDAELYADIIMDKSENLAVIETLKQTYDEALTFFENNDRQGFIDAFHKVRDWFGDYSEQFLKESRQLLQQANDLKQG"
            }
        }
    ],
    "dialect": "alphafold3",
    "version": 1
}
```

### 10.2 测试场景

| 场景 | 测试内容 | 预期结果 |
|------|----------|----------|
| 正常提交 | 上传有效 JSON | 返回 task_id，状态为 pending |
| 无效 JSON | 上传格式错误的 JSON | 返回 400 错误 |
| 查询状态 | 查询存在的 task_id | 返回任务状态和详情 |
| 查询不存在 | 查询不存在的 task_id | 返回 404 错误 |
| 取消任务 | 取消 pending 状态任务 | 任务被取消 |
| 取消运行中 | 取消 running 状态任务 | 返回 409 错误 |
| 获取结果 | 查询已完成任务的结果 | 返回置信度数据 |
| 下载文件 | 下载 CIF 文件 | 返回文件内容 |
| 下载 ZIP | 下载完整结果包 | 返回 ZIP 文件 |

### 10.3 测试命令

```bash
# 提交任务
curl -X POST http://localhost:8015/api/v1/predict \
  -F "file=@test_input.json"

# 查询任务状态
curl http://localhost:8015/api/v1/tasks/{task_id}

# 获取任务列表
curl http://localhost:8015/api/v1/tasks

# 获取结果
curl http://localhost:8015/api/v1/tasks/{task_id}/results

# 下载文件
curl -O http://localhost:8015/api/v1/tasks/{task_id}/files/model.cif

# 健康检查
curl http://localhost:8015/api/v1/health
```

---

## 11. 项目计划

### 11.1 里程碑

| 阶段 | 时间 | 交付物 |
|------|------|--------|
| M1: 基础框架 | 第 1 周 | FastAPI + SQLite + loguru 配置 |
| M2: 核心功能 | 第 2 周 | AlphaFold 调用封装 + 任务队列 |
| M3: 接口实现 | 第 3 周 | 完整 REST API + 结果解析 |
| M4: 测试部署 | 第 4 周 | 测试用例 + 部署文档 |

### 11.2 详细任务分解

#### 第 1 周：基础框架
- [ ] 初始化项目结构（api/ 目录）
- [ ] 配置 FastAPI 应用
- [ ] 集成 loguru 日志
- [ ] 设计并创建 SQLite 数据库
- [ ] 实现基础中间件（CORS、异常处理）
- [ ] 编写 Dockerfile

#### 第 2 周：核心功能
- [ ] 实现 AlphaFold 调用封装（run_alphafold.py）
- [ ] 实现任务管理器（FIFO 队列）
- [ ] 实现文件存储管理器
- [ ] 实现异步任务 Worker

#### 第 3 周：接口实现
- [ ] 实现预测任务接口（POST /api/v1/predict）
- [ ] 实现任务查询接口（GET /api/v1/tasks）
- [ ] 实现结果获取接口（GET /api/v1/tasks/{id}/results）
- [ ] 实现文件下载接口
- [ ] 实现结果解析逻辑
- [ ] 实现健康检查和统计接口

#### 第 4 周：测试部署
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 编写 docker-compose.yml
- [ ] 编写部署文档
- [ ] 部署测试环境

---

## 12. 风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 推理时间过长 | 用户体验差 | 高 | 提供队列位置和进度反馈 |
| 存储空间不足 | 无法保存结果 | 中 | 自动清理 30 天前数据 |
| 模型推理失败 | 任务失败 | 中 | 记录错误信息，支持重试 |
| Docker 容器异常 | 服务中断 | 低 | 设置超时，异常捕获 |
| GPU 内存不足 | 推理失败 | 中 | 限制序列长度，优化配置 |

---

## 13. 附录

### 13.1 参考文档

- [AlphaFold 3 官方文档](https://github.com/google-deepmind/alphafold3)
- [AlphaFold 3 输入格式](input.md)
- [AlphaFold 3 输出格式](output.md)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [loguru 官方文档](https://loguru.readthedocs.io/)

### 13.2 术语表

| 术语 | 说明 |
|------|------|
| AlphaFold 3 | Google DeepMind 开发的生物分子结构预测模型 |
| pLDDT | 预测局部距离差异测试，原子级置信度指标（0-100） |
| PAE | 预测对齐误差，残基对之间的相对位置误差 |
| pTM | 预测模板建模分数，整体结构质量指标（0-1） |
| ipTM | 界面预测模板建模分数，复合物界面质量指标（0-1） |
| ranking_score | 综合排名分数，用于选择最佳预测 |
| mmCIF | macromolecular Crystallographic Information File，结构文件格式 |
| MSA | 多序列比对，用于蛋白质结构预测的进化信息 |

### 13.3 变更记录

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0 | 2026-06-25 | lvyizhuo | 初始版本 |
| v2.0 | 2026-06-25 | lvyizhuo | 简化设计：单文件上传、FIFO 队列、30 天数据清理、无认证 |
| v3.0 | 2026-06-25 | lvyizhuo | 明确部署方案：端口 8015、SQLite 外部、Docker 容器部署、目录结构 |

---

**文档结束**
