"""
灵犀（Lingxi）智能客服后端服务入口。

本模块负责：
- 创建 FastAPI 应用并注册所有路由（/chat、/reason、/search、/health）
- 配置日志（控制台 + 文件滚动输出）
- 配置 CORS 中间件
- 挂载前端静态文件
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict
import aiohttp
import asyncio
from app.core.config import settings, ServiceType
from app.services.llm_factory import LLMFactory
from app.services.search_service import SearchService

from fastapi.staticfiles import StaticFiles

# 配置标准库 logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 日志格式：文件使用完整时间，控制台使用短时间
FILE_FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
CONSOLE_FORMATTER = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

# 文件 handler：按大小滚动（10MB），保留 7 个备份
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

# 应用日志器
logger = logging.getLogger("lingxi")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

app = FastAPI(title="灵犀接口文档")


@app.on_event("startup")
async def startup():
    """启动事件：打印当前路由配置总览"""
    logger.info("=" * 50)
    logger.info("灵犀服务启动 - 当前路由配置：")
    chat_svc = settings.CHAT_SERVICE.value
    chat_model = settings.DEEPSEEK_MODEL if chat_svc == "deepseek" else settings.OLLAMA_CHAT_MODEL
    logger.info(f"  普通对话 /chat   -> {chat_svc:8} | 模型: {chat_model}")
    reason_svc = settings.REASON_SERVICE.value
    reason_model = settings.DEEPSEEK_MODEL if reason_svc == "deepseek" else settings.OLLAMA_REASON_MODEL
    logger.info(f"  深度推理 /reason -> {reason_svc:8} | 模型: {reason_model}")
    logger.info(f"  联网搜索 /search -> deepseek | 模型: deepseek-ai/DeepSeek-V3")
    logger.info("=" * 50)


# CORS 中间件配置（生产环境应限制具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReasonRequest(BaseModel):
    """推理接口请求体"""
    messages: List[Dict[str, str]]


class ChatMessage(BaseModel):
    """聊天接口请求体"""
    messages: List[Dict[str, str]]


@app.post("/chat")
async def chat_endpoint(request: ChatMessage):
    """聊天接口 - 流式 SSE 输出，路由由 CHAT_SERVICE 配置决定"""
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
    """推理接口 - 流式 SSE 输出，路由由 REASON_SERVICE 配置决定"""
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
    """联网搜索增强聊天接口 - 先搜索后总结，流式 SSE 输出"""
    try:
        search_service = SearchService()
        return StreamingResponse(
            search_service.generate_stream(request.messages[0]["content"]),
            media_type="text/event-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _check_ollama_model(base_url: str, model_name: str, timeout: int = 5) -> dict:
    """检测 Ollama 服务是否在线，以及指定模型是否已拉取。

    Args:
        base_url: Ollama 服务地址，如 http://localhost:11434
        model_name: 要检测的模型名，如 qwen2.5:7b
        timeout: 请求超时秒数

    Returns:
        dict with keys: reachable (bool), model_available (bool), error (str|None)
    """
    result = {"reachable": False, "model_available": False, "error": None}
    try:
        async with aiohttp.ClientSession() as session:
            # 第一步：检查 Ollama 服务是否可达
            async with session.get(f"{base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    result["error"] = f"Ollama 返回状态码 {resp.status}"
                    return result
                data = await resp.json()

            result["reachable"] = True

            # 第二步：检查目标模型是否在模型列表中
            models = [m.get("name", "") for m in data.get("models", [])]
            # 模型名可能有 :latest 后缀，做前缀匹配
            for available in models:
                if available == model_name or available.startswith(model_name + ":"):
                    result["model_available"] = True
                    break

            if not result["model_available"]:
                result["error"] = f"模型 {model_name} 未找到，可用模型: {models[:5]}{'...' if len(models) > 5 else ''}"

    except asyncio.TimeoutError:
        result["error"] = f"连接超时 ({timeout}s)"
    except aiohttp.ClientConnError:
        result["error"] = "无法连接到 Ollama 服务"
    except Exception as e:
        result["error"] = str(e)

    return result


@app.get("/health")
async def health_check():
    """健康检查 - 返回各接口路由配置，并实时检测本地 Ollama 模型状态"""
    routing: dict[str, dict] = {}

    # Chat 路由
    chat_entry: dict = {
        "service": settings.CHAT_SERVICE.value,
        "model": settings.DEEPSEEK_MODEL if settings.CHAT_SERVICE == ServiceType.DEEPSEEK else settings.OLLAMA_CHAT_MODEL,
    }
    if settings.CHAT_SERVICE == ServiceType.OLLAMA:
        chat_entry["ollama_status"] = await _check_ollama_model(
            settings.OLLAMA_BASE_URL, settings.OLLAMA_CHAT_MODEL
        )
    routing["chat"] = chat_entry

    # Reason 路由
    reason_entry: dict = {
        "service": settings.REASON_SERVICE.value,
        "model": settings.DEEPSEEK_MODEL if settings.REASON_SERVICE == ServiceType.DEEPSEEK else settings.OLLAMA_REASON_MODEL,
    }
    if settings.REASON_SERVICE == ServiceType.OLLAMA:
        reason_entry["ollama_status"] = await _check_ollama_model(
            settings.OLLAMA_BASE_URL, settings.OLLAMA_REASON_MODEL
        )
    routing["reason"] = reason_entry

    # Search 路由
    routing["search"] = {
        "service": "deepseek",
        "model": "deepseek-ai/DeepSeek-V3",
    }

    return {"status": "ok", "routing": routing}


# 挂载前端静态文件 SPA
app.mount("/", StaticFiles(directory="static/dist", html=True), name="static")