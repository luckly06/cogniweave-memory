# 联调指南

这份文档只负责真实联调，不负责框架设计说明。

如果你的目标是验证 MiniMax、Qdrant、Neo4j 和当前框架主链路是否一起工作，请按这份文档执行。

## 1. 联调前提

项目目录：

```bash
cd /home/dd/dev/lab/03/process-accep/cogniweave_layered_impl/cogniweave_layered_impl
```

Python 依赖：

```bash
source /home/dd/miniconda3/etc/profile.d/conda.sh
conda activate cogniweave-minimax
```

如果环境还没创建：

```bash
source /home/dd/miniconda3/etc/profile.d/conda.sh
conda env create -f environment.miniconda.yml
conda activate cogniweave-minimax
```

必须确认 `.env` 已经填好真实值：

- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL=https://api.minimaxi.com`
- `MINIMAX_MODEL=MiniMax-M2.7`
- `COGNIWEAVE_QDRANT_URL=http://localhost:6333`
- `COGNIWEAVE_NEO4J_URI=neo4j://localhost:7687`
- `COGNIWEAVE_NEO4J_USER=neo4j`
- `COGNIWEAVE_NEO4J_PASSWORD=...`

## 2. 启动联调依赖

```bash
docker compose -f docker-compose.integration.yml up -d
docker compose -f docker-compose.integration.yml ps
```

停止：

```bash
docker compose -f docker-compose.integration.yml down
```

如果你想把容器数据也清掉：

```bash
docker compose -f docker-compose.integration.yml down -v
```

## 2.1 一键跑完整联调

如果你不想手动分 4 步执行，可以直接跑：

```bash
bash scripts/run_integration_suite.sh
```

默认行为：

- 自动启动 Qdrant 和 Neo4j
- 自动等待健康检查通过
- 自动执行 MiniMax / Qdrant / Neo4j 单组件检查
- 自动执行真实端到端 `unittest`
- 结束后自动关闭联调容器

如果你想保留容器不关：

```bash
KEEP_SERVICES_UP=1 bash scripts/run_integration_suite.sh
```

## 3. 单组件检查

### 3.1 MiniMax

```bash
python3 scripts/check_minimax.py
```

通过标准：

- 能返回非空文本
- 没有 `MiniMax invocation failed`

### 3.2 Qdrant

```bash
python3 scripts/check_qdrant.py
```

通过标准：

- `hit_ids` 非空
- 第一条命中是预期写入的 semantic record

### 3.3 Neo4j

```bash
python3 scripts/check_neo4j.py
```

通过标准：

- `neighbors` 里包含刚写入的 target id

## 4. 全链路联调

真实端到端联调不会默认运行。

原因很简单：

- 会消耗真实模型调用
- 需要真实 Qdrant 和 Neo4j
- 失败时排查成本比本地 smoke test 高

你必须显式打开它：

```bash
export COGNIWEAVE_RUN_REAL_INTEGRATION=true
python3 -m unittest tests.integration.test_full_stack -v
```

这套联调会验证：

- MiniMax 能真实完成 `run_cycle`
- Key Memory 写入后可按 `task_scope/policy_scope` 命中
- tool loop 能产生 episodic / experience 写回
- offline ingest 后可以通过 RAG 召回
- semantic cross-memory link 会写入 graph store

## 5. 推荐联调顺序

不要跳步骤。

正确顺序是：

1. `scripts/check_minimax.py`
2. `scripts/check_qdrant.py`
3. `scripts/check_neo4j.py`
4. `python3 -m unittest tests.integration.test_full_stack -v`

如果你不想手动拆开跑，就直接执行：

1. `bash scripts/run_integration_suite.sh`

如果第 1 到第 3 步任何一步失败，不要直接跑第 4 步。

## 6. 常见失败定位

### 6.1 MiniMax 失败

先检查：

- `.env` 是否真的被加载
- `MINIMAX_BASE_URL` 是否还是 `https://api.minimaxi.com`
- 模型名是否是 `MiniMax-M2.7`
- 当前 conda 环境里是否装了 `openai`

### 6.2 Qdrant 失败

先检查：

- 容器是否在跑
- `http://localhost:6333/collections` 能否访问
- 当前环境里是否装了 `qdrant-client`

### 6.3 Neo4j 失败

先检查：

- 容器是否在跑
- `neo4j://localhost:7687` 是否可连接
- 用户名密码是否和 `.env` 一致
- 当前环境里是否装了 `neo4j`

### 6.4 全链路失败

优先按下面顺序定位：

1. 先看单组件检查是否绿
2. 再看 `run_cycle` 是否能出非空回答
3. 再看 `writeback.drain()` 后 store 里是否真的有记录
4. 最后看 graph neighbors 和 RAG retrieval 结果

## 7. 注意事项

- 不要把真实密钥提交进仓库
- 不要直接修改 `cogniweave_full/` 来“绕过”联调失败
- 如果真实联调暴露出框架缺口，先写 `.md` 记录缺口，再决定是否改框架
