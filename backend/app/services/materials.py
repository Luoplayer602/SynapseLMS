"""Private storage, file inspection and learner grants."""

import hashlib
import socket
import struct
import time
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import func, or_, select

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import now, utc
from app.models import (
    Enrollment,
    EnrollmentPeriod,
    Material,
    MaterialAssignment,
    MaterialQuota,
    MaterialVersion,
    Notification,
    Organization,
    StudentMaterialGrant,
)

LIMITS = {"pdf": 25_000_000, "image": 25_000_000, "audio": 50_000_000}


def storage_root() -> Path:
    root = Path(get_settings().material_storage_path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def detect(head: bytes) -> tuple[str, str]:
    if head.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "audio", "audio/mpeg"
    raise APIError(422, "MATERIAL_FILE_TYPE")


def scan(path: Path) -> str:
    """clamd INSTREAM; an unavailable scanner never marks a file ready."""
    settings = get_settings()
    try:
        with socket.create_connection(
            (settings.clamav_host, settings.clamav_port), timeout=8
        ) as sock:
            sock.settimeout(60)
            sock.sendall(b"zINSTREAM\0")
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            answer = sock.recv(512).decode("utf-8", errors="replace")
    except (OSError, TimeoutError):
        return "pending_check"
    if answer.endswith("OK\0") or answer.endswith("OK\n"):
        return "ready"
    return "rejected" if " FOUND" in answer else "pending_check"


def quota(db, org_id: UUID) -> int:
    row = db.scalar(select(MaterialQuota).where(MaterialQuota.organization_id == org_id))
    return row.quota_bytes if row else 2_147_483_648


def used(db, org_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(MaterialVersion.size_bytes), 0)).where(
                MaterialVersion.organization_id == org_id,
                MaterialVersion.object_key.is_not(None),
                MaterialVersion.file_status != "rejected",
            )
        )
        or 0
    )


