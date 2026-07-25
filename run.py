#!/usr/bin/env python
"""灵犀服务启动脚本 - v1.1

用法:
    python run.py              # 开发模式（热加载）
    python run.py --prod       # 生产模式（无热加载）
    python run.py --prod -w 4  # 生产模式（4 worker）
"""
import argparse
import uvicorn
from app.core.logger import get_logger
import os
from pathlib import Path

logger = get_logger(service="server")


def start_server():
    """启动 FastAPI 服务，自动检测 .env 配置并初始化日志。"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="灵犀服务启动脚本")
    parser.add_argument("--prod", action="store_true", help="生产模式（关闭热加载）")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Worker 进程数（仅生产模式）")
    args = parser.parse_args()

    is_prod = args.prod
    workers = args.workers if is_prod else 1

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

    mode_tag = "\U0001f3ed  生产模式" if is_prod else "\U0001f527  开发模式（热加载）"
    if is_prod and workers > 1:
        mode_tag += f" | {workers} workers"

    logger.info("\u2501" * 50)
    logger.info(f"  \U0001f300  灵犀 \u00b7 智能助手   {mode_tag}")
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
    logger.info("  \U0001f310  访问地址:")
    logger.info("    \U0001f3e0  前端页面   http://localhost:8000/")
    logger.info("    \U0001f4d6  API 文档   http://localhost:8000/docs")
    logger.info("    \U0001f3e5  健康检查   http://localhost:8000/health")
    logger.info("\u2501" * 50)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        access_log=False,
        log_level="error",
        reload=not is_prod,
        workers=workers,
    )


if __name__ == "__main__":
    start_server() 