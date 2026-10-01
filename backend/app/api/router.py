from fastapi import APIRouter

from app.api.routes.access import router as access_router
from app.api.routes.account import router as account_router
from app.api.routes.admissions import router as admissions_router
from app.api.routes.attendance import router as attendance_router
from app.api.routes.auth import router as auth_router
from app.api.routes.classrooms import router as classrooms_router
from app.api.routes.courses import router as courses_router
from app.api.routes.enrollment_lifecycle import router as enrollment_lifecycle_router
from app.api.routes.health import router as health_router
from app.api.routes.materials import router as materials_router
from app.api.routes.membership_invitations import router as membership_invitations_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.proficiencies import router as proficiencies_router
from app.api.routes.results import router as results_router
from app.api.routes.schedules import router as schedules_router
from app.api.routes.session_operations import router as session_operations_router
from app.api.routes.students import router as students_router
from app.api.routes.teachers import router as teachers_router

api_router = APIRouter()
api_router.include_router(enrollment_lifecycle_router, tags=["enrollment-lifecycle"])
api_router.include_router(results_router, tags=["results"])
api_router.include_router(materials_router, tags=["materials"])
api_router.include_router(admissions_router, tags=["admissions"])
api_router.include_router(attendance_router, tags=["attendance"])
api_router.include_router(notifications_router, tags=["notifications"])
api_router.include_router(health_router, tags=["system"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(account_router, tags=["account"])
api_router.include_router(access_router, tags=["access"])
api_router.include_router(membership_invitations_router, tags=["membership-invitations"])
api_router.include_router(students_router, tags=["students"])
api_router.include_router(courses_router, tags=["courses"])
api_router.include_router(proficiencies_router, tags=["student-proficiencies"])
api_router.include_router(teachers_router, tags=["teachers"])
api_router.include_router(classrooms_router, tags=["class-foundation"])
api_router.include_router(schedules_router, tags=["scheduling"])
api_router.include_router(session_operations_router, tags=["session-operations"])
