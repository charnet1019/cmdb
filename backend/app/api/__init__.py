"""
API Router initialization
"""
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.users import router as users_router, group_router
from app.api.assets import router as assets_router, org_router, cred_router
from app.api.settings import router as settings_router
from app.api.dashboard import router as dashboard_router
from app.api.logs import router as logs_router
from app.api.authorizations import router as authz_router
from app.api.preferences import router as preferences_router

api_router = APIRouter()

# Include all API routers
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(users_router)
api_router.include_router(group_router)
api_router.include_router(assets_router)
api_router.include_router(org_router)
api_router.include_router(cred_router)
api_router.include_router(settings_router)
api_router.include_router(logs_router)
api_router.include_router(authz_router)
api_router.include_router(preferences_router)