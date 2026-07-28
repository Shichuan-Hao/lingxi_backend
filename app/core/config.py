import os
from pydantic_settings import BaseSettings
from enum import Enum
from pathlib import Path

# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

class ServiceType(str, Enum):
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"

class Settings(BaseSettings):
    # Deepseek settings
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_MODEL: str
    
    # Vision Model settings (独立配置)
    VISION_API_KEY: str
    VISION_BASE_URL: str
    VISION_MODEL: str
    
    # Ollama settings
    OLLAMA_BASE_URL: str
    OLLAMA_CHAT_MODEL: str
    OLLAMA_REASON_MODEL: str
    OLLAMA_EMBEDDING_MODEL: str
    OLLAMA_AGENT_MODEL: str
    # Service selection
    CHAT_SERVICE: ServiceType = ServiceType.DEEPSEEK
    REASON_SERVICE: ServiceType = ServiceType.OLLAMA
    AGENT_SERVICE: ServiceType = ServiceType.DEEPSEEK
    
    # Search settings
    SERPAPI_KEY: str
    SEARCH_RESULT_COUNT: int = 3
    
    # Database settings
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    
    # Neo4j settings
    NEO4J_URL: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    
    # JWT settings
    SECRET_KEY: str = "your-secret-key"  # 在生产环境中使用安全的密钥
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis settings
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_CACHE_EXPIRE: int = 3600
    REDIS_CACHE_THRESHOLD: float = 0.8
    
    # Embedding settings 
    EMBEDDING_TYPE: str = "ollama"  # ollama 或 sentence_transformer
    EMBEDDING_MODEL: str = "bge-m3"  # ollama embedding模型
    EMBEDDING_THRESHOLD: float = 0.90  # 语义相似度阈值
    
    # GraphRAG settings
    GRAPHRAG_PROJECT_DIR: str = str(ROOT_DIR / "app" / "graphrag")  # GraphRAG项目目录（默认=项目根目录/app/graphrag）
    GRAPHRAG_DATA_DIR: str = "data"                         # 数据目录名称
    GRAPHRAG_QUERY_TYPE: str = "local"                      # 查询类型
    GRAPHRAG_RESPONSE_TYPE: str = "text"                    # 响应类型
    GRAPHRAG_COMMUNITY_LEVEL: int = 3                       # 社区级别
    GRAPHRAG_DYNAMIC_COMMUNITY: bool = False                # 是否动态选择社区
    
    # GraphRAG settings.yaml 中引用的环境变量（graphrag 的 load_config 直读 os.environ）
    GRAPHRAG_API_BASE: str = ""          # LLM API 地址（默认取 DEEPSEEK_BASE_URL）
    GRAPHRAG_API_KEY: str = ""           # LLM API 密钥（默认取 DEEPSEEK_API_KEY）
    GRAPHRAG_MODEL_NAME: str = ""        # LLM 模型名（默认取 DEEPSEEK_MODEL）
    Embedding_API_BASE: str = ""         # Embedding API 地址（默认取 DEEPSEEK_BASE_URL）
    Embedding_API_KEY: str = ""          # Embedding API 密钥（默认取 DEEPSEEK_API_KEY）
    Embedding_MODEL_NAME: str = ""       # Embedding 模型名（默认 text-embedding-3-small）
    
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def REDIS_URL(self) -> str:
        """构建Redis URL"""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def NEO4J_CONN_URL(self) -> str:
        """构建Neo4j连接URL"""
        return f"{self.NEO4J_URL}"
    
    class Config:
        env_file = str(ENV_FILE)  # 使用绝对路径
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()

# ============================================================
# 将 GraphRAG settings.yaml 需要的变量注入 os.environ
# graphrag 的 load_config() 直接从系统环境变量读取 ${VAR} 占位符，
# 而 pydantic-settings 只填充 Python 对象，不会写入 os.environ，
# 所以这里需要手动桥接一次。
# ============================================================
_GRAPH_LLM = {
    "GRAPHRAG_API_BASE": settings.GRAPHRAG_API_BASE or settings.DEEPSEEK_BASE_URL,
    "GRAPHRAG_API_KEY": settings.GRAPHRAG_API_KEY or settings.DEEPSEEK_API_KEY,
    "GRAPHRAG_MODEL_NAME": settings.GRAPHRAG_MODEL_NAME or settings.DEEPSEEK_MODEL,
}
_GRAPH_EMBEDDING = {
    "Embedding_API_BASE": settings.Embedding_API_BASE or settings.DEEPSEEK_BASE_URL,
    "Embedding_API_KEY": settings.Embedding_API_KEY or settings.DEEPSEEK_API_KEY,
    "Embedding_MODEL_NAME": settings.Embedding_MODEL_NAME or "text-embedding-3-small",
}
for _d in (_GRAPH_LLM, _GRAPH_EMBEDDING):
    for _k, _v in _d.items():
        if _v:  # 只注入有值的，避免覆盖用户已在 shell 中 export 的值
            os.environ.setdefault(_k, _v)