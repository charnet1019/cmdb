"""
CMDB FastAPI Application
Main entry point
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, close_db
from app.api import api_router


def _ensure_upload_dir():
    """Create upload directory if it doesn't exist"""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
CMDB - Configuration Management Database API

## 功能模块
- 🔐 认证管理: 用户登录、JWT Token
- 👥 用户管理: 用户CRUD、用户组
- 📦 资产管理: 资产CRUD、凭证管理
- 🔑 权限管理: 资产授权
- 📊 日志审计: 登录日志、操作日志

## 资产类型
- 主机 (host): Linux/Windows服务器
- 网络设备 (network): 交换机/路由器/防火墙
- 数据库 (database): MySQL/PostgreSQL/MongoDB
- 云服务 (cloud): AWS/阿里云/腾讯云
- Web应用 (web): 网站系统
- GPT服务 (gpt): AI服务平台
        """,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    # Mount static file serving for uploads
    _ensure_upload_dir()
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    return app


app = create_app()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}