"""
API Router initialization
"""
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.auth_mfa import router as auth_mfa_router
from app.api.users import router as users_router
from app.api.groups import group_router
# user_account registers force-logout/reset-password/authorizations routes
# onto users_router as an import side effect (decorates the same `router`
# object exported by users.py) — imported for that effect only.
from app.api import user_account
_ = user_account
from app.api.assets import router as assets_router
# asset_config/asset_import_export/asset_detail register their routes onto
# assets_router as an import side effect (they decorate the same `router`
# object) — the modules themselves have no exported names we need, but the
# import must happen before assets_router is included below.
#
# Order matters: Starlette matches routes in registration order, and
# asset_detail's GET/PUT/DELETE /{asset_id} are wildcards that would swallow
# fixed paths like /assets/export or /assets/import/{category} if registered
# first (asset_id="export"). asset_detail must be imported LAST among these.
from app.api import asset_config, asset_import_export, asset_detail
_ = (asset_config, asset_import_export, asset_detail)
from app.api.organizations import org_router
from app.api.credentials import cred_router, oob_router
from app.api.settings import router as settings_router
from app.api.dashboard import router as dashboard_router
from app.api.logs import router as logs_router
from app.api.logs_login import router as logs_login_router
from app.api.logs_operation import router as logs_operation_router
from app.api.logs_password import router as logs_password_router
from app.api.authorizations import router as authz_router
from app.api.preferences import router as preferences_router
from app.api.upload import router as upload_router
from app.api.events import router as events_router
from app.api.notifications import router as notifications_router

api_router = APIRouter()

# Include all API routers
api_router.include_router(auth_router)
api_router.include_router(auth_mfa_router)
api_router.include_router(dashboard_router)
api_router.include_router(users_router)
api_router.include_router(group_router)
api_router.include_router(assets_router)
api_router.include_router(org_router)
api_router.include_router(cred_router)
api_router.include_router(oob_router)
api_router.include_router(settings_router)
api_router.include_router(logs_router)
api_router.include_router(logs_login_router)
api_router.include_router(logs_operation_router)
api_router.include_router(logs_password_router)
api_router.include_router(authz_router)
api_router.include_router(preferences_router)
api_router.include_router(upload_router)
api_router.include_router(events_router)
api_router.include_router(notifications_router)
