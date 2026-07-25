"""
聊天相关数据模型（Pydantic）。

定义 API 请求体的数据结构，FastAPI 自动进行请求校验和序列化。
"""

from pydantic import BaseModel
from typing import List, Dict

class ChatRequest(BaseModel):
    """通用聊天请求体，包含标准对话消息列表"""
    messages: List[Dict[str, str]]