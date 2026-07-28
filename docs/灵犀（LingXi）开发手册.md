# 灵犀（LingXi）开发手册

> 本文档覆盖项目整体架构、目录结构、API 端点、数据库模型、配置系统与启动部署，与《灵犀（LingXi）智能客服.md》中的核心模块详解互为补充。

---

## 一、项目定位

**灵犀（LingXi）** 是一个面向电商垂直领域的智能客服系统，基于大语言模型的 Multi-Agent 架构，实现多场景意图识别、混合检索问答、动态上下文理解等核心能力，为企业级用户提供高效的对话与咨询服务解决方案。

---

## 二、技术栈总览

| 层次 | 技术 | 说明 |
|------|------|------|
| Web 框架 | **FastAPI** + Uvicorn | 异步 HTTP 服务，支持 SSE 流式响应 |
| 前端 | **Vue 3** + Element Plus + TypeScript | SPA 构建产物位于 `static/dist/` |
| AI Agent 框架 | **LangGraph** + LangChain | 图状态机构建 Multi-Agent，`Map-Reduce` 并行工具调用 |
| LLM 服务 | **DeepSeek V4 Pro**（云端 API）/ **Ollama**（本地） | 工厂模式按配置动态切换 |
| 推理模型 | DeepSeek-R1（本地 Ollama） | 专用于深度推理场景 |
| 视觉模型 | **GPT-4o** | 独立视觉 API 配置，用于图片分析 |
| Embedding | Ollama **bge-m3** | 语义向量生成（缓存 + 检索） |
| 关系数据库 | **MySQL** + SQLAlchemy（异步） | 用户 / 会话 / 消息持久化 |
| 图数据库 | **Neo4j** | 电商知识图谱，结构化数据检索 |
| 缓存 | **Redis** | 语义向量缓存（余弦相似度匹配） |
| 知识图谱 RAG | **Microsoft GraphRAG** | 本地文档索引构建与全局/局部查询 |
| 向量检索 | **FAISS** + Sentence-Transformers | 本地文件 RAG 问答 |
| 搜索引擎 | SerpAPI | Google 实时联网检索（Function Calling） |
| 认证 | JWT（python-jose）+ bcrypt | Token 签发 / 密码哈希 |
| 日志 | Loguru | 结构化日志，分级存储 |

---

## 三、整体架构

```
┌──────────────────────────────────────────────────┐
│               前端 SPA (Vue 3)                     │
│           static/dist/ 静态托管                    │
└───────────────────┬──────────────────────────────┘
                    │ HTTP / SSE
┌───────────────────▼──────────────────────────────┐
│           FastAPI 主应用 (main.py)                 │
│  ├─ /api/* 路由 (api_router + 内联端点)            │
│  ├─ 中间件: CORS + LoggingMiddleware              │
│  └─ 静态文件挂载: / → static/dist/                 │
└─────────┬────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────┐
│         LangGraph Multi-Agent 图  (lg_agent)       │
│                                                    │
│  ┌───────────────┐     ┌───────────────────────┐  │
│  │ Router 节点    │     │  业务处理子图 / 节点:   │  │
│  │ analyze_and   │────▶│  - general-query      │  │
│  │ _route_query  │     │  - additional-query   │  │
│  │ (意图识别)     │     │  - graphrag-query ⭐   │  │
│  └───────────────┘     │  - image-query        │  │
│                        │  - file-query         │  │
│                        └───────────┬───────────┘  │
│                                    │              │
│  ┌─────────────────────────────────▼────────────┐ │
│  │  graphrag-query 子图（知识库检索）             │ │
│  │  Guardrails → Planner → Tool Selection       │ │
│  │    ├→ Text2Cypher（动态 Cypher 生成）          │ │
│  │    ├→ PredefinedCypher（预定义查询）           │ │
│  │    └→ CustomerTools（GraphRAG 查询）           │ │
│  │        ↓                                      │ │
│  │  Summarize → Final Answer → 幻觉检测           │ │
│  └──────────────────────────────────────────────┘ │
└─────────┬────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────┐
│                 数据 & 服务层                       │
│  MySQL ┃ Neo4j ┃ Redis ┃ GraphRAG ┃ FAISS         │
└──────────────────────────────────────────────────┘
```

### 数据流概要

1. 用户通过前端提交文本/图片 → FastAPI 接收请求
2. API 层调用编译好的 LangGraph 图 → `analyze_and_route_query` 意图识别
3. 路由到对应处理节点 → LLM 直接回复 / 知识库检索子图展开
4. 子图内：护栏校验 → 任务分解 → 工具选择 → 并行执行 → 汇总 → 最终回答
5. SSE 流式逐字返回前端

---

## 四、目录结构

