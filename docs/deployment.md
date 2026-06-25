# AlphaFold 3 推理服务 — 部署与运维文档

## 文档信息

| 字段 | 内容 |
|------|------|
| 项目名称 | AlphaFold 3 推理服务 API |
| 文档版本 | v1.0 |
| 创建日期 | 2026-06-25 |
| 适用环境 | Ubuntu 22.04 + NVIDIA GPU + Docker |

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker 容器 (端口 8015)                     │
│                                                              │
│  FastAPI + uvicorn                                           │
│  ├── /api/v1/predict         POST  JSON 文件推理              │
│  ├── /api/v1/predict/dna     POST  DNA 序列推理（EVO2 专用）   │
│  ├── /api/v1/tasks           GET   任务列表                   │
│  ├── /api/v1/tasks/{id}      GET   任务详情                   │
│  ├── /api/v1/tasks/{id}/results  GET  推理结果                │
│  ├── /api/v1/tasks/{id}/download/{file}  GET  文件下载        │
│  ├── /api/v1/tasks/{id}      DELETE  删除任务                 │
│  ├── /api/v1/stats           GET   系统统计                   │
│  └── /health                 GET   健康检查                   │
│                                                              │
│  依赖: SQLite + run_alphafold.py (GPU 推理)                   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ./data/              ./storage/            ./logs/
   (SQLite 数据库)      (推理结果文件)        (运行日志)
```

---

## 2. 服务器要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| GPU | NVIDIA GPU ≥ 16GB 显存 | NVIDIA A100 40GB |
| 内存 | 32GB | 64GB |
| 磁盘 | 100GB（模型权重 + 数据库） | 500GB SSD |
| Docker | 20.10+ | 最新版 |
| Docker Compose | 2.0+ | 最新版 |
| NVIDIA Container Toolkit | 已安装 | 已安装 |

**磁盘空间分布**：

| 路径 | 用途 | 预估大小 |
|------|------|---------|
| `/data2/ntt/lvyizhuo/alphafold3/weights` | 模型权重 | ~5GB |
| `/data2/ntt/lvyizhuo/alphafold3/databases` | 搜索数据库 | ~100GB |
| `./data/` | SQLite 数据库 | < 100MB |
| `./storage/` | 推理结果（自动清理 30 天前） | 按使用量增长 |
| `./logs/` | 日志文件 | 自动轮转，保留 30 天 |

---

## 3. 目录结构

### 3.1 项目目录

```
/data2/ntt/lvyizhuo/task06-alphafold3-agent/
├── api/                            # API 服务代码
│   ├── main.py                     # FastAPI 入口
│   ├── config.py                   # 配置管理
│   ├── router.py                   # 路由定义（9 个接口）
│   ├── schemas.py                  # Pydantic 数据模型
│   ├── service.py                  # 业务逻辑层
│   ├── alphafold.py                # AlphaFold 推理封装
│   ├── models.py                   # SQLAlchemy ORM 模型
│   ├── database.py                 # 数据库连接管理
│   ├── cleanup.py                  # 定时清理任务
│   └── requirements.txt            # Python 依赖
├── docker/
│   └── Dockerfile                  # 生产镜像构建文件
├── docs/                           # 文档目录
├── docker-compose.yml              # 生产部署配置
├── docker-compose.override.yml     # 开发环境覆盖配置（热加载）
├── data/                           # SQLite 数据库（绑定挂载）
│   └── alphafold3.db
├── storage/                        # 推理结果存储（绑定挂载）
│   └── outputs/
│       └── {task_id}/
│           └── output/
│               └── {job_name}/
│                   ├── {job_name}_model.cif
│                   ├── {job_name}_confidences.json
│                   ├── {job_name}_summary_confidences.json
│                   ├── {job_name}_ranking_scores.csv
│                   └── seed-{n}_sample-{n}/
│                       └── ...
├── logs/                           # 日志文件（绑定挂载）
│   └── app.log
└── run_alphafold.py                # AlphaFold 3 推理脚本
```

### 3.2 存储架构

所有数据通过 **绑定挂载** 映射到宿主机，容器删除不影响数据：

| 容器内路径 | 宿主机路径 | 用途 | 挂载方式 |
|-----------|-----------|------|---------|
| `/app/data/` | `./data/` | SQLite 数据库 | 读写 |
| `/app/storage/` | `./storage/` | 推理结果文件 | 读写 |
| `/app/logs/` | `./logs/` | 运行日志 | 读写 |
| `/root/models` | `/data2/.../weights` | 模型权重 | 只读 |
| `/root/public_databases` | `/data2/.../databases` | 搜索数据库 | 只读 |

### 3.3 结果文件命名规则

每个推理任务的输出目录结构：

```
storage/outputs/{task_id}/output/{job_name}/
├── {job_name}_model.cif                        # 最佳预测的 3D 结构
├── {job_name}_confidences.json                 # 最佳预测的完整置信度
├── {job_name}_summary_confidences.json         # 最佳预测的置信度摘要
├── {job_name}_data.json                        # 输入数据（含 MSA）
├── {job_name}_ranking_scores.csv               # 所有预测的排名分数
├── seed-{seed}_sample-{sample}/                # 每个预测的独立目录
│   ├── {job_name}_seed-{n}_sample-{n}_model.cif
│   ├── {job_name}_seed-{n}_sample-{n}_confidences.json
│   └── {job_name}_seed-{n}_sample-{n}_summary_confidences.json
└── ...
```

---

## 4. 部署步骤

### 4.1 首次部署

```bash
# 1. 进入项目目录
cd /data2/ntt/lvyizhuo/task06-alphafold3-agent

