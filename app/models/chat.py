"""
聊天请求/响应 Pydantic 数据模型。

定义 Chat 和 Reason 两个端点的请求体结构，
作为 FastAPI 接口的输入校验模型。
"""
from pydantic import BaseModel
from typing import List, Dict

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]] 