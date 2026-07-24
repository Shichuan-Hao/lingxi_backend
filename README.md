# 灵犀（ling_xi）

一个基于 Deepseek V3 & R1 构建的 Agent 对话式应用服务

## 项目概览

### 技术栈

| 类别         | 技术                          |
| ------------ | ----------------------------- |
| Web 框架     | FastAPI + Uvicorn             |
| AI 模型      | DeepSeek V3/R1 (云端) + Ollama (本地) |
| 搜索增强     | SerpAPI (Google 搜索)         |
| 数据库       | SQLAlchemy + Redis + MySQL    |
| 图数据库     | Neo4j                         |
| 知识图谱     | GraphRAG                      |
| 向量检索     | FAISS + sentence_transformers |
| Agent 框架   | LangGraph                     |

### 项目结构

```
lingxi_backend/
├── main.py                         # FastAPI 入口，路由注册
├── app/
│   ├── api/v1/chat.py              # API 版本化路由（规划中）
│   ├── core/config.py              # 配置管理 (pydantic-settings)
│   ├── models/chat.py              # 数据模型
│   ├── services/
│   │   ├── llm_factory.py          # LLM 工厂，动态切换 DeepSeek/Ollama
│   │   ├── deepseek_service.py     # DeepSeek API 服务（流式/非流式）
│   │   ├── ollama_service.py       # Ollama 本地模型服务
│   │   └── search_service.py       # 联网搜索增强聊天服务
│   ├── tools/search.py             # SerpAPI 搜索工具
│   └── test/                       # 测试脚本
├── docs/                           # Jupyter Notebook 教程
└── requirements.txt
```

### 核心 API

| 接口     | 方法 | 说明                              |
| -------- | ---- | --------------------------------- |
| `/chat`  | POST | 通用聊天，流式 SSE 输出，可选 DeepSeek/Ollama |
| `/reason`| POST | 推理接口，默认使用 Ollama 推理模型 |
| `/search`| POST | 联网搜索增强，先搜索后总结回答    |
| `/health`| GET  | 健康检查 + 当前路由配置（显示各接口走的是 Ollama 还是 API） |

### 架构设计

- **工厂模式**：`LLMFactory` 根据 `.env` 中的 `CHAT_SERVICE` / `REASON_SERVICE` 配置动态选择 DeepSeek 云服务或 Ollama 本地模型
- **流式输出**：所有聊天接口均使用 SSE (Server-Sent Events) 实现流式响应
- **Function Calling**：`SearchService` 利用 DeepSeek 的 tool call 能力，自动调用 SerpAPI 进行联网搜索，再将结果喂给模型生成回答

## 环境要求

- Python 3.11+
- Ollama (可选，如果需要使用本地模型)

## 安装步骤

### 第1步： 创建并激活虚拟环境

### 方式一：使用 Python venv（轻量，推荐纯 Python 项目）

```bash
python -m venv .venv

# Windows（需确保 python3.11 在 PATH 环境变量中）
python -m venv --python python3.11 .venv

# Linux/Mac（同上）
python -m venv --python python3.11 .venv

# 如果是Windows操作系统

# 更改执行策略：
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 激活虚拟环境
.venv\Scripts\activate

# 如果是 Linux/Mac 操作系统
source .venv/bin/activate
```

### 方式二：使用 Conda（推荐数据科学/LLM 项目，跨平台命令统一）

```bash
# 创建 Conda 环境（指定 Python 3.11，环境名称自定，如 ling_xi）
conda create -n ling_xi python=3.11 -y

# 激活环境（Windows / Linux / Mac 通用命令）
conda activate ling_xi

# （可选）如果你偏好将环境建在项目本地 .venv 目录
# conda create --prefix ./.venv python=3.11 -y
# conda activate ./.venv
conda deactivate
```
<hr/>

说明：两种方式任选其一即可。venv 更轻量，适合纯 Python 项目；conda 更强大，能管理
非 Python 依赖（如 CUDA、C++ 库），且激活命令跨平台一致。如果使用 Conda 时 Windows 提示权限错误，
请执行 conda init powershell 并重启终端，无需修改系统执行策略。


2. 安装依赖
```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

4. 创建配置文件
```bash
# 复制示例配置文件，注意， .env 文件需要放在 llm_backend 目录下
cp .env.example .env
```

## 配置说明

创建 `.env` 文件并配置以下内容：

```env
# Deepseek settings
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Ollama settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:1.5b
OLLAMA_REASON_MODEL=deepseek-r1:32b

# Service selection (deepseek or ollama)
CHAT_SERVICE=deepseek
REASON_SERVICE=ollama

# SerpAPI 配置 (搜索增强) , 本期代码没有使用，可以忽略，会在第四期项目中介绍联网检索功能，但需要写上该配置
SERPAPI_KEY=your-serpapi-key
```

配置说明：
- `DEEPSEEK_API_KEY`: Deepseek API 密钥
- `DEEPSEEK_BASE_URL`: Deepseek API 地址
- `DEEPSEEK_MODEL`: Deepseek 模型名称（如 `deepseek-chat`）
- `OLLAMA_BASE_URL`: Ollama 服务地址
- `OLLAMA_CHAT_MODEL`: Ollama 聊天模型名称
- `OLLAMA_REASON_MODEL`: Ollama 推理模型名称
- `CHAT_SERVICE`: 聊天服务类型 (deepseek 或 ollama)
- `REASON_SERVICE`: 推理服务类型 (deepseek 或 ollama)

## 启动服务

```bash
cd llm_backend
# 开发模式
uvicorn main:app --reload --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000
```

服务启动后访问：
- 前端页面：http://localhost:8000/
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health


## 前端项目

本项目配套的前端实现请参考：[My-DeepSeek-Web](https://github.com/MuYuCheney/My-DeepSeek-Web)

前端项目提供了完整的用户界面，支持：
- 智能对话
- Markdown 渲染
- 代码高亮
- 流式输出
- 聊天记录

## 注意事项

1. `.env` 文件包含敏感信息，已添加到 `.gitignore`，不会上传到代码仓库
2. `.venv` 虚拟环境目录也已添加到 `.gitignore`
3. 使用 Ollama 时需要确保 Ollama 服务已启动且可访问
4. 建议在生产环境中配置 CORS 和安全设置

## License

MIT 


```
ollama pull qwen2.5:1.5b
ollama pull deepseek-r1:7b
```