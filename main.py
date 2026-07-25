"""
灵犀 FastAPI 应用主入口。

定义所有 API 路由和静态文件挂载，包括：
- /chat      普通对话
- /reason    深度推理
- /search    联网搜索
- /upload    文件上传(RAG)
- /chat-rag  文档问答
- /api/*     用户认证
- /health    健康检查
"""
import json as _json
import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, AsyncGenerator
from app.services.llm_factory import LLMFactory
from app.services.search_service import SearchService

from fastapi.staticfiles import StaticFiles
from datetime import datetime
from pathlib import Path
from app.services.rag_service import RAGService
from app.services.rag_chat_service import RAGChatService
from app.core.logger import get_logger
from app.core.middleware import LoggingMiddleware
from app.core.config import settings
from app.api import api_router


# 配置上传目录 - RAG 功能的
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# logger 变量就被初始化为一个日志记录器实例。
# 之后，便可以在当前文件中直接使用 logger.info()、logger.error() 等方法来记录日志，而不需要进行其他操作。
logger = get_logger(service="main")

# 创建 FastAPI 应用实例
app = FastAPI(title="灵犀 REST API")

# 添加日志中间件， 使用 LoggingMiddleware 来统一处理日志记录，从而替代 FastAPI 的原生打印日志。
app.add_middleware(LoggingMiddleware)

# CORS设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中要设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. 用户注册、登录路由通过 api_router 路由挂载到 /api 前缀
app.include_router(api_router, prefix="/api")

class ReasonRequest(BaseModel):
    messages: List[Dict[str, str]]

class ChatMessage(BaseModel):
    messages: List[Dict[str, str]]

class RAGChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    index_id: str

# 用于区分首次启动与 uvicorn 热加载：通过父进程 PID 判断是否为同一轮运行
# uvicorn 热加载时父进程（reload supervisor）保持不变，仅工作进程被替换
STARTUP_MARKER = Path(__file__).parent / ".lingxi_startup_marker"


def _is_hot_reload() -> bool:
    """若标记文件存在且记录的父进程 PID 与当前一致，则判定为热加载。"""
    if not STARTUP_MARKER.exists():
        return False
    try:
        stored_ppid = int(STARTUP_MARKER.read_text(encoding="utf-8").strip())
        return stored_ppid == os.getppid()
    except Exception:
        return False


@app.on_event("startup")
async def startup_event():
    if _is_hot_reload():
        logger.info("\U0001f504 服务更新成功！")
    else:
        logger.info("\u2705 服务启动成功！访问: http://localhost:8000")
        try:
            STARTUP_MARKER.write_text(str(os.getppid()), encoding="utf-8")
        except Exception:
            pass


# ---------- 辅助函数 ----------
async def logged_stream(generator: AsyncGenerator[str, None], logger, label: str = ""):
    """包装流式生成器，完成后记录响应摘要"""
    parts = []
    async for chunk in generator:
        if chunk.startswith("data: ") and len(chunk) > 6:
            try:
                text = _json.loads(chunk[6:].strip())
                if isinstance(text, str):
                    parts.append(text)
            except Exception:
                pass
        yield chunk
    if parts:
        summary = "".join(parts)[:200]
        if label:
            logger.info(f"\U0001f4e4 {label}: {summary}{'...' if len(summary) >= 200 else ''}")


# ---------- API 路由 ----------
@app.post("/chat")
async def chat_endpoint(request: ChatMessage):
    """聊天接口"""
    try:
        # 确定使用的服务和模型
        if settings.CHAT_SERVICE == "deepseek":
            service_info = f"云端API({settings.DEEPSEEK_MODEL})"
        else:
            service_info = f"本地Ollama({settings.OLLAMA_CHAT_MODEL})"

        last_msg = request.messages[-1]["content"] if request.messages else ""
        logger.info(f"\U0001f4ac Chat | {service_info} | 请求: {last_msg[:80]}{'...' if len(last_msg) > 80 else ''}")

        logger.info("Processing chat request")
        chat_service = LLMFactory.create_chat_service()
        return StreamingResponse(
            logged_stream(chat_service.generate_stream(request.messages), logger, "Chat响应"),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"\u274c Chat 失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reason")
async def reason_endpoint(request: ReasonRequest):
    """推理接口"""
    try:
        if settings.REASON_SERVICE == "deepseek":
            service_info = f"云端API({settings.DEEPSEEK_MODEL})"
        else:
            service_info = f"本地Ollama({settings.OLLAMA_REASON_MODEL})"

        last_msg = request.messages[-1]["content"] if request.messages else ""
        logger.info(f"\U0001f9e0 Reason | {service_info} | 请求: {last_msg[:80]}{'...' if len(last_msg) > 80 else ''}")

        reasoner = LLMFactory.create_reasoner_service()
        return StreamingResponse(
            logged_stream(reasoner.generate_stream(request.messages), logger, "Reason响应"),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"\u274c Reason 失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search_endpoint(request: ChatMessage):
    """带搜索功能的聊天接口"""
    try:
        service_info = f"云端API({settings.DEEPSEEK_MODEL})"
        query = request.messages[-1]["content"] if request.messages else ""
        logger.info(f"\U0001f50d Search | {service_info} | 请求: {query[:80]}{'...' if len(query) > 80 else ''}")

        search_service = SearchService()
        return StreamingResponse(
            logged_stream(search_service.generate_stream(query), logger, "Search响应"),
            media_type="text/event-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并准备 RAG 处理"""
    try:
        # 生成唯一的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        file_path = UPLOAD_DIR / filename
        
        # 确保上传目录存在
        UPLOAD_DIR.mkdir(exist_ok=True)
        
        # 保存文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        # 获取文件类型
        file_type = file.content_type
        
        logger.info(f"\U0001f4c1 Upload | 已保存: {file.filename} ({len(content)} bytes)")
        
        # 返回文件信息
        file_info = {
            "filename": filename,
            "original_name": file.filename,
            "size": len(content),
            "type": file_type,
            "path": str(file_path).replace('\\', '/'),
        }
        
        # 初始化 RAG 服务
        rag_service = RAGService()
        # 初始化 RAG 处理
        rag_result = await rag_service.process_file(file_info)
        
        if rag_result.get("status") == "error":
            logger.error(f"\u274c Upload | RAG 处理失败: {rag_result.get('error')}")
            raise HTTPException(status_code=500, detail=rag_result.get("error"))
        
        logger.info(f"\u2705 Upload | 索引创建成功: {rag_result.get('index_id')}, 分块数: {rag_result.get('chunks')}")
        
        # 合并结果
        result = {**file_info, **rag_result}
        return result
        
    except Exception as e:
        logger.error(f"\u274c Upload 失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat-rag")
async def rag_chat_endpoint(request: RAGChatRequest):
    """基于文档的问答接口"""
    try:
        rag_chat_service = RAGChatService()
        
        return StreamingResponse(
            rag_chat_service.generate_stream(
                request.messages,
                request.index_id
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 最后挂载静态文件，并确保使用绝对路径
STATIC_DIR = Path(__file__).parent / "static" / "dist"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