def save_upload(
    db, tenant, material: Material, upload: UploadFile, request_key: UUID, audit
) -> MaterialVersion:
    # Serialize uploads and quota changes within a tenant before reading used bytes.
    db.scalar(
        select(Organization.id)
        .where(Organization.id == tenant.organization.id)
        .with_for_update()
    )
    db.scalar(
        select(Material)
        .where(Material.id == material.id, Material.organization_id == tenant.organization.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if material.status == "withdrawn":
        raise APIError(409, "MATERIAL_WITHDRAWN")
    old = db.scalar(
        select(MaterialVersion).where(
            MaterialVersion.organization_id == tenant.organization.id,
            MaterialVersion.request_key == request_key,
        )
    )
    if old:
        if old.material_id != material.id:
            raise APIError(409, "MATERIAL_REQUEST_REUSED")
        digest_check = hashlib.sha256()
        size_check = 0
        while chunk := upload.file.read(1024 * 1024):
            size_check += len(chunk)
            if size_check > 50_000_000:
                raise APIError(413, "MATERIAL_FILE_SIZE")
            digest_check.update(chunk)
        if old.checksum != digest_check.hexdigest() or old.size_bytes != size_check:
            raise APIError(409, "MATERIAL_REQUEST_REUSED")
        return old
    root = storage_root()
    key = uuid4().hex
    path = root / key
    size = 0
    available = quota(db, tenant.organization.id) - used(db, tenant.organization.id)
    digest = hashlib.sha256()
    head = b""
    try:
        with path.open("xb") as stream:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > 50_000_000 or size > available:
                    raise APIError(413, "MATERIAL_QUOTA")
                if len(head) < 16:
                    head += chunk[: 16 - len(head)]
                digest.update(chunk)
                stream.write(chunk)
        kind, mime = detect(head)
        if size > LIMITS[kind]:
            raise APIError(413, "MATERIAL_FILE_SIZE")
        previous = db.scalar(
            select(MaterialVersion).where(
                MaterialVersion.material_id == material.id,
                MaterialVersion.checksum == digest.hexdigest(),
                MaterialVersion.file_status != "rejected",
            )
        )
        if previous:
            path.unlink(missing_ok=True)
            return previous
        # The browser MIME is untrusted. Store only the detected type.
        status = scan(path)
        if status == "rejected":
            path.unlink(missing_ok=True)
        revision = (
            db.scalar(
                select(func.coalesce(func.max(MaterialVersion.revision), 0)).where(
                    MaterialVersion.material_id == material.id
                )
            )
            + 1
        )
        row = MaterialVersion(
            organization_id=tenant.organization.id,
            material_id=material.id,
            revision=revision,
            request_key=request_key,
            kind=kind,
            file_status=status,
            object_key=key if status != "rejected" else None,
            metadata_snapshot={
                "title": material.title,
                "description": material.description,
                "source": material.source,
                "language": material.language,
                "audience": material.audience,
            },
            filename="".join(
                char
                for char in Path((upload.filename or "file").replace("\\", "/")).name
                if char.isascii() and (char.isalnum() or char in "._- ")
            )[:200]
            or "file",
            mime=mime,
            checksum=digest.hexdigest(),
            size_bytes=size,
            scan_message="scanner unavailable" if status == "pending_check" else "",
        )
        db.add(row)
        db.flush()
        audit(db, tenant.actor, "material.version.file", tenant.organization.id, row.id)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        path.unlink(missing_ok=True)
        raise


def own_grant(db, org_id: UUID, enrollment: Enrollment, assignment: MaterialAssignment):
    """Grant only if enrollment was active at publication, preserving past access on suspension."""
    if enrollment.state == "cancelled" or utc(assignment.publish_at) > now():
        return None
    granted = db.scalar(
        select(StudentMaterialGrant).where(
            StudentMaterialGrant.assignment_id == assignment.id,
            StudentMaterialGrant.enrollment_id == enrollment.id,
            StudentMaterialGrant.organization_id == org_id,
        )
    )
    if granted:
        return granted if granted.revoked_at is None else None
    period = db.scalar(
        select(EnrollmentPeriod.id).where(
            EnrollmentPeriod.enrollment_id == enrollment.id,
            EnrollmentPeriod.organization_id == org_id,
            EnrollmentPeriod.starts_at <= assignment.publish_at,
            or_(
                EnrollmentPeriod.ends_at.is_(None), EnrollmentPeriod.ends_at > assignment.publish_at
            ),
        )
    )
    if not period:
        return None
    granted = StudentMaterialGrant(
        organization_id=org_id,
        assignment_id=assignment.id,
        enrollment_id=enrollment.id,
        granted_at=now(),
    )
    db.add(granted)
    db.flush()
    return granted


def notify_grant(db, org_id: UUID, user_id: UUID, assignment: MaterialAssignment):
    key = f"material:{assignment.id}:{user_id}"
    if not db.scalar(
        select(Notification.id).where(
            Notification.organization_id == org_id,
            Notification.event_key == key,
            Notification.user_id == user_id,
        )
    ):
        db.add(
            Notification(
                organization_id=org_id,
                user_id=user_id,
                event_key=key,
                kind="material.published",
                target_id=assignment.id,
                created_at=now(),
            )
        )


def safe_path(key: str) -> Path:
    if len(key) != 32 or any(ch not in "0123456789abcdef" for ch in key):
        raise APIError(404, "BUSINESS_NOT_FOUND")
    path = storage_root() / key
    if not path.is_file():
        raise APIError(503, "MATERIAL_FILE_MISSING")
    return path


def cleanup_orphans(db, *, apply: bool = False, older_than_seconds: int = 86400) -> int:
    """Remove only unreferenced UUID-named files older than the retention window."""
    referenced = set(
        db.scalars(
            select(MaterialVersion.object_key).where(MaterialVersion.object_key.is_not(None))
        )
    )
    cutoff = time.time() - older_than_seconds
    candidates = 0
    for path in storage_root().iterdir():
        if (
            path.is_file()
            and not path.is_symlink()
            and len(path.name) == 32
            and all(char in "0123456789abcdef" for char in path.name)
            and path.name not in referenced
            and path.stat().st_mtime < cutoff
        ):
            candidates += 1
            if apply:
                path.unlink(missing_ok=True)
    return candidates
