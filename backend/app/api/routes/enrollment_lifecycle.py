from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.api.dependencies import DB, Tenant, auth_guard
from app.api.enrollment_lifecycle_schemas import (
    DisbursementInput,
    LifecycleInput,
    LifecyclePreview,
    PolicyInput,
    RefundCreate,
    RefundDecision,
    RefundPreview,
)
from app.api.routes.admissions import access, invoice_view, owner, page, staff, view
from app.api.routes.courses import Limit, Offset, authorize
from app.core.errors import APIError
from app.core.security import now
from app.models import (
    AdmissionRequest,
    ClassSession,
    Course,
    EnrollmentOperation,
    EnrollmentPeriod,
    Invoice,
    InvoiceAdjustment,
    LearningClass,
    RefundCase,
    RefundDisbursement,
    RefundPolicy,
    StudentProfile,
)
from app.services import admissions as svc
from app.services import enrollment_lifecycle as life

router = APIRouter(dependencies=[Depends(auth_guard)])


def case_view(db, row, personal=False):
    result = view(
        row,
        "id request_id invoice_id status version proposed approved "
        "offset_amount cash_amount created_at",
    )
    # Financial figures are personal; payment IDs and internal reasons are staff-only.
    result["calculation"] = {
        k: row.snapshot[k]
        for k in (
            "total",
            "paid",
            "remaining",
            "unused",
            "total_sessions",
            "unused_sessions",
            "policy",
            "fee",
        )
    }
    result["student_name"] = db.get(
        StudentProfile, db.get(Invoice, row.invoice_id).student_id
    ).full_name
    payout = db.scalar(select(RefundDisbursement).where(RefundDisbursement.case_id == row.id))
    result["disbursement"] = (
        view(payout, "id amount method reference created_at") if payout else None
    )
    if not personal:
        result.update(reason=row.reason, actor_id=row.actor_id, snapshot=row.snapshot)
    return result


def enrollment_view(db, req, personal=False, detail=False):
    row = life.enrollment_for(db, req.id)
    periods = (
        list(
            db.scalars(
                select(EnrollmentPeriod)
                .where(
                    EnrollmentPeriod.enrollment_id == row.id,
                )
                .order_by(EnrollmentPeriod.starts_at)
            )
        )
        if row
        else []
    )
    result = {
        "id": req.id,
        "enrollment_id": row.id if row else None,
        "student_name": db.get(StudentProfile, req.student_id).full_name,
        "course_name": db.get(Course, req.course_id).name,
        "class_name": db.get(LearningClass, row.class_id).name if row else None,
        "state": row.state if row else "cancelled" if req.cancelled_at else "waiting",
        "version": row.version if row else req.version,
        "settled": bool(life.settled(db, req.id)),
        "periods": [view(p, "starts_at ends_at") for p in periods],
    }
    if detail:
        invoice = db.scalar(select(Invoice).where(Invoice.request_id == req.id))
        result["invoice"] = invoice_view(db, invoice)
        result["sessions"] = (
            [
                view(s, "id starts_at ends_at timezone status")
                for s in db.scalars(
                    select(ClassSession)
                    .where(
                        ClassSession.class_id == row.class_id,
                        ClassSession.starts_at > now(),
                        ClassSession.status == "scheduled",
                    )
                    .order_by(ClassSession.starts_at, ClassSession.id)
                )
            ]
            if row
            else []
        )
        result["history"] = [
            view(
                o,
                "id action effective_at created_at" + (" reason actor_id" if not personal else ""),
            )
            for o in db.scalars(
                select(EnrollmentOperation)
                .where(
                    EnrollmentOperation.request_id == req.id,
                )
                .order_by(EnrollmentOperation.created_at, EnrollmentOperation.id)
            )
        ]
        result["refunds"] = [
            case_view(db, c, personal)
            for c in db.scalars(
                select(RefundCase)
                .where(RefundCase.request_id == req.id)
                .order_by(RefundCase.created_at.desc(), RefundCase.id)
            )
        ]
    return result


