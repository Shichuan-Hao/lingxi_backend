"""
Ollama 本地模型对话服务。

通过 aiohttp 异步 HTTP 客户端调用本地 Ollama 服务，
支持流式（SSE）和非流式两种生成模式。
"""

from typing import List, Dict, AsyncGenerator
import aiohttp
import json
from app.core.config import settings

class OllamaService:
    """Ollama 本地模型对话服务"""

    def __init__(self, model: str | None = None):
        self.base_url = settings.OLLAMA_BASE_URL
        # 模型优先级：传入参数 > 配置文件中的 OLLAMA_CHAT_MODEL
        self.model = model or settings.OLLAMA_CHAT_MODEL

    async def generate_stream(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """流式生成回复，通过 Ollama /api/chat 接口，yield SSE data chunk"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        "keep_alive": -1,
                        "options": {
                            "temperature": 0.7,
                        }
                    }
                ) as response:
                    async for line in response.content:
                        if line:
                            chunk = json.loads(line)
                            if chunk.get("message", {}).get("content"):
                                content = json.dumps(
                                    chunk["message"]["content"],
                                    ensure_ascii=False
                                )
                                yield f"data: {content}\n\n"

        except Exception as e:
            print(f"Stream generation error: {str(e)}")
            raise

    async def generate(self, messages: List[Dict]) -> str:
        """非流式生成回复，一次性返回完整文本"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "keep_alive": -1,
                        "options": {
                            "temperature": 0.7,
                        }
                    }
                ) as response:
                    result = await response.json()
                    return result["message"]["content"]

        except Exception as e:
            print(f"Generation error: {str(e)}")
            raise