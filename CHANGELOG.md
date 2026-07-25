# 更新日志

所有项目的显著变更都将记录在此文件中。


## [v1.0] - 【AssistGen】Ch 1.1 ~ Ch 1.6
### 基础知识
- Ollama 本地部署 DeepSeek R1 模型完整流程
- Ollama REST API 核心接口：api/generate & api/chat
- Ollama 兼容 OpenAI API 接口规范
- Deepseek v3 & R1 在线 API 调用方法


## [v1.1] - 灵犀稳定性与体验优化

### Bug 修复
- 修复 `OllamaService` 初始化参数错误导致的启动失败
- 修复文件上传界面卡死问题（同步阻塞异步事件循环）
- 修复联网搜索返回 Unicode 乱码问题（JSON `ensure_ascii=False`）
- 修复首次启动与热加载日志无法区分的问题（PID 标记文件方案）

### 日志系统优化
- 统一使用 `loguru` → 自定义 `get_logger()` 架构
- 精简冗余日志，按请求-响应结构化输出
- 区分 `/chat` `/reason` `/search` `/upload` 路由，展示对应的本地/云端模型信息
- 流式响应结束后输出摘要，便于追踪对话历史
- 全部日志加入 emoji 标识（💬🧠🔍📁📤❌）
- 启动横幅展示完整路由表及模型配置
- 首次启动 → ✅ 服务启动成功；热加载 → 🔄 服务更新成功

### 服务重构
- `EmbeddingService`：模型懒加载 + `asyncio.to_thread`，支持 PDF/Word/TXT/Markdown
- `SearchService`：异步搜索 + 异常兜底 + 中文 JSON 正常输出
- `RAGService` / `RAGChatService`：适配新版异步 EmbeddingService


### DevOps
- 配置 HuggingFace 国内镜像 (`HF_ENDPOINT`) 加速模型下载
- uvicorn 原生日志屏蔽 (`access_log=False, log_level="error"`)
- 启动标记文件 `.lingxi_startup_marker` 加入 `.gitignore`