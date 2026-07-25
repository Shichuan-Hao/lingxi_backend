# 灵犀（LingXi）

基于 DeepSeek V3/R1 与 Ollama 的 Agent 对话式应用服务，支持文档上传、RAG 问答与联网搜索。

## 项目概览

### 技术栈

| 类别        | 技术                                        |
| ----------- | ------------------------------------------- |
| Web 框架    | FastAPI + Uvicorn                           |
| AI 模型     | DeepSeek V3/R1 (云端) + Ollama (本地)        |
| 流式输出    | SSE (Server-Sent Events)                    |
| 搜索增强    | SerpAPI (Google 搜索)                       |
| RAG / 向量  | FAISS + sentence-transformers               |
| 文档解析    | PyPDF2 + python-docx                        |
| 数据库      | SQLAlchemy (async) + MySQL + Redis          |
| 图数据库    | Neo4j (GraphRAG)                            |
| Agent 框架  | LangGraph                                   |
| 日志        | Loguru                                      |

### 项目结构

```
lingxi_backend/
├── main.py                         # FastAPI 入口，路由注册
├── run.py                          # 一键启动脚本
├── app/
│   ├── api/
│   │   └── auth.py                 # 用户认证路由 (注册/登录)
│   ├── core/
│   │   ├── config.py               # 配置管理 (pydantic-settings)
│   │   ├── database.py             # 数据库连接 (MySQL + Redis)
│   │   ├── security.py             # JWT 鉴权
│   │   ├── hashing.py              # 密码哈希
│   │   ├── logger.py               # 日志系统
│   │   └── middleware.py           # HTTP 请求日志中间件
│   ├── models/
│   │   ├── user.py                 # 用户模型
│   │   ├── conversation.py         # 会话模型
│   │   └── message.py              # 消息模型
│   ├── schemas/                    # Pydantic 数据校验
│   ├── services/
│   │   ├── llm_factory.py          # LLM 工厂，动态切换 DeepSeek/Ollama
│   │   ├── deepseek_service.py     # DeepSeek API 服务（流式）
│   │   ├── ollama_service.py       # Ollama 本地模型服务
│   │   ├── search_service.py       # 联网搜索增强服务
│   │   ├── embedding_service.py    # 文本向量化 (异步)
│   │   ├── rag_service.py          # RAG 文件处理与索引
│   │   ├── rag_chat_service.py     # RAG 文档问答
│   │   └── user_service.py         # 用户业务逻辑
│   └── tools/
│       └── search.py               # SerpAPI 搜索工具
├── static/dist/                    # 前端构建产物
├── uploads/                        # 上传文件目录
├── docs/                           # Jupyter Notebook 教程
├── requirements.txt
└── CHANGELOG.md
```

### 核心 API

| 接口        | 方法 | 说明                                     |
| ----------- | ---- | ---------------------------------------- |
| `/chat`     | POST | 普通对话，流式 SSE 输出，可切换 DeepSeek/Ollama |
| `/reason`   | POST | 深度推理，默认 Ollama 推理模型             |
| `/search`   | POST | 联网搜索增强，先搜索后总结回答             |
| `/upload`   | POST | 文件上传，支持 PDF/Word/TXT/Markdown       |
| `/chat-rag` | POST | 基于已上传文档的问答                       |
| `/api/register` | POST | 用户注册                               |
| `/api/token`    | POST | 用户登录，返回 JWT Token               |
| `/api/users/me` | GET  | 获取当前用户信息                       |
| `/health`   | GET  | 健康检查                                 |

### 架构设计

- **工厂模式**：`LLMFactory` 根据 `.env` 中的 `CHAT_SERVICE` 配置动态选择 DeepSeek 云端 API 或 Ollama 本地模型
- **流式输出**：所有对话接口均使用 SSE 实现流式响应，并自动记录响应摘要
- **RAG 管道**：`/upload` 上传文件 → 异步文本提取与向量化 → FAISS 索引 → `/chat-rag` 文档问答
- **异步安全**：`EmbeddingService` 和 `SearchService` 均使用 `asyncio.to_thread` 包裹阻塞操作，避免卡死事件循环
- **日志系统**：基于 Loguru 的结构化日志，按路由区分（💬🧠🔍📁），自动展示本地/云端模型信息，流式响应结束后输出摘要

## 环境要求

- Python 3.11+
- MySQL 8.0+
- Redis (可选，用于会话缓存)
- Ollama (可选，如需使用本地模型)

## 快速开始

### 1. 创建虚拟环境

