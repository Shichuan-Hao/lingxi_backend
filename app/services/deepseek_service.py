"""
DeepSeek 云端 API 对话服务。

通过 AsyncOpenAI 客户端调用 DeepSeek 云端大模型，
支持流式（SSE）和非流式两种生成模式。
"""

from typing import List, Dict, AsyncGenerator
from openai import AsyncOpenAI
from app.core.config import settings
import json

class DeepseekService:
    """DeepSeek 云端 API 对话服务"""

    def __init__(self, model: str = "deepseek-chat"):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        # 模型优先级：传入参数 > 配置文件 > 默认值 "deepseek-chat"
        self.model = settings.DEEPSEEK_MODEL or model

    async def generate_stream(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """流式生成回复，yield 为 SSE 格式的 data chunk"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = json.dumps(chunk.choices[0].delta.content, ensure_ascii=False)
                    yield f"data: {content}\n\n"
        except Exception as e:
            print(f"Stream generation error: {str(e)}")
            raise

    async def generate(self, messages: List[Dict]) -> str:
        """非流式生成回复，一次性返回完整文本"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Generation error: {str(e)}")
            raise