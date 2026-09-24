from fastapi import APIRouter

from app.api.routes.access import router as access_router
from app.api.routes.account import router as account_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.membership_invitations import router as membership_invitations_router
from app.api.routes.students import router as students_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(account_router, tags=["account"])
api_router.include_router(access_router, tags=["access"])
api_router.include_router(membership_invitations_router, tags=["membership-invitations"])
api_router.include_router(students_router, tags=["students"])
