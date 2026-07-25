"""
API v1 聊天路由模块（规划中）。

使用 FastAPI APIRouter 组织路由，支持版本化管理。
当前为 v1 版本的占位实现，后续可添加路由前缀和中间件。
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.deepseek_service import DeepseekService
from app.models.chat import ChatRequest

router = APIRouter()
llm_service = DeepseekService()

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """v1 聊天接口 - 使用 DeepSeek 服务流式返回"""
    try:
        return StreamingResponse(
            llm_service.generate_stream(request.messages),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))