# 2. 创建本地数据目录
mkdir -p data storage logs

# 3. 构建镜像
docker-compose build

# 4. 启动服务
docker-compose up -d

# 5. 查看日志确认启动成功
docker-compose logs -f

# 6. 验证服务
curl http://localhost:8015/health
```

### 4.2 更新代码后重新部署

```bash
# 1. 拉取最新代码
git pull

# 2. 重建镜像并重启
docker-compose down && docker-compose up -d --build

# 3. 验证
curl http://localhost:8015/health
```

### 4.3 开发环境（热加载）

开发时使用 `docker-compose.override.yml` 自动生效，代码修改后无需重建镜像：

```bash
# 1. 启动（自动加载 override 配置）
docker-compose up -d

# 2. 修改 api/ 目录下的代码，uvicorn 自动热重载
# 无需重启容器

# 3. 如需切换到生产模式
docker-compose -f docker-compose.yml up -d --build
```

开发模式与生产模式的区别：

| 特性 | 开发模式（override） | 生产模式 |
|------|-------------------|---------|
| 代码挂载 | `./api:/app/alphafold/api` | 镜像内 COPY |
| 启动命令 | `uvicorn --reload` | `uvicorn` |
| 代码修改 | 实时生效 | 需重建镜像 |

---

## 5. 配置说明

### 5.1 环境变量

所有配置在 `docker-compose.yml` 的 `environment` 中设置：

| 变量名 | 说明 | 默认值 | 修改方式 |
|--------|------|--------|---------|
| `API_HOST` | 监听地址 | `0.0.0.0` | docker-compose.yml |
| `API_PORT` | 监听端口 | `8015` | docker-compose.yml |
| `ALPHAFOLD_DIR` | 容器内 AlphaFold 代码目录 | `/app/alphafold` | 不建议修改 |
| `MODEL_DIR` | 模型权重目录 | `/root/models` | 不建议修改 |
| `DB_DIR` | 搜索数据库目录 | `/root/public_databases` | 不建议修改 |
| `STORAGE_PATH` | 推理结果存储目录 | `/app/storage` | 不建议修改 |
| `DATABASE_PATH` | SQLite 数据库文件路径 | `/app/data/alphafold3.db` | 不建议修改 |
| `LOG_FILE` | 日志文件路径 | `/app/logs/app.log` | 不建议修改 |
| `LOG_LEVEL` | 日志级别 | `INFO` | 按需调整 |
| `DATA_RETENTION_DAYS` | 结果保留天数 | `30` | 按需调整 |
| `MAX_UPLOAD_SIZE_MB` | 上传文件大小限制 | `10` | 按需调整 |
| `NVIDIA_VISIBLE_DEVICES` | 可见 GPU | `0` | 按需调整 |
| `CUDA_VISIBLE_DEVICES` | CUDA 设备 | `0` | 按需调整 |

### 5.2 修改端口

编辑 `docker-compose.yml`：

```yaml
ports:
  - "新端口:8015"    # 左边是宿主机端口，右边是容器端口
