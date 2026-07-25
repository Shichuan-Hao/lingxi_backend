#!/usr/bin/env python
"""灵犀服务启动脚本 - v1.1

用法:
    python run.py              # 推荐方式
    chmod +x run.py && ./run.py  # 执行权限后直接运行
"""
import uvicorn
from app.core.logger import get_logger
import os
from pathlib import Path

logger = get_logger(service="server")


def start_server():
    """启动 FastAPI 服务，自动检测 .env 配置并初始化日志。"""
    # 确保工作目录为项目根目录
    os.chdir(Path(__file__).parent)

    # 延迟导入，确保工作目录正确后加载配置
    from app.core.config import settings

    # 确定各服务的模型信息
    chat_info = (
        f"云端 Deepseek({settings.DEEPSEEK_MODEL})"
        if settings.CHAT_SERVICE == "deepseek"
        else f"本地 Ollama({settings.OLLAMA_CHAT_MODEL})"
    )
    reason_info = (
        f"云端 Deepseek({settings.DEEPSEEK_MODEL})"
        if settings.REASON_SERVICE == "deepseek"
        else f"本地 Ollama({settings.OLLAMA_REASON_MODEL})"
    )
    search_info = f"云端 Deepseek({settings.DEEPSEEK_MODEL})"

    logger.info("\u2501" * 50)
    logger.info("  \U0001f300  灵犀 \u00b7 智能助手   \U0001f300")
    logger.info("\u2501" * 50)
    logger.info("  \U0001f4e6  服务配置:")
    logger.info(f"    \U0001f4ac  /chat       普通对话  \u2192 {chat_info}")
    logger.info(f"    \U0001f9e0  /reason     深度推理  \u2192 {reason_info}")
    logger.info(f"    \U0001f50d  /search     联网搜索  \u2192 {search_info}")
    logger.info("  " + "\u2500" * 42)
    logger.info("    \U0001f4c1  /upload     文件上传(RAG)")
    logger.info("    \U0001f4d6  /chat-rag   文档问答")
    logger.info("    \U0001f511  /api/register  用户注册")
    logger.info("    \U0001f6aa  /api/token     用户登录")
    logger.info("    \U0001f464  /api/users/me  用户信息")
    logger.info("    \U0001f3e5  /health        健康检查")
    logger.info("\u2501" * 50)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        access_log=False,
        log_level="error",
        reload=True,
    )


if __name__ == "__main__":
    start_server() 