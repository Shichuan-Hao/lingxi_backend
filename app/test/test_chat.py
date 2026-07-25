"""
DeepSeek 对话对比测试脚本。

分别测试同步（非流式）和流式两种模式的聊天效果，仅用于开发调试。
"""

from openai import OpenAI

# 测试用 API 密钥（请替换为实际密钥）
API_KEY = "sk-fb7369c51357447d9bfa082b012346d4"
BASE_URL = "https://api.deepseek.com/v1"

def test_sync():
    """同步模式测试：一次性获取完整回复"""
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一位乐于助人的智能小助手"},
            {"role": "user", "content": "你好，请你介绍一下你自己。"},
        ],
        stream=False
    )

    print(response.choices[0].message.content)

def test_stream():
    """流式模式测试：逐个 token 实时打印回复"""
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL
    )

    stream = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一位乐于助人的智能小助手"},
            {"role": "user", "content": "你好，请你介绍一下你自己。"},
        ],
        stream=True
    )

    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()

if __name__ == "__main__":
    print("Testing sync chat:")
    test_sync()
    print("\nTesting stream chat:")
    test_stream() 