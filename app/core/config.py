"""
应用配置管理模块。

使用 pydantic-settings 从 .env 文件加载配置，提供类型安全的配置访问。
支持 DeepSeek 云端 API 和 Ollama 本地模型两种服务后端。
"""

from pydantic_settings import BaseSettings
from enum import Enum

class ServiceType(str, Enum):
    """服务类型枚举：deepseek（云端 API）或 ollama（本地模型）"""
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"

class Settings(BaseSettings):
    """应用配置，从 .env 文件自动加载"""

    # DeepSeek 云端 API 配置
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_MODEL: str

    # Ollama 本地模型配置
    OLLAMA_BASE_URL: str
    OLLAMA_CHAT_MODEL: str
    OLLAMA_REASON_MODEL: str

    # 服务路由选择：chat/reason 接口分别走哪个服务
    CHAT_SERVICE: ServiceType = ServiceType.DEEPSEEK
    REASON_SERVICE: ServiceType = ServiceType.OLLAMA

    # 搜索引擎 API 密钥
    SERPAPI_KEY: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# 全局单例配置对象
settings = Settings()