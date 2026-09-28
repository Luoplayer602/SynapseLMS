"""One end-to-end tenant workflow: admissions, invoicing, collection and placement."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.api.admission_schemas import (
    DecisionInput,
    DiscountInput,
    DiscountState,
    FeeInput,
    OpeningInput,
    PaymentInput,
    PlacementInput,
    RequestInput,
    ReverseInput,
    SettingsInput,
)
from app.api.dependencies import DB, Tenant, auth_guard
from app.api.routes.courses import Limit, Offset, authorize
from app.api.routes.schedules import session_view
from app.core.errors import APIError
from app.core.security import now
from app.models import (
    AdmissionOpening,
    AdmissionRequest,
    AdmissionSettings,
    Branch,
    BusinessOperation,
    ClassSession,
    Course,
    DiscountCode,
    Enrollment,
    FeePolicy,
    Invoice,
    LearningClass,
    Payment,
    StudentProfile,
)
from app.services import admissions as svc

router = APIRouter(prefix="/admissions", dependencies=[Depends(auth_guard)])


def view(row, fields):
    return {key: getattr(row, key) for key in fields.split()}


def staff(db, tenant, request, response):
    return authorize(db, tenant, request, response)


def access(db, tenant, request, response):
    role = authorize(db, tenant, request, response, "business_read")
    if role == "teacher":
        raise APIError(403, "FORBIDDEN")
    return svc.own_student(db, tenant) if role == "student" else None


def owner(row, own):
    if own and row.student_id != own.id:
        raise APIError(404, "BUSINESS_NOT_FOUND")


def page(db, query, limit, offset, render):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return {
        "items": [render(x) for x in db.scalars(query.limit(limit).offset(offset))],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def request_view(db, row):
    result = view(
        row,
        "id student_id course_id branch_id format availability "
        "discount_code status reason version created_at",
    )
    result.update(
        student_name=db.get(StudentProfile, row.student_id).full_name,
        course_name=db.get(Course, row.course_id).name,
    )
    enrollment = db.scalar(select(Enrollment).where(Enrollment.request_id == row.id))
    result["class_name"] = db.get(LearningClass, enrollment.class_id).name if enrollment else None
    result["class_id"] = enrollment.class_id if enrollment else None
    return result


def invoice_view(db, row):
    received = svc.paid(db, row)
    allocation = received
    installments = []
    for part in row.installments:
        allocated = min(allocation, part["amount"])
        allocation -= allocated
        installments.append(
            {
                **part,
                "paid": allocated,
                "remaining": part["amount"] - allocated,
                "overdue": part["due_on"] < now().date().isoformat() and allocated < part["amount"],
            }
        )
    return {
        **view(row, "id request_id student_id gross discount total snapshot created_at"),
        "student_name": db.get(StudentProfile, row.student_id).full_name,
        "paid": received,
        "remaining": row.total - received,
        "installments": installments,
        "overdue": sum(i["remaining"] for i in installments if i["overdue"]),
    }


@router.get("/options")
def options(db: DB, tenant: Tenant, request: Request, response: Response):
    own = access(db, tenant, request, response)
    org = tenant.organization.id
    courses = [
        {
            **view(c, "id code name"),
            "fee": (
                view(p, "amount installments version")
                if (p := db.scalar(select(FeePolicy).where(FeePolicy.course_id == c.id)))
                else None
            ),
        }
        for c in db.scalars(
            select(Course)
            .where(Course.organization_id == org, Course.status == "published")
            .order_by(Course.name)
        )
    ]
    return {
        "courses": courses,
        "branches": [
            view(x, "id name timezone")
            for x in db.scalars(
                select(Branch)
                .where(Branch.organization_id == org, Branch.archived_at.is_(None))
                .order_by(Branch.name)
            )
        ],
        "students": [view(own, "id full_name")]
        if own
        else [
            view(x, "id full_name")
            for x in db.scalars(
                select(StudentProfile)
                .where(StudentProfile.organization_id == org, StudentProfile.archived_at.is_(None))
                .order_by(StudentProfile.full_name)
            )
        ],
    }


@router.get("/settings")
def settings(db: DB, tenant: Tenant, request: Request, response: Response):
    staff(db, tenant, request, response)
    row = db.scalar(
        select(AdmissionSettings).where(AdmissionSettings.organization_id == tenant.organization.id)
    )
    return view(row, "block_debt version") if row else {"block_debt": False, "version": 0}


@router.put("/settings")
def set_settings(body: SettingsInput, db: DB, tenant: Tenant, request: Request, response: Response):
    authorize(db, tenant, request, response, "manage")
    fp, old = svc.replay(db, tenant, "admission.settings", None, body)
    if old is not None:
        return old
    row = db.scalar(
        select(AdmissionSettings).where(AdmissionSettings.organization_id == tenant.organization.id)
    )
    svc.expected(row, body.version)
    before = view(row, "version block_debt") if row else {}
    if not row:
        row = AdmissionSettings(organization_id=tenant.organization.id)
        db.add(row)
    row.block_debt, row.version = body.block_debt, body.version + 1
    return svc.finish(
        db, tenant, "admission.settings", None, body, fp, view(row, "version block_debt"), before
    )


@router.put("/fees/{course_id}")
def set_fee(
    course_id: UUID, body: FeeInput, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    svc.scoped(db, Course, tenant, course_id)
    fp, old = svc.replay(db, tenant, "fee.configure", course_id, body)
    if old is not None:
        return old
    row = db.scalar(select(FeePolicy).where(FeePolicy.course_id == course_id))
    svc.expected(row, body.version)
    before = view(row, "version amount installments") if row else {}
    if not row:
        row = FeePolicy(organization_id=tenant.organization.id, course_id=course_id)
        db.add(row)
    row.amount, row.installments, row.version = (
        body.amount,
        [x.model_dump() for x in body.installments],
        body.version + 1,
    )
    return svc.finish(
        db,
        tenant,
        "fee.configure",
        course_id,
        body,
        fp,
        view(row, "version amount installments"),
        before,
    )


@router.get("/discounts")
def discounts(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    staff(db, tenant, request, response)
    return page(
        db,
        select(DiscountCode)
        .where(DiscountCode.organization_id == tenant.organization.id)
        .order_by(DiscountCode.created_at.desc(), DiscountCode.id),
        limit,
        offset,
        lambda x: view(
            x, "id code course_id kind value starts_on ends_on max_uses used active version"
        ),
    )


@router.post("/discounts")
def create_discount(
    body: DiscountInput, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    fp, old = svc.replay(db, tenant, "discount.create", None, body)
    if old is not None:
        return old
    if body.course_id:
        svc.scoped(db, Course, tenant, body.course_id)
    code = body.code.upper()
    if db.scalar(
        select(DiscountCode.id).where(
            DiscountCode.organization_id == tenant.organization.id, DiscountCode.code == code
        )
    ):
        raise APIError(409, "DISCOUNT_DUPLICATE")
    row = DiscountCode(
        organization_id=tenant.organization.id,
        **body.model_dump(exclude={"request_key", "code"}),
        code=code,
    )
    db.add(row)
    db.flush()
    return svc.finish(db, tenant, "discount.create", row.id, body, fp, view(row, "id code version"))


@router.put("/discounts/{discount_id}")
def discount_state(
    discount_id: UUID,
    body: DiscountState,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, DiscountCode, tenant, discount_id)
    fp, old = svc.replay(db, tenant, "discount.state", discount_id, body)
    if old is not None:
        return old
    svc.expected(row, body.version)
    before = view(row, "active version")
    row.active, row.version = body.active, row.version + 1
    return svc.finish(
        db, tenant, "discount.state", row.id, body, fp, view(row, "id active version"), before
    )


@router.get("/openings")
def openings(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    staff(db, tenant, request, response)

    def render(row):
        opening = db.scalar(select(AdmissionOpening).where(AdmissionOpening.class_id == row.id))
        count = db.scalar(
            select(func.count()).select_from(Enrollment).where(Enrollment.class_id == row.id)
        )
        return {
            **view(row, "id name code capacity status"),
            "enrolled": count,
            "enabled": opening.enabled if opening else False,
            "version": opening.version if opening else 0,
        }

    return page(
        db,
        select(LearningClass)
        .where(LearningClass.organization_id == tenant.organization.id)
        .order_by(LearningClass.starts_on.desc(), LearningClass.id),
        limit,
        offset,
        render,
    )


@router.put("/openings/{class_id}")
def set_opening(
    class_id: UUID, body: OpeningInput, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    item = svc.scoped(db, LearningClass, tenant, class_id)
    fp, old = svc.replay(db, tenant, "admission.opening", class_id, body)
    if old is not None:
        return old
    row = db.scalar(select(AdmissionOpening).where(AdmissionOpening.class_id == class_id))
    svc.expected(row, body.version)
    if body.enabled:
        any_session = db.scalar(
            select(ClassSession.id)
            .where(
                ClassSession.class_id == class_id,
                ClassSession.status == "scheduled",
                ClassSession.starts_at > now(),
            )
            .limit(1)
        )
        begun = db.scalar(
            select(ClassSession.id)
            .where(ClassSession.class_id == class_id, ClassSession.starts_at <= now())
            .limit(1)
        )
        if (
            not any_session
            or begun
            or item.status != "draft"
            or db.get(Course, item.course_id).status != "published"
        ):
            raise APIError(409, "ADMISSION_CLASS_NOT_READY")
    before = view(row, "enabled version") if row else {}
    if not row:
        row = AdmissionOpening(organization_id=tenant.organization.id, class_id=class_id)
        db.add(row)
    row.enabled, row.version = body.enabled, body.version + 1
    return svc.finish(
        db, tenant, "admission.opening", class_id, body, fp, view(row, "enabled version"), before
    )


@router.get("/requests")
def requests(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    own = access(db, tenant, request, response)
    query = select(AdmissionRequest).where(
        AdmissionRequest.organization_id == tenant.organization.id
    )
    if own:
        query = query.where(AdmissionRequest.student_id == own.id)
    return page(
        db,
        query.order_by(AdmissionRequest.created_at.desc(), AdmissionRequest.id),
        limit,
        offset,
        lambda x: request_view(db, x),
    )


@router.get("/classes/{class_id}/roster")
def class_roster(
    class_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    staff(db, tenant, request, response)
    svc.scoped(db, LearningClass, tenant, class_id)
    query = (
        select(Enrollment)
        .where(Enrollment.class_id == class_id)
        .order_by(Enrollment.effective_at, Enrollment.id)
    )
    return page(
        db,
        query,
        limit,
        offset,
        lambda row: {
            "id": row.id,
            "student_id": row.student_id,
            "student_name": db.get(StudentProfile, row.student_id).full_name,
            "effective_at": row.effective_at,
            "request_id": row.request_id,
        },
    )


@router.post("/requests")
def submit(body: RequestInput, db: DB, tenant: Tenant, request: Request, response: Response):
    own = access(db, tenant, request, response)
    fp, old = svc.replay(db, tenant, "admission.submit", None, body)
    if old is not None:
        return old
    if own and body.student_id and body.student_id != own.id:
        raise APIError(403, "FORBIDDEN")
    profile = own or svc.scoped(db, StudentProfile, tenant, body.student_id)
    svc.student_ready(db, tenant, profile)
    course = svc.scoped(db, Course, tenant, body.course_id)
    if course.status != "published" or not db.scalar(
        select(FeePolicy.id).where(FeePolicy.course_id == course.id)
    ):
        raise APIError(409, "ADMISSION_FEE_REQUIRED")
    if body.branch_id and svc.scoped(db, Branch, tenant, body.branch_id).archived_at:
        raise APIError(409, "FACILITY_ARCHIVED")
    settings = db.scalar(
        select(AdmissionSettings).where(AdmissionSettings.organization_id == tenant.organization.id)
    )
    if settings and settings.block_debt and svc.debt(db, profile.id) > 0:
        raise APIError(409, "ADMISSION_DEBT_BLOCKED")
    if db.scalar(
        select(AdmissionRequest.id).where(
            AdmissionRequest.student_id == profile.id,
            AdmissionRequest.course_id == course.id,
            AdmissionRequest.status.in_(["submitted", "waiting", "placed"]),
        )
    ):
        raise APIError(409, "ADMISSION_DUPLICATE")
    row = AdmissionRequest(
        organization_id=tenant.organization.id,
        student_id=profile.id,
        **body.model_dump(exclude={"request_key", "student_id", "availability", "discount_code"}),
        availability=jsonable_encoder(body.availability),
        discount_code=body.discount_code.upper(),
    )
    db.add(row)
    db.flush()
    svc.notify(
        db,
        tenant.organization.id,
        svc.staff_ids(db, tenant.organization.id),
        "admission.submitted",
        row.id,
        f"admission:{row.id}:1",
    )
    return svc.finish(db, tenant, "admission.submit", row.id, body, fp, request_view(db, row))


def build_invoice(db, tenant, row, course):
    policy = db.scalar(select(FeePolicy).where(FeePolicy.course_id == course.id))
    if not policy:
        raise APIError(409, "ADMISSION_FEE_REQUIRED")
    discount = 0
    if row.discount_code:
        code = db.scalar(
            select(DiscountCode).where(
                DiscountCode.organization_id == tenant.organization.id,
                DiscountCode.code == row.discount_code,
            )
        )
        if (
            not code
            or not code.active
            or code.used >= code.max_uses
            or not code.starts_on <= now().date() <= code.ends_on
            or code.course_id
            and code.course_id != course.id
        ):
            raise APIError(409, "DISCOUNT_UNAVAILABLE")
        discount = min(
            policy.amount, code.value if code.kind == "fixed" else policy.amount * code.value // 100
        )
        code.used += 1
        code.version += 1
    total = policy.amount - discount
    parts, remaining = [], total
    for index, rule in enumerate(policy.installments):
        amount = (
            remaining if index == len(policy.installments) - 1 else total * rule["percent"] // 100
        )
        remaining -= amount
        parts.append(
            {"due_on": (now().date() + timedelta(days=rule["days"])).isoformat(), "amount": amount}
        )
    invoice = Invoice(
        organization_id=tenant.organization.id,
        request_id=row.id,
        student_id=row.student_id,
        gross=policy.amount,
        discount=discount,
        total=total,
        installments=parts,
        snapshot={
            "currency": "VND",
            "course_name": course.name,
            "course_code": course.code,
            "fee_version": policy.version,
            "discount_code": row.discount_code,
            "installments": policy.installments,
        },
    )
    db.add(invoice)
    db.flush()
    return invoice


@router.post("/requests/{request_id}/decision")
def decide(
    request_id: UUID,
    body: DecisionInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, AdmissionRequest, tenant, request_id)
    fp, old = svc.replay(db, tenant, "admission.decision", request_id, body)
    if old is not None:
        return old
    svc.expected(row, body.version)
    if row.status != "submitted":
        raise APIError(409, "ADMISSION_STATE")
    before = request_view(db, row)
    profile = svc.scoped(db, StudentProfile, tenant, row.student_id)
    if body.action == "reject":
        if len(body.reason) < 3:
            raise APIError(422, "BUSINESS_REASON_REQUIRED")
        row.status, row.reason = "rejected", body.reason
    else:
        svc.student_ready(db, tenant, profile)
        course = svc.scoped(db, Course, tenant, row.course_id)
        if course.status != "published":
            raise APIError(409, "ADMISSION_STATE")
        settings = db.scalar(
            select(AdmissionSettings).where(
                AdmissionSettings.organization_id == tenant.organization.id
            )
        )
        if settings and settings.block_debt and svc.debt(db, profile.id) > 0:
            raise APIError(409, "ADMISSION_DEBT_BLOCKED")
        build_invoice(db, tenant, row, course)
        row.status = "waiting"
        choices = svc.candidates(db, tenant, row)
        sure = [x for x in choices if not x["warnings"]]
        if len(sure) == 1:
            svc.place(db, tenant, row, sure[0]["id"])
        else:
            svc.notify(
                db,
                tenant.organization.id,
                svc.staff_ids(db, tenant.organization.id),
                "admission.waiting",
                row.id,
                f"waiting:{row.id}",
            )
    row.version += 1
    svc.notify(
        db,
        tenant.organization.id,
        [svc.student_user(db, profile)],
        f"admission.{row.status}",
        row.id,
        f"admission:{row.id}:{row.version}",
    )
    return svc.finish(
        db, tenant, "admission.decision", row.id, body, fp, request_view(db, row), before
    )


@router.get("/requests/{request_id}/candidates")
def placement_choices(
    request_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, AdmissionRequest, tenant, request_id)
    return {"items": svc.candidates(db, tenant, row) if row.status == "waiting" else []}


@router.post("/requests/{request_id}/placement")
def manual_place(
    request_id: UUID,
    body: PlacementInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, AdmissionRequest, tenant, request_id)
    fp, old = svc.replay(db, tenant, "admission.place", request_id, body)
    if old is not None:
        return old
    svc.expected(row, body.version)
    svc.student_ready(db, tenant, svc.scoped(db, StudentProfile, tenant, row.student_id))
    if row.status != "waiting" or body.class_id not in [
        x["id"] for x in svc.candidates(db, tenant, row)
    ]:
        raise APIError(409, "ADMISSION_NO_SEAT")
    before = request_view(db, row)
    svc.place(db, tenant, row, body.class_id)
    row.version += 1
    before["placement_reason"] = body.reason
    svc.notify(
        db,
        tenant.organization.id,
        [svc.student_user(db, db.get(StudentProfile, row.student_id))],
        "admission.placed",
        row.id,
        f"admission:{row.id}:{row.version}",
    )
    return svc.finish(
        db, tenant, "admission.place", row.id, body, fp, request_view(db, row), before
    )


@router.get("/invoices")
def invoices(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    own = access(db, tenant, request, response)
    query = select(Invoice).where(Invoice.organization_id == tenant.organization.id)
    if own:
        query = query.where(Invoice.student_id == own.id)
    return page(
        db,
        query.order_by(Invoice.created_at.desc(), Invoice.id),
        limit,
        offset,
        lambda x: invoice_view(db, x),
    )


@router.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: UUID, db: DB, tenant: Tenant, request: Request, response: Response):
    own = access(db, tenant, request, response)
    row = svc.scoped(db, Invoice, tenant, invoice_id)
    owner(row, own)
    return {
        **invoice_view(db, row),
        "organization_name": tenant.organization.name,
        "payments": [
            view(x, "id amount method reference created_at reversed_at reversal_reason actor_id")
            for x in db.scalars(
                select(Payment)
                .where(Payment.invoice_id == row.id)
                .order_by(Payment.created_at, Payment.id)
            )
        ],
    }


@router.post("/invoices/{invoice_id}/payments")
def collect(
    invoice_id: UUID,
    body: PaymentInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, Invoice, tenant, invoice_id)
    fp, old = svc.replay(db, tenant, "payment.collect", invoice_id, body)
    if old is not None:
        return old
    if body.amount > row.total - svc.paid(db, row):
        raise APIError(409, "PAYMENT_EXCEEDS_DEBT")
    before = invoice_view(db, row)
    payment = Payment(
        organization_id=tenant.organization.id,
        invoice_id=row.id,
        actor_id=tenant.actor.user.id,
        **body.model_dump(exclude={"request_key"}),
    )
    db.add(payment)
    db.flush()
    svc.notify(
        db,
        tenant.organization.id,
        [svc.student_user(db, db.get(StudentProfile, row.student_id))],
        "payment.collected",
        row.id,
        f"payment:{payment.id}",
    )
    return svc.finish(
        db,
        tenant,
        "payment.collect",
        row.id,
        body,
        fp,
        {"payment_id": payment.id, "invoice": invoice_view(db, row)},
        before,
    )


@router.post("/payments/{payment_id}/reverse")
def reverse(
    payment_id: UUID,
    body: ReverseInput,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
):
    staff(db, tenant, request, response)
    row = svc.scoped(db, Payment, tenant, payment_id)
    fp, old = svc.replay(db, tenant, "payment.reverse", payment_id, body)
    if old is not None:
        return old
    if row.reversed_at:
        raise APIError(409, "PAYMENT_REVERSED")
    before = view(row, "id amount method reference")
    row.reversed_at, row.reversed_by, row.reversal_reason = now(), tenant.actor.user.id, body.reason
    db.flush()
    invoice = db.get(Invoice, row.invoice_id)
    svc.notify(
        db,
        tenant.organization.id,
        [svc.student_user(db, db.get(StudentProfile, invoice.student_id))],
        "payment.reversed",
        invoice.id,
        f"reverse:{row.id}",
    )
    return svc.finish(
        db, tenant, "payment.reverse", row.id, body, fp, invoice_view(db, invoice), before
    )


@router.get("/history/{target_id}")
def history(
    target_id: UUID,
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    staff(db, tenant, request, response)
    return page(
        db,
        select(BusinessOperation)
        .where(
            BusinessOperation.organization_id == tenant.organization.id,
            BusinessOperation.target_id == target_id,
        )
        .order_by(BusinessOperation.created_at.desc(), BusinessOperation.id),
        limit,
        offset,
        lambda x: view(x, "id action actor_id created_at before result"),
    )


@router.get("/my-sessions")
def my_sessions(
    db: DB,
    tenant: Tenant,
    request: Request,
    response: Response,
    limit: Limit = 20,
    offset: Offset = 0,
):
    authorize(db, tenant, request, response, "catalog")
    own = svc.own_student(db, tenant)
    query = (
        select(ClassSession)
        .join(Enrollment, Enrollment.class_id == ClassSession.class_id)
        .where(
            Enrollment.student_id == own.id,
            ClassSession.organization_id == tenant.organization.id,
            ClassSession.status == "scheduled",
            ClassSession.ends_at >= now(),
        )
        .order_by(ClassSession.starts_at, ClassSession.id)
    )
    return page(db, query, limit, offset, lambda x: session_view(db, x))
