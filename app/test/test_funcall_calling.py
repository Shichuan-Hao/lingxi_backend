"""
DeepSeek Function Calling 测试脚本。

验证 DeepSeek 模型的工具调用（tool call）能力，
以天气查询为例，演示完整 function calling 流程：
发送消息 → 模型返回工具调用 → 执行函数 → 将结果传回模型 → 生成最终回复。
"""

from openai import OpenAI

def send_messages(messages):
    """发送消息到 DeepSeek，附带 tools 定义"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=tools
    )
    return response.choices[0].message

client = OpenAI(
    api_key="<your api key>",
    base_url="https://api.deepseek.com",
)

# 定义可调用的工具函数
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather of an location, the user shoud supply a location first",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    }
                },
                "required": ["location"]
            },
        }
    },
]

messages = [{"role": "user", "content": "How's the weather in Hangzhou?"}]
message = send_messages(messages)
print(f"User>\t {messages[0]['content']}")

tool = message.tool_calls[0]
messages.append(message)

messages.append({"role": "tool", "tool_call_id": tool.id, "content": "24℃"})
message = send_messages(messages)
print(f"Model>\t {message.content}")