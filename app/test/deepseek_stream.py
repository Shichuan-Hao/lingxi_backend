"""
DeepSeek 流式对话测试脚本。

验证 DeepSeek API 的流式（stream=True）聊天能力，逐字打印模型回复。
"""

from openai import OpenAI
import os
from dotenv import load_dotenv
import sys

# 获取项目根目录的 .env 文件
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
env_path = os.path.join(root_dir, 'llm_backend', '.env')

load_dotenv(env_path)

def stream_chat():
    """测试 DeepSeek 流式聊天：实时打印每个 token"""
    try:
        client = OpenAI(
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            base_url=os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
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
    except Exception as e:
        print(f"发生错误: {str(e)}", file=sys.stderr)
        raise

if __name__ == "__main__":
    stream_chat()