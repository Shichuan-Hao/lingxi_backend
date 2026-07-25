"""
API 路由注册入口。

汇总所有子路由模块，暴露为统一的 api_router，
由 main.py 挂载到 FastAPI 应用上。
"""
from fastapi import APIRouter
from app.api.auth import router as auth_router

# 创建主路由，所有可用的参数：https://fastapi.tiangolo.com/reference/apirouter/?h=apirouter#fastapi.APIRouter--example
api_router = APIRouter()

# 注册所有子路由，不使用前缀
api_router.include_router(auth_router, tags=["authentication"]) 