```
lingxi_backend/
├── main.py                       # FastAPI 主应用（所有 API 端点）
├── run.py                        # 服务器启动脚本
├── requirements.txt              # Python 依赖清单
├── .env / .env.example           # 环境变量配置
├── README.md                     # 项目说明
├── CHANGELOG.md                  # 版本更新日志
├── 架构说明.md                    # 架构图引用
├── 灵犀（LingXi）智能客服.md       # 产品背景与核心模块详解
├── 灵犀（LingXi）开发手册.md       # 本文档
│
├── app/
│   ├── api/                      # API 路由层
│   │   ├── __init__.py           # 注册 api_router
│   │   └── auth.py               # 认证路由 (/register, /token, /users/me)
│   │
│   ├── core/                     # 核心基础设施
│   │   ├── config.py             # 全局配置 (pydantic-settings)
│   │   ├── database.py           # MySQL 异步连接 (SQLAlchemy)
│   │   ├── security.py           # JWT 认证
│   │   ├── hashing.py            # 密码哈希 (bcrypt)
│   │   ├── logger.py             # 日志系统 (Loguru)
│   │   └── middleware.py         # HTTP 日志中间件
│   │
│   ├── models/                   # 数据库 ORM 模型 (SQLAlchemy)
│   │   ├── user.py               # User 表
│   │   ├── conversation.py       # Conversation 表
│   │   └── message.py            # Message 表
│   │
│   ├── schemas/                  # Pydantic 数据校验
│   │   └── user.py               # UserCreate, Token 等
│   │
│   ├── services/                 # 业务逻辑服务层
│   │   ├── llm_factory.py        # LLM 工厂（DeepSeek / Ollama 切换）
│   │   ├── deepseek_service.py   # DeepSeek API 流式/非流式
│   │   ├── ollama_service.py     # Ollama 本地模型流式服务
│   │   ├── search_service.py     # 联网检索 (SerpAPI + Function Calling)
│   │   ├── conversation_service.py  # 会话 CRUD
│   │   ├── user_service.py       # 用户注册 / 认证
│   │   ├── embedding_service.py  # FAISS 向量索引
│   │   ├── indexing_service.py   # GraphRAG 文件索引构建
│   │   ├── redis_semantic_cache.py  # Redis 语义向量缓存
│   │   └── function_tools.py     # 工具注册中心 (ToolRegistry)
│   │
│   ├── tools/                    # 外部工具
│   │   ├── definitions.py        # 工具 JSON Schema
│   │   └── search.py             # SerpAPI 实现
│   │
│   ├── prompts/                  # 提示词模板
│   │   └── search_prompts.py
│   │
│   ├── lg_agent/                 # LangGraph Multi-Agent 核心 ⭐
│   │   ├── main.py               # 独立测试入口
│   │   ├── lg_builder.py         # 图构建（节点 / 边 / 编译）
│   │   ├── lg_states.py          # 图状态定义
│   │   ├── lg_prompts.py         # 所有系统提示词
│   │   ├── utils.py              # 工具函数
│   │   └── kg_sub_graph/         # 知识图谱检索子图
│   │       ├── kg_neo4j_conn.py       # Neo4j 连接
│   │       ├── kg_states.py           # 子图状态
│   │       ├── kg_tools_list.py       # 工具列表
│   │       └── agentic_rag_agents/    # 多 Agent RAG 子图组件
│   │           ├── components/
│   │           │   ├── guardrails/    # 安全护栏
│   │           │   ├── planner/       # 任务分解
│   │           │   ├── tool_selection/ # 工具选择路由
│   │           │   ├── text2cypher/   # 动态 Cypher 生成
│   │           │   ├── predefined_cypher/ # 预定义查询
│   │           │   ├── customer_tools/ # GraphRAG 查询
│   │           │   ├── summarize/     # 结果汇总
│   │           │   ├── final_answer/  # 最终回答
│   │           │   └── validate_final_answer/ # 幻觉检测
│   │           ├── workflows/         # 多 Agent 编排
│   │           ├── retrievers/        # Cypher 示例检索器
│   │           └── ingest/            # 示例数据导入
│   │
│   ├── graphrag/                 # Microsoft GraphRAG 完整项目
│   └── test/                     # 测试脚本
│
├── scripts/
│   └── init_db.py                # 数据库初始化
│
├── static/dist/                  # 前端构建产物
├── uploads/                      # 文件上传目录
├── images/                       # 文档图片资源
├── docs/                         # 学习笔记 (Jupyter)
└── logs/                         # 日志输出
```

---

## 五、API 端点一览