@router.get("/enrollments")
def enrollments(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    own = access(db, tenant, request, response)
    query = (
        select(AdmissionRequest)
        .join(Invoice, Invoice.request_id == AdmissionRequest.id)
        .where(
            AdmissionRequest.organization_id == tenant.organization.id,
        )
    )
    if own:
        query = query.where(AdmissionRequest.student_id == own.id)
    return page(
        db,
        query.order_by(AdmissionRequest.created_at.desc(), AdmissionRequest.id),
        limit,
        offset,
        lambda r: enrollment_view(db, r, bool(own)),
    )


@router.get("/enrollments/{request_id}")
def detail(request_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    own = access(db, tenant, request, response)
    row = svc.scoped(db, AdmissionRequest, tenant, request_id)
    owner(row, own)
    if not db.scalar(select(Invoice.id).where(Invoice.request_id == row.id)):
        raise APIError(404, "BUSINESS_NOT_FOUND")
    return enrollment_view(db, row, bool(own), True)


@router.post("/enrollments/{request_id}/preview")
def preview(
    request_id: UUID,
    body: LifecyclePreview,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, AdmissionRequest, tenant, request_id)
    return life.preview(db, row, body)


@router.post("/enrollments/{request_id}/operations")
def operate(
    request_id: UUID,
    body: LifecycleInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, AdmissionRequest, tenant, request_id)
    fp, old = svc.replay(db, tenant, "enrollment.operate", request_id, body)
    if old is not None:
        return old
    if body.action == "resume":
        svc.student_ready(db, tenant, db.get(StudentProfile, row.student_id))
    before = life.operate(db, tenant, row, body)
    return svc.finish(
        db,
        tenant,
        "enrollment.operate",
        row.id,
        body,
        fp,
        enrollment_view(db, row, detail=True),
        before,
    )


@router.get("/refunds/policy")
def policy(db: DB, tenant: Tenant, request: Request, response: Response):
    staff(db, tenant, request, response)
    return life.policy(db, tenant.organization.id)


@router.put("/refunds/policy")
def set_policy(body: PolicyInput, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    fp, old = svc.replay(db, tenant, "refund.policy", None, body)
    if old is not None:
        return old
    row = db.scalar(
        select(RefundPolicy).where(RefundPolicy.organization_id == tenant.organization.id)
    )
    svc.expected(row, body.version)
    before = life.policy(db, tenant.organization.id)
    if not row:
        row = RefundPolicy(organization_id=tenant.organization.id)
        db.add(row)
    row.kind, row.value, row.version = body.kind, body.value, body.version + 1
    db.flush()
    return svc.finish(
        db, tenant, "refund.policy", None, body, fp, life.policy(db, tenant.organization.id), before
    )


@router.post("/refunds/preview")
def refund_preview(
    body: RefundPreview, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    return life.refund_quote(db, svc.scoped(db, AdmissionRequest, tenant, body.request_id))


@router.post("/refunds")
def propose(body: RefundCreate, db: DB, tenant: Tenant, request: Request, response: Response):
    staff(db, tenant, request, response)
    req = svc.scoped(db, AdmissionRequest, tenant, body.request_id)
    fp, old = svc.replay(db, tenant, "refund.propose", req.id, body)
    if old is not None:
        return old
    quote = life.refund_quote(db, req)
    if quote["source_digest"] != body.source_digest:
        raise APIError(409, "BUSINESS_STALE")
    if db.scalar(
        select(RefundCase.id).where(
            RefundCase.request_id == req.id, RefundCase.status == "proposed"
        )
    ):
        raise APIError(409, "REFUND_OPEN_CASE")
    row = RefundCase(
        organization_id=req.organization_id,
        request_id=req.id,
        invoice_id=UUID(quote["invoice_id"]),
        snapshot=quote,
        proposed=quote["proposed"],
        source_digest=body.source_digest,
        actor_id=tenant.actor.user.id,
        created_at=now(),
    )
    db.add(row)
    db.flush()
    return svc.finish(db, tenant, "refund.propose", req.id, body, fp, case_view(db, row))


@router.get("/refunds")
def refunds(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    own = access(db, tenant, request, response)
    query = (
        select(RefundCase)
        .join(Invoice, Invoice.id == RefundCase.invoice_id)
        .where(
            RefundCase.organization_id == tenant.organization.id,
        )
    )
    if own:
        query = query.where(Invoice.student_id == own.id)
    return page(
        db,
        query.order_by(RefundCase.created_at.desc(), RefundCase.id),
        limit,
        offset,
        lambda r: case_view(db, r, bool(own)),
    )


@router.get("/refunds/{case_id}")
def refund_detail(case_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    own = access(db, tenant, request, response)
    row = svc.scoped(db, RefundCase, tenant, case_id)
    owner(db.get(Invoice, row.invoice_id), own)
    return case_view(db, row, bool(own))


def notify(db, tenant, row, event):
    invoice = db.get(Invoice, row.invoice_id)
    svc.notify(
        db,
        tenant.organization.id,
        [svc.student_user(db, db.get(StudentProfile, invoice.student_id))],
        "refund." + event,
        row.request_id,
        f"refund:{row.id}:{row.version}",
    )


@router.post("/refunds/{case_id}/decision")
def decide(
    case_id: UUID,
    body: RefundDecision,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, RefundCase, tenant, case_id)
    fp, old = svc.replay(db, tenant, "refund.decision", case_id, body)
    if old is not None:
        return old
    svc.expected(row, body.version)
    if row.status != "proposed":
        raise APIError(409, "REFUND_STATE")
    before = case_view(db, row)
    if body.action != "approve":
        if len(body.reason) < 3:
            raise APIError(422, "BUSINESS_REASON_REQUIRED")
        row.status = "rejected" if body.action == "reject" else "cancelled"
    else:
        quote = life.refund_quote(db, db.get(AdmissionRequest, row.request_id))
        if quote["source_digest"] != row.source_digest:
            raise APIError(409, "BUSINESS_STALE")
        if body.amount > quote["paid"]:
            raise APIError(409, "REFUND_EXCEEDS_PAID")
        if body.amount != row.proposed and len(body.reason) < 3:
            raise APIError(422, "BUSINESS_REASON_REQUIRED")
        row.approved = body.amount
        row.offset_amount = min(body.amount, quote["remaining"])
        row.cash_amount = body.amount - row.offset_amount
        row.status = "pending" if row.cash_amount else "paid" if body.amount else "no_refund"
        row.settled_request_id = row.request_id if body.amount else None
        if row.offset_amount:
            db.add(
                InvoiceAdjustment(
                    organization_id=row.organization_id,
                    invoice_id=row.invoice_id,
                    case_id=row.id,
                    amount=row.offset_amount,
                )
            )
    row.reason, row.version = body.reason, row.version + 1
    db.flush()
    notify(db, tenant, row, row.status)
    return svc.finish(db, tenant, "refund.decision", row.id, body, fp, case_view(db, row), before)


@router.post("/refunds/{case_id}/disburse")
def disburse(
    case_id: UUID,
    body: DisbursementInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, RefundCase, tenant, case_id)
    fp, old = svc.replay(db, tenant, "refund.disburse", case_id, body)
    if old is not None:
        return old
    svc.expected(row, body.version)
    if row.status != "pending":
        raise APIError(409, "REFUND_STATE")
    before = case_view(db, row)
    db.add(
        RefundDisbursement(
            organization_id=row.organization_id,
            case_id=row.id,
            amount=row.cash_amount,
            method=body.method,
            reference=body.reference,
            actor_id=tenant.actor.user.id,
            created_at=now(),
        )
    )
    row.status, row.version = "paid", row.version + 1
    db.flush()
    notify(db, tenant, row, "paid")
    return svc.finish(db, tenant, "refund.disburse", row.id, body, fp, case_view(db, row), before)
