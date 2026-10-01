from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select

from app.api.dependencies import DB, Tenant, auth_guard
from app.api.routes import materials as material_routes
from app.api.routes.admissions import page, view
from app.api.routes.courses import Limit, Offset, authorize
from app.core.errors import APIError
from app.core.security import now
from app.models import Notification, SessionHistory

router = APIRouter(prefix="/notifications", dependencies=[Depends(auth_guard)])


def notification_view(db, row):
    result = view(row, "id kind target_id created_at read_at")
    result["session"] = None
    if row.kind.startswith("session."):
        # Use the event snapshot, not the live session: a replaced teacher must not
        # learn later changes made after they stopped being a recipient.
        version = row.event_key.rsplit(":", 1)[-1]
        if version.isdigit():
            history = db.scalar(
                select(SessionHistory).where(
                    SessionHistory.organization_id == row.organization_id,
                    SessionHistory.session_id == row.target_id,
                    SessionHistory.version == int(version),
                )
            )
            if history:
                result["session"] = {
                    key: history.after[key]
                    for key in (
                        "class_name",
                        "starts_at",
                        "ends_at",
                        "timezone",
                        "room_name",
                    )
                }
    return result


@router.get("")
def inbox(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    current = authorize(db, tenant, request, response, "business_read")
    if current == "student":
        try:
            list(material_routes.learner_rows(db, tenant))
            db.commit()
        except APIError as error:
            if error.code != "ADMISSION_PROFILE_REQUIRED":
                raise
    query = select(Notification).where(
        Notification.organization_id == tenant.organization.id,
        Notification.user_id == tenant.actor.user.id,
    )
    unread = db.scalar(
        select(func.count()).select_from(query.where(Notification.read_at.is_(None)).subquery())
    )
    return {
        **page(
            db,
            query.order_by(Notification.created_at.desc(), Notification.id),
            limit,
            offset,
            lambda x: notification_view(db, x),
        ),
        "unread": unread,
    }


@router.post("/{notification_id}/read")
def read(notification_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "business_read")
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == tenant.organization.id,
            Notification.user_id == tenant.actor.user.id,
        )
    )
    if not row:
        raise APIError(404, "BUSINESS_NOT_FOUND")
    row.read_at = row.read_at or now()
    db.commit()
    return {"id": row.id, "read_at": row.read_at}