**方式一：Python venv（轻量）**

```bash
# Windows
python -m venv .venv
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\activate

# Linux / Mac
python -m venv .venv
source .venv/bin/activate
```

**方式二：Conda（推荐）**

```bash
conda create -n lingxi python=3.11 -y
conda activate lingxi
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
# 使用国内镜像加速（可选）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# DeepSeek 云端 API
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Ollama 本地模型
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:1.5b
OLLAMA_REASON_MODEL=deepseek-r1:32b

# 服务选择 (deepseek 或 ollama)
CHAT_SERVICE=deepseek
REASON_SERVICE=ollama

# SerpAPI 搜索
SERPAPI_KEY=your-serpapi-key
SEARCH_RESULT_COUNT=3

# HuggingFace 镜像 (国内加速模型下载)
HF_ENDPOINT=https://hf-mirror.com

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=lingxi

# JWT
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 4. 启动服务

**开发模式**（支持热加载，代码修改自动生效）

```bash
python run.py
```

**生产模式**（关闭热加载）

```bash
# 单 Worker
python run.py --prod

# 多 Worker
python run.py --prod -w 4
```

> 多 Worker 模式下 `/upload` 和 `/chat-rag` 等依赖内存中 FAISS 索引的功能需额外处理共享状态，建议使用单 Worker + Nginx 反向代理实现并发。

启动成功后将显示路由表与模型配置：

```
──────────────────────────────────────────────────
  🌐  灵犀 · 智能助手   🌐
──────────────────────────────────────────────────
  📦  服务配置:
    💬   /chat       普通对话  → 云端 Deepseek(deepseek-chat)
    🧠   /reason     深度推理  → 本地 Ollama(deepseek-r1:32b)
    🔍   /search     联网搜索  → 云端 Deepseek(deepseek-chat)
  ──────────────────────────────────────────
    📁   /upload     文件上传(RAG)
    📖   /chat-rag   文档问答
    🔑   /api/register  用户注册
    🚪   /api/token     用户登录
    👤   /api/users/me  用户信息
    🏥   /health        健康检查
──────────────────────────────────────────────────
```

### 5. 访问

| 页面/功能    | 地址                         |
| ------------ | ---------------------------- |
| 前端页面     | http://localhost:8000/       |
| API 文档     | http://localhost:8000/docs   |
| 健康检查     | http://localhost:8000/health |

## 功能介绍

### 智能对话

- **普通对话** (`/chat`)：通用聊天，支持 DeepSeek 云端或 Ollama 本地模型，通过 `CHAT_SERVICE` 环境变量切换
- **深度推理** (`/reason`)：适合复杂逻辑推理问题，默认配置为 Ollama 推理模型
- **联网搜索** (`/search`)：自动调用 SerpAPI 搜索并整合结果回答，适合事实性问题

### 文档问答 (RAG)

1. **上传文档** (`/upload`)：支持 PDF、Word (.docx)、TXT、Markdown 格式，自动提取文本、分块、向量化并建立 FAISS 索引
2. **文档问答** (`/chat-rag`)：基于已上传文档的索引 ID 进行检索增强问答

### 用户认证

- 用户注册与登录，JWT Token 鉴权
- 加密密码存储 (bcrypt)

## 前端项目

本项目已内置前端页面（`static/dist/`），开箱即用。

如需独立开发前端，可参考配套项目：[My-DeepSeek-Web](https://github.com/MuYuCheney/My-DeepSeek-Web)，支持：
- 智能对话、Markdown 渲染、代码高亮
- 流式输出、聊天记录管理
- 文件上传与文档问答

## v1.1 更新要点

详见 [CHANGELOG.md](CHANGELOG.md)

- 修复上传卡死、搜索乱码等关键 Bug
- 日志系统全面优化（emoji 标识、路由区分、流式摘要）
- EmbeddingService / SearchService 异步重构
- HuggingFace 国内镜像加速
- 首次启动与热加载状态区分
- 前端 "AssistGen" → "灵犀"

## 注意事项

1. `.env` 包含敏感信息，已加入 `.gitignore`，不会提交到仓库
2. 使用本地 Ollama 模型前，需先启动 Ollama 服务并拉取模型：
   ```bash
   ollama pull qwen2.5:1.5b
   ollama pull deepseek-r1:32b
   ```
3. 生产环境请修改 CORS 配置和安全 Secret Key
4. `HuggingFace` 模型下载（sentence-transformers）在国内可能较慢，已默认配置 `HF_ENDPOINT` 镜像

## License

MIT
