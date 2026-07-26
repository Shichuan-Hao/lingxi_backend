from typing import List, Dict, AsyncGenerator, Optional, Callable
import json
import asyncio
from app.tools.search import SearchTool
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logger import get_logger
from app.tools.definitions import SEARCH_TOOL, TOOL_DEFINITIONS
from app.services.function_tools import ToolRegistry, FunctionTool
from app.prompts.search_prompts import SEARCH_SYSTEM_PROMPT, SEARCH_SUMMARY_PROMPT
from datetime import datetime

logger = get_logger(service="search")

class SearchService:
    def __init__(self):
        logger.info("Initializing SearchService...")
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL
        self.search_tool = SearchTool()  # 检索工具
        
        # 初始化工具注册中心，统一的工具中心，集成多个
        self.tool_registry = ToolRegistry()
        
        # 注册搜索工具 - 直接使用定义好的描述
        self.tool_registry.register(FunctionTool(
            **SEARCH_TOOL,  # 展开工具定义 jsonSCHEAM
            handler=self._handle_search
        ))
        
        # 生成工具描述提示
        self.tools_description = self._generate_tools_description()

    def _generate_tools_description(self) -> str:
        """根据工具定义生成工具描述提示"""
        tool_descriptions = []
        
        for tool_def in self.tool_registry.get_tools_definition():
            func = tool_def["function"]
            name = func["name"]
            desc = func["description"]
            params = []
            
            # 获取必需参数及其描述
            for param_name, param_info in func["parameters"]["properties"].items():
                if param_name in func["parameters"].get("required", []):
                    params.append(f"{param_name}，作用是：{param_info['description']}")
            
            tool_desc = (
                f"{name}，{desc}"
                f"{'，必须解析出来的参数是：' if params else ''}"
                f"{', '.join(params)}"
            )
            tool_descriptions.append(tool_desc)
        
        return (
            "你现在可用的工具有：\n\n" + 
            "\n".join(tool_descriptions)
        )

    async def _handle_search(self, query: str) -> List[Dict]:
        """处理搜索请求"""
        return await asyncio.to_thread(self.search_tool.search, query)

    async def _call_with_tool(self, query: str) -> Dict:
        """调用模型并获取工具调用结果"""
        try:
            logger.info(f"Calling model with query: {query}")
            logger.info(f"Messages: {query}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=query,
                tools=self.tool_registry.get_tools_definition(),
                tool_choice="auto"  # 让模型自己决定是否使用工具
            )
            
            logger.info(f"Model response: {response.choices[0]}")
            return response.choices[0]
            
        except Exception as e:
            logger.error(f"Error in _call_with_tool: {str(e)}", exc_info=True)
            raise

    async def generate_stream(
        self, 
        query: str,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        on_complete: Optional[Callable] = None
    ) -> AsyncGenerator[str, None]:
        """流式生成带搜索功能的回复"""
        try:
            logger.info(f"Starting search generation for query: {query}")
            
            # 使用格式化的系统提示
            messages = [
                {
                    "role": "system",
                    "content": SEARCH_SYSTEM_PROMPT.format(
                        tools_description=self.tools_description
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            # 第一步：获取工具调用
            choice = await self._call_with_tool(messages)
            logger.info(f"Tool call response: {choice}")
            
            # 根据finish_reason决定处理方式
            if choice.finish_reason == "tool_calls":
                # 需要搜索的情况
                tool_calls = choice.message.tool_calls
                if tool_calls:
                    tool_call = tool_calls[0]
                    logger.info(f"Processing tool call: {tool_call}")
                    
                    # 先返回一个类型标识，告诉前端搜索已开始（避免前端一直卡住）
                    yield f"data: {json.dumps({'type': 'search_start'}, ensure_ascii=False)}\n\n"
                    
                    search_results = []
                    try:
                        # 执行工具调用，设置总超时，避免同步请求长时间阻塞
                        search_results = await asyncio.wait_for(
                            self.tool_registry.execute_tool(
                                tool_call.function.name,
                                tool_call.function.arguments
                            ),
                            timeout=getattr(settings, "SEARCH_TIMEOUT", 8) + 3  # 比底层 timeout 多 3 秒缓冲
                        )
                        logger.info(f"Got {len(search_results)} search results")
                    except asyncio.TimeoutError:
                        logger.warning(f"Search timeout for query: {query}")
                        yield f"data: {json.dumps({'type': 'search_error', 'message': '搜索超时，已自动切换为直接回答'}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.error(f"Search tool error: {str(e)}", exc_info=True)
                        yield f"data: {json.dumps({'type': 'search_error', 'message': '搜索服务暂不可用，已自动切换为直接回答'}, ensure_ascii=False)}\n\n"
                    
                    if search_results:
                        # 构建上下文内容
                        context = []
                        for result in search_results:
                            context.append(
                                f"来源：{result['title']}\n"
                                f"链接：{result['url']}\n"
                                f"内容：{result['snippet']}\n"
                            )
                        
                        # 构造带上下文的提示
                        context_prompt = SEARCH_SUMMARY_PROMPT.format(
                            context="\n---\n".join(context),
                            query=query,
                            cur_date=datetime.now().strftime("%Y年%m月%d日")
                        )
                        
                        # 返回搜索结果
                        search_data = {
                            "type": "search_results",  # 保持原有的类型标识
                            "total": len(search_results),
                            "query": json.loads(tool_call.function.arguments)["query"],
                            "results": [
                                {
                                    "title": result["title"],
                                    "url": result["url"],
                                    "snippet": result["snippet"]
                                }
                                for result in search_results
                            ]
                        }
                        yield f"data: {json.dumps(search_data, ensure_ascii=False)}\n\n"
                        
                        # 使用新的消息上下文生成回复
                        async for chunk in await self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": context_prompt}
                            ],
                            stream=True
                        ):      

                            if chunk.choices[0].delta.content:
                                content = json.dumps(chunk.choices[0].delta.content, ensure_ascii=False)
                                yield f"data: {content}\n\n"
                    else:
                        # 搜索失败或结果为空，降级为直接回答
                        logger.info("Search failed or returned empty, falling back to direct answer")
                        async for chunk in await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            stream=True
                        ):
                            if chunk.choices and chunk.choices[0].delta.content:
                                content = chunk.choices[0].delta.content
                                data = json.dumps({
                                    'type': 'direct_content',
                                    'content': content,
                                }, ensure_ascii=False)
                                yield f"data: {data}\n\n"
                
            elif choice.finish_reason == "stop":
                # 直接回答的情况，使用流式响应
                logger.info("Model chose to answer directly, streaming response...")
                
                # 先返回一个类型标识，告诉前端这是直接回答
                yield f"data: {json.dumps({'type': 'direct_answer'}, ensure_ascii=False)}\n\n"
                
                # 使用流式API重新生成回答
                stream_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True
                )
                
                full_response = []
                async for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response.append(content)
                        # 包装直接回答的内容
                        # yield f"data: {json.dumps({
                        #     'type': 'direct_content',
                        #     'content': content
                        # }, ensure_ascii=False)}\n\n"
                        data = json.dumps({
                                'type': 'direct_content',
                                'content': content,
                            }, ensure_ascii=False)
                        yield f"data: {data}\n\n"
                
                # 如果需要保存对话
                if on_complete and user_id is not None and conversation_id is not None:
                    complete_response = "".join(full_response)
                    await on_complete(user_id, conversation_id, [{"role": "user", "content": query}], complete_response)
                
        except Exception as e:
            logger.error(f"Error in generate_stream: {str(e)}", exc_info=True)
            raise