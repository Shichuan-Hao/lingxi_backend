"""
联网搜索服务。

先通过 SerpAPI 进行网络搜索获取实时信息，
再将搜索结果结合用户问题交给 Deepseek 生成流式回答。
"""
import asyncio
import json as _json
from typing import AsyncGenerator
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logger import get_logger
from app.tools.search import SearchTool

logger = get_logger(service="search")


class SearchService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
        self.model = settings.DEEPSEEK_MODEL
        self.search_count = settings.SEARCH_RESULT_COUNT or 3
        self.search_tool = SearchTool()

    async def generate_stream(self, query: str) -> AsyncGenerator[str, None]:
        """联网搜索 + 流式生成回答"""
        try:
            # 1. 执行搜索（放到线程池，避免同步 requests 阻塞事件循环）
            logger.info(f"\U0001f50d 开始搜索: {query}")
            search_results = await asyncio.to_thread(
                self.search_tool.search, query, self.search_count
            )
            logger.info(f"\U0001f4ca 搜索结果数: {len(search_results)}")

            # 2. 构建提示词
            system_prompt = (
                "你是一个智能助手。请根据搜索结果回答用户问题。"
                "如果搜索结果为空或不足，请基于你的知识诚实回答。"
                "不要编造不存在的信息。"
            )

            if search_results:
                context = "\n\n".join(
                    f"[{i+1}] {item.get('title', '')}\n{item.get('snippet', '')}\nURL: {item.get('url', '')}"
                    for i, item in enumerate(search_results)
                )
                user_prompt = f"用户问题：{query}\n\n搜索结果：\n{context}\n\n请根据以上搜索结果回答。"
            else:
                user_prompt = f"用户问题：{query}\n\n（未获取到有效搜索结果，请基于你的知识回答）"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # 3. 流式生成回答
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.7,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    # ensure_ascii=False 保持中文字符原样输出
                    yield f"data: {_json.dumps(content, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"\u274c 搜索/生成失败: {str(e)}", exc_info=True)
            error_msg = "联网搜索暂时不可用，让我基于已有知识回答您的问题。"
            yield f"data: {_json.dumps(error_msg, ensure_ascii=False)}\n\n"

            # 尽量再给一个兜底回答
            fallback_msg = (
                "关于您的问题，目前无法通过联网获取最新信息。"
                "建议您直接访问权威网站查询最新数据。"
            )
            yield f"data: {_json.dumps(fallback_msg, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
