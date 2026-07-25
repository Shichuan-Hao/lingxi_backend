"""
HTTP 请求日志中间件。

拦截所有 HTTP 请求，记录请求方法、路径、状态码和响应时间。
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import get_logger
import time

logger = get_logger(service="http")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 根据状态码选择图标
        status = response.status_code
        if 200 <= status < 300:
            icon = "\u2705"  # ✅
        elif 300 <= status < 400:
            icon = "\u27a1\ufe0f"  # ➡️
        elif 400 <= status < 500:
            icon = "\u26a0\ufe0f"  # ⚠️
        else:
            icon = "\u274c"  # ❌

        logger.info(
            f"{icon} {request.method:6s} {request.url.path:20s} | "
            f"{status} | {process_time:.2f}s | {request.client.host}"
        )
        
        return response 