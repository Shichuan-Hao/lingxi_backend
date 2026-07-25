"""
LLM 服务工厂模块。

根据配置文件中的 CHAT_SERVICE / REASON_SERVICE 设置，
动态创建 DeepSeek（云端 API）或 Ollama（本地模型）服务实例，
实现零代码切换路由。
"""

import logging

from app.core.config import settings, ServiceType
from app.services.deepseek_service import DeepseekService
from app.services.ollama_service import OllamaService

logger = logging.getLogger("lingxi")

class LLMFactory:
    """LLM 服务工厂，根据配置动态选择服务后端"""

    @staticmethod
    def create_chat_service():
        """创建聊天服务实例，路由由 CHAT_SERVICE 环境变量决定"""
        if settings.CHAT_SERVICE == ServiceType.DEEPSEEK:
            logger.info(f"[路由] /chat -> 云端API | 服务: deepseek | 模型: {settings.DEEPSEEK_MODEL}")
            return DeepseekService()
        else:
            logger.info(f"[路由] /chat -> 本地模型 | 服务: ollama | 模型: {settings.OLLAMA_CHAT_MODEL}")
            return OllamaService(model=settings.OLLAMA_CHAT_MODEL)

    @staticmethod
    def create_reasoner_service():
        """创建推理服务实例，路由由 REASON_SERVICE 环境变量决定"""
        if settings.REASON_SERVICE == ServiceType.DEEPSEEK:
            logger.info(f"[路由] /reason -> 云端API | 服务: deepseek | 模型: {settings.DEEPSEEK_MODEL}")
            return DeepseekService()
        else:
            logger.info(f"[路由] /reason -> 本地模型 | 服务: ollama | 模型: {settings.OLLAMA_REASON_MODEL}")
            return OllamaService(model=settings.OLLAMA_REASON_MODEL)