### 5.1 认证模块（`app/api/auth.py`）

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/register` | 用户注册（用户名 + 邮箱 + 密码） | 无 |
| POST | `/api/token` | 登录，返回 JWT Token | 无 |
| GET | `/api/users/me` | 获取当前用户信息 | Bearer Token |

### 5.2 通用对话（`main.py`）

| 方法 | 路径 | 说明 | 特点 |
|------|------|------|------|
| POST | `/api/chat` | 通用流式问答 | SSE 流式，含 Redis 语义缓存 |
| POST | `/api/reason` | 深度推理 | DeepSeek-R1 推理模型 |
| POST | `/api/search` | 联网检索 | Function Calling + SerpAPI |

### 5.3 会话管理（`main.py` + `conversation_service.py`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/conversations` | 创建新会话 |
| GET | `/api/conversations/user/{user_id}` | 获取用户所有会话 |
| GET | `/api/conversations/{id}/messages` | 获取会话消息历史 |
| PUT | `/api/conversations/{id}/name` | 修改会话名称 |
| DELETE | `/api/conversations/{id}` | 删除会话（级联删除消息） |

### 5.4 LangGraph Multi-Agent 智能客服 ⭐

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/langgraph/query` | 主智能客服入口，文本+图片，SSE 流式输出 |
| POST | `/api/langgraph/resume` | 恢复中断的 Agent 流程 |

### 5.5 文件上传与 RAG

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文件并触发 GraphRAG 索引构建 |
| POST | `/api/upload/image` | 图片上传 |
| POST | `/chat-rag` | 基于 FAISS 的本地文档问答 |

### 5.6 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 服务健康检查 |

---

## 六、数据库模型

### 6.1 MySQL 表结构（3 张表）

#### `users` — 用户表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT (PK) | 主键 |
| username | VARCHAR | 用户名 |
| email | VARCHAR | 邮箱 |
| password_hash | VARCHAR | bcrypt 哈希密码 |
| created_at | DATETIME | 创建时间 |
| last_login | DATETIME | 最后登录 |
| status | ENUM | 用户状态 |

#### `conversations` — 会话表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT (PK) | 主键 |
| user_id | INT (FK → users) | 所属用户 |
| title | VARCHAR | 会话标题 |
| dialogue_type | ENUM | 对话类型：普通/深度思考/联网检索/RAG |
| created_at | DATETIME | 创建时间 |
| status | ENUM | 会话状态 |

#### `messages` — 消息表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT (PK) | 主键 |
| conversation_id | INT (FK → conversations) | 所属会话 |
| sender | VARCHAR | 发送者：user / assistant |
| content | TEXT | 消息内容 |
| created_at | DATETIME | 发送时间 |
| message_type | VARCHAR | 消息类型 |

### 6.2 Neo4j 图数据库（电商知识图谱）

#### 节点类型

| 节点 | 标识 | 关键属性 |
|------|------|---------|
| **Product** | ProductID | ProductName, UnitPrice, UnitsInStock... |
| **Category** | CategoryID | CategoryName, Description |
| **Supplier** | SupplierID | CompanyName, Country... |
| **Customer** | CustomerID | CompanyName, ContactName... |
| **Order** | OrderID | OrderDate, ShippedDate... |
| **Employee** | EmployeeID | FirstName, LastName... |
| **Shipper** | ShipperID | CompanyName |
| **Review** | — | Rating, Comment |

#### 关系类型

| 关系 | 方向 | 说明 |
|------|------|------|
| BELONGS_TO | Product → Category | 产品归属类别 |
| SUPPLIED_BY | Product → Supplier | 产品供应商 |
| PLACED | Customer → Order | 客户下单 |
| CONTAINS | Order → Product | 订单包含产品 |
| PROCESSED | Employee → Order | 员工处理订单 |
| SHIPPED_VIA | Order → Shipper | 物流配送 |
| WROTE | Customer → Review | 客户评价 |
| ABOUT | Review → Product | 评价关联产品 |

### 6.3 Redis 缓存结构

- **用途**：语义向量缓存
- **Embedding 模型**：Ollama `bge-m3`
- **匹配方式**：余弦相似度
- **可配置项**：相似度阈值、过期时间

---

## 七、Multi-Agent 意图路由

用户提问后，`analyze_and_route_query` 节点自动识别意图，`route_query` 按条件分发到 5 种处理分支：

```
START → analyze_and_route_query
              │ (条件路由)
    ┌─────────┼──────────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼          ▼
 general  additional  graphrag   image      file
 -query    -query      -query    -query     -query
```

| 意图 | 处理方式 | 节点/子图 |
|------|---------|----------|
| `general-query` | 闲聊，纯 LLM 回复，客服风格提示工程 | 普通节点 |
| `additional-query` | 安全护栏 → 引导用户补充信息 | 普通节点 + 护栏 |
| **`graphrag-query`** | 知识库检索：护栏→规划→工具选择→并行执行→汇总 | **子图（SubGraph）** |
| `image-query` | GPT-4o 视觉分析 → 结合上下文回复 | 普通节点 |
| `file-query` | 文件解析回复 | 普通节点（待完善） |

### graphrag-query 子图内部流程

```
Guardrails（安全护栏）
    ↓
Planner（任务分解为子任务）
    ↓
Tool Selection（工具选择 + Map-Reduce 并行分发）
    ├── Text2Cypher（LLM 动态生成 Cypher → 校验 → 修正 → 执行）
    ├── PredefinedCypher（预定义 Cypher 字典直接执行）
    └── CustomerTools（Microsoft GraphRAG 检索）
    ↓
Summarize（结果汇总）
    ↓
Final Answer（最终回答生成）
    ↓
Validate Final Answer（幻觉检测）
```

---

## 八、配置系统（`.env`）

### 8.1 LLM 服务路由

| 配置项 | 可选值 | 说明 |
|--------|--------|------|
| `CHAT_SERVICE` | `deepseek` / `ollama` | 日常聊天用哪个服务 |
| `REASON_SERVICE` | `deepseek` / `ollama` | 推理任务用哪个服务 |
| `AGENT_SERVICE` | `deepseek` / `ollama` | Multi-Agent 客服用哪个服务 |

### 8.2 核心配置项

| 分类 | 配置项 | 说明 |
|------|--------|------|
| DeepSeek | `DEEPSEEK_API_KEY` | API 密钥 |
| DeepSeek | `DEEPSEEK_BASE_URL` | API 地址 |
| DeepSeek | `DEEPSEEK_MODEL` | 模型名 |
| Ollama | `OLLAMA_BASE_URL` | 服务地址 |
| Ollama | `OLLAMA_CHAT_MODEL` | 聊天模型 |
| Ollama | `OLLAMA_REASON_MODEL` | 推理模型 |
| Ollama | `OLLAMA_AGENT_MODEL` | Agent 模型 |
| Ollama | `OLLAMA_EMBEDDING_MODEL` | Embedding 模型 |
| 视觉 | `VISION_API_KEY / BASE_URL / MODEL` | GPT-4o 配置 |
| MySQL | `DB_HOST / PORT / USER / PASSWORD / NAME` | 数据库连接 |
| Neo4j | `NEO4J_URI / USERNAME / PASSWORD` | 图数据库连接 |
| Redis | `REDIS_HOST / PORT / DB` | 缓存连接 |
| JWT | `SECRET_KEY / ALGORITHM / ACCESS_TOKEN_EXPIRE_MINUTES` | 认证配置 |
| 搜索 | `SERPAPI_KEY / SERPAPI_RESULTS_COUNT` | 联网检索 |
| GraphRAG | `GRAPHRAG_PROJECT_DIR / DATA_DIR` | 知识库路径 |
| 缓存 | `CACHE_SIMILARITY_THRESHOLD / CACHE_EXPIRE_SECONDS` | 缓存参数 |

---

## 九、启动与部署

### 9.1 环境准备

```bash
# 1. 克隆项目
git clone git@github.com:Shichuan-Hao/lingxi_backend.git

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制并编辑配置文件
cp .env.example .env
# 按注释填写各项配置

# 5. 初始化数据库
python scripts/init_db.py
```

### 9.2 启动服务

```bash
# 开发模式（默认 8000 端口）
python run.py

# 生产模式（单 Worker）
python run.py --prod

# 生产模式（多 Worker）
python run.py --prod -w 4
```

启动后访问：
- **前端页面**：`http://localhost:8000`
- **API 文档**：`http://localhost:8000/docs`

---

## 十、关键设计特点总结

| 特点 | 说明 |
|------|------|
| **工厂模式切换 LLM** | `LLMFactory` 根据 `.env` 配置动态选择 DeepSeek / Ollama |
| **SSE 流式响应** | 所有对话接口 `text/event-stream`，打字机效果 |
| **语义缓存加速** | Redis + bge-m3 Embedding，余弦相似度匹配，阈值可配 |
| **安全护栏机制** | 经营范围人工规则 + Neo4j Schema 动态提示，双重保障 |
| **Map-Reduce 并行调用** | LangGraph Send API 实现多工具并行 + 结果汇总 |
| **GraphRAG 集成** | Microsoft GraphRAG 作为子图接入，全局/局部查询 |
| **多模型混合策略** | 聊天→DeepSeek V4，推理→DeepSeek-R1，视觉→GPT-4o，Embedding→bge-m3 |
| **状态持久化** | LangGraph MemorySaver，跨请求会话状态保持，支持中断恢复 |
| **Cypher 多层校验** | 语法校验 → 权限控制 → 关系方向校正 → 大模型辅助校验 |
| **高度可迁移** | 核心组件抽象封装，换业务只需替换提示词 + Neo4j Schema + GraphRAG 数据 |