```

### 5.3 切换 GPU

编辑 `docker-compose.yml`：

```yaml
environment:
  - NVIDIA_VISIBLE_DEVICES=1    # 改为其他 GPU 编号
  - CUDA_VISIBLE_DEVICES=1
```

---

## 6. 日常运维

### 6.1 查看日志

```bash
# 实时日志
docker-compose logs -f

# 最近 100 行
docker-compose logs --tail=100

# 宿主机日志文件
tail -f logs/app.log
```

### 6.2 查看服务状态

```bash
# 容器状态
docker-compose ps

# 健康检查
curl http://localhost:8015/health

# 系统统计
curl http://localhost:8015/api/v1/stats
```

### 6.3 查看推理结果

结果文件直接在宿主机上访问：

```bash
# 查看所有任务
ls storage/outputs/

# 查看某个任务的结果
ls storage/outputs/{task_id}/output/{job_name}/

# 查看数据库（需要 sqlite3）
sqlite3 data/alphafold3.db "SELECT id, name, status, created_at FROM tasks;"
```

### 6.4 手动清理过期数据

系统默认每天凌晨 03:00 (UTC) 自动清理超过 30 天的数据。如需手动触发：

```bash
# 进入容器执行清理
docker exec -it alphafold3-api python3 -c "
import asyncio
from api.cleanup import cleanup_old_tasks
asyncio.run(cleanup_old_tasks())
"
```

### 6.5 数据备份

```bash
# 备份数据库
cp data/alphafold3.db data/alphafold3.db.bak

# 备份指定任务结果
cp -r storage/outputs/{task_id} /backup/path/

# 完整备份
tar czf backup_$(date +%Y%m%d).tar.gz data/ storage/ logs/
```

### 6.6 重启服务

```bash
# 重启（不重建镜像）
docker-compose restart

# 重建并重启
docker-compose down && docker-compose up -d --build
```

### 6.7 停止服务

```bash
# 停止容器（数据保留）
docker-compose down

# 停止并删除所有数据（谨慎！）
docker-compose down -v   # 不推荐，绑定挂载模式下 -v 不影响宿主机数据
```

---

## 7. 故障排查

### 7.1 服务无法启动

```bash
# 查看容器日志
docker-compose logs --tail=200

# 检查端口占用
lsof -i :8015

# 检查 GPU 是否可用
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### 7.2 推理失败

```bash
# 查看详细错误日志
docker-compose logs --tail=500 | grep -i error

# 检查 GPU 显存
docker exec alphafold3-api nvidia-smi

# 检查模型权重是否正确挂载
docker exec alphafold3-api ls /root/models/
```

### 7.3 磁盘空间不足

```bash
# 检查磁盘使用
df -h /data2

# 查看存储目录大小
du -sh storage/ data/ logs/

# 清理 Docker 旧镜像
docker image prune -f
```

### 7.4 数据库损坏

```bash
# 检查数据库完整性
sqlite3 data/alphafold3.db "PRAGMA integrity_check;"

# 如损坏，从备份恢复
cp data/alphafold3.db.bak data/alphafold3.db
```

---

## 8. API 接口总览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/predict` | 上传 JSON 文件推理 |
| POST | `/api/v1/predict/dna` | DNA 序列推理（EVO2 专用，自动生成双链） |
| GET | `/api/v1/tasks` | 任务列表（分页） |
| GET | `/api/v1/tasks/{task_id}` | 任务详情 |
| GET | `/api/v1/tasks/{task_id}/results` | 推理结果详情 |
| GET | `/api/v1/tasks/{task_id}/download/{filename}` | 下载结果文件 |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务 |
| GET | `/api/v1/stats` | 系统统计 |
| GET | `/health` | 健康检查 |

详细接口文档见 `docs/alphafold3-api.md`。

---

## 9. 安全注意事项

- 模型权重和搜索数据库以 **只读** 方式挂载，防止误修改
- API 无认证机制，仅限内网访问，不要暴露到公网
- 上传文件大小限制 10MB，防止恶意上传
- 定时清理任务自动删除 30 天前的数据
- 日志自动轮转（7 天），保留 30 天

---

## 10. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| v1.0 | 2026-06-25 | 初始版本，支持 JSON 文件推理和 DNA 序列推理 |
