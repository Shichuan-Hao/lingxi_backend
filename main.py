import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
from app.core.config import settings
from app.services.llm_factory import LLMFactory
from app.services.search_service import SearchService

from fastapi.staticfiles import StaticFiles

# 配置标准库 logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
FILE_FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
CONSOLE_FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

# 文件 handler（按大小滚动，保留 7 个备份）
file_handler = RotatingFileHandler(
    LOG_DIR / "lingxi.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=7,
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(FILE_FORMATTER)

# 控制台 handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(CONSOLE_FORMATTER)

# 应用日志
logger = logging.getLogger("lingxi")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

app = FastAPI(title="灵犀接口文档")


@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("灵犀服务启动 - 当前路由配置：")
    chat_svc = settings.CHAT_SERVICE.value
    chat_model = settings.DEEPSEEK_MODEL if chat_svc == "deepseek" else settings.OLLAMA_CHAT_MODEL
    logger.info(f"  /chat   -> {chat_svc:8} | 模型: {chat_model}")
    reason_svc = settings.REASON_SERVICE.value
    reason_model = settings.DEEPSEEK_MODEL if reason_svc == "deepseek" else settings.OLLAMA_REASON_MODEL
    logger.info(f"  /reason -> {reason_svc:8} | 模型: {reason_model}")
    logger.info(f"  /search -> deepseek | 模型: deepseek-ai/DeepSeek-V3")
    logger.info("=" * 50)


# CORS设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中要设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReasonRequest(BaseModel):
    messages: List[Dict[str, str]]


class ChatMessage(BaseModel):
    messages: List[Dict[str, str]]


@app.post("/chat")
async def chat_endpoint(request: ChatMessage):
    """聊天接口"""
    try:
        chat_service = LLMFactory.create_chat_service()

        return StreamingResponse(
            chat_service.generate_stream(request.messages),
            media_type="text/event-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reason")
async def reason_endpoint(request: ReasonRequest):
    """推理接口"""
    try:
        reasoner = LLMFactory.create_reasoner_service()

        return StreamingResponse(
            reasoner.generate_stream(request.messages),
            media_type="text/event-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search_endpoint(request: ChatMessage):
    """带搜索功能的聊天接口"""
    try:
        search_service = SearchService()
        return StreamingResponse(
            search_service.generate_stream(request.messages[0]["content"]),
            media_type="text/event-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "routing": {
            "chat": {
                "service": settings.CHAT_SERVICE.value,
                "model": settings.DEEPSEEK_MODEL if settings.CHAT_SERVICE == "deepseek" else settings.OLLAMA_CHAT_MODEL,
            },
            "reason": {
                "service": settings.REASON_SERVICE.value,
                "model": settings.DEEPSEEK_MODEL if settings.REASON_SERVICE == "deepseek" else settings.OLLAMA_REASON_MODEL,
            },
            "search": {
                "service": "deepseek",
                "model": "deepseek-ai/DeepSeek-V3",
            },
        },
    }


app.mount("/", StaticFiles(directory="static/dist", html=True), name="static")