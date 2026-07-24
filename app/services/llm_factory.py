import logging

from app.core.config import settings, ServiceType
from app.services.deepseek_service import DeepseekService
from app.services.ollama_service import OllamaService

logger = logging.getLogger("lingxi")

class LLMFactory:
    @staticmethod
    def create_chat_service():
        """创建聊天服务"""
        if settings.CHAT_SERVICE == ServiceType.DEEPSEEK:
            logger.info(f"[路由] /chat -> 云端API | 服务: deepseek | 模型: {settings.DEEPSEEK_MODEL}")
            return DeepseekService()
        else:
            logger.info(f"[路由] /chat -> 本地模型 | 服务: ollama | 模型: {settings.OLLAMA_CHAT_MODEL}")
            return OllamaService(model=settings.OLLAMA_CHAT_MODEL)

    @staticmethod
    def create_reasoner_service():
        """创建推理服务"""
        if settings.REASON_SERVICE == ServiceType.DEEPSEEK:
            logger.info(f"[路由] /reason -> 云端API | 服务: deepseek | 模型: {settings.DEEPSEEK_MODEL}")
            return DeepseekService()
        else:
            logger.info(f"[路由] /reason -> 本地模型 | 服务: ollama | 模型: {settings.OLLAMA_REASON_MODEL}")
            return OllamaService(model=settings.OLLAMA_REASON_MODEL) 