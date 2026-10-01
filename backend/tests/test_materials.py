import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import now
from app.models import (
    ClassCurriculum,
    ClassTeacher,
    Enrollment,
    EnrollmentPeriod,
    MaterialAssignment,
    MaterialVersion,
    StudentMaterialGrant,
)
from app.services.materials import cleanup_orphans
from tests.test_admissions import admissions, approve, submit  # noqa: F401
from tests.test_auth_api import login
from tests.test_classrooms import foundation  # noqa: F401
from tests.test_courses import catalog_fixture  # noqa: F401
from tests.test_schedules import schedule  # noqa: F401

BASE = "/api/v1/materials"


def make_link(s):
    f = s["f"]
    client, manager = f[0], f[5]
    created = client.post(BASE, headers=manager, json={"title": "Lesson 1", "source": "Licensed"})
    assert created.status_code == 200, created.text
    material_id = created.json()["id"]
    version = client.post(
        BASE + f"/{material_id}/versions/link",
        headers=manager,
        json={"url": "https://example.org/lesson-1", "request_key": str(uuid4())},
    )
    assert version.status_code == 200, version.text
    version_id = version.json()["id"]
    published = client.post(BASE + f"/versions/{version_id}/publish", headers=manager)
    assert published.status_code == 200, published.text
    return material_id, version_id


def test_library_to_learner_and_withdraw(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    approve(s, submit(s))
    material_id, version_id = make_link(s)
    client, manager = f[0], f[5]
    assigned = client.post(
        BASE + "/assignments",
        headers=manager,
        json={
            "material_version_id": version_id,
            "class_id": s["class_id"],
            "request_key": str(uuid4()),
        },
    )
    assert assigned.status_code == 200, assigned.text
    assignment_id = assigned.json()["id"]
    assert client.get(BASE + "/mine", headers=s["learner"]).json()["total"] == 1
    assert client.get(BASE + f"/versions/{version_id}/content", headers=s["learner"]).json() == {
        "url": "https://example.org/lesson-1"
    }
    with Session(f[1]) as db:
        assert db.scalar(select(StudentMaterialGrant.id)) is not None
    old = client.post(
        BASE + "/assignments",
        headers=manager,
        json={
            "material_version_id": version_id,
            "class_id": s["class_id"],
            "request_key": assigned.json().get("request_key", str(uuid4())),
        },
    )
    assert old.status_code == 200
    assert (
        client.post(
            BASE + f"/{material_id}/withdraw", headers=manager, json={"reason": "Bad source"}
        ).status_code
        == 200
    )
    assert client.get(BASE + "/mine", headers=s["learner"]).json()["total"] == 0
    assert (
        client.get(BASE + f"/versions/{version_id}/content", headers=s["learner"]).status_code
        == 404
    )
    with Session(f[1]) as db:
        assert (
            db.scalar(
                select(MaterialAssignment.withdrawn_at).where(
                    MaterialAssignment.id == UUID(assignment_id)
                )
            )
            is None
        )


def test_teacher_student_permissions_and_file_scan(admissions, monkeypatch, tmp_path):  # noqa: F811
    s, f = admissions, admissions["f"]
    manager, client = f[5], f[0]
    teacher = login(client, "schedule-teacher@example.com")
    assert client.post(BASE, headers=s["learner"], json={"title": "Forbidden"}).status_code == 403
    assert (
        client.post(
            BASE, headers=teacher, json={"title": "Class notes", "class_id": s["class_id"]}
        ).status_code
        == 200
    )
    row = client.post(BASE, headers=manager, json={"title": "Image"}).json()
    monkeypatch.setattr("app.services.materials.storage_root", lambda: tmp_path)
    monkeypatch.setattr("app.services.materials.scan", lambda _path: "pending_check")
    pending = client.post(
        BASE + f"/{row['id']}/versions/file",
        headers=manager,
        data={"request_key": str(uuid4())},
        files={"upload": ("picture.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"fake"), "image/png")},
    )
    assert pending.status_code == 200, pending.text
    version_id = pending.json()["id"]
    assert pending.json()["file_status"] == "pending_check"
    assert client.post(BASE + f"/versions/{version_id}/publish", headers=manager).status_code == 409
    monkeypatch.setattr("app.services.materials.scan", lambda _path: "ready")
    assert (
        client.post(BASE + f"/versions/{version_id}/retry-scan", headers=manager).json()[
            "file_status"
        ]
        == "ready"
    )
    assert client.post(BASE + f"/versions/{version_id}/publish", headers=manager).status_code == 200
    with Session(f[1]) as db:
        version = db.get(MaterialVersion, UUID(version_id))
        assert version.object_key and version.checksum
    bad = client.post(
        BASE + f"/{row['id']}/versions/file",
        headers=manager,
        data={"request_key": str(uuid4())},
        files={"upload": ("script.exe", BytesIO(b"MZ" + b"x" * 30), "image/png")},
    )
    assert bad.status_code == 422


def test_revoked_teacher_assignment_blocks_class_material(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    client = f[0]
    teacher = login(client, "schedule-teacher@example.com")
    created = client.post(
        BASE, headers=teacher, json={"title": "Private class note", "class_id": s["class_id"]}
    )
    assert created.status_code == 200, created.text
    material_id = created.json()["id"]
    version = client.post(
        BASE + f"/{material_id}/versions/link",
        headers=teacher,
        json={"url": "https://example.org/note", "request_key": str(uuid4())},
    )
    assert version.status_code == 200, version.text
    version_id = version.json()["id"]
    assert client.get(BASE + f"/versions/{version_id}/content", headers=teacher).status_code == 200
    with Session(f[1]) as db:
        assignment = db.scalar(
            select(ClassTeacher).where(ClassTeacher.class_id == UUID(s["class_id"]))
        )
        assert assignment is not None
        db.delete(assignment)
        db.commit()
    listed = client.get(BASE, headers=teacher)
    assert listed.status_code == 200
    assert material_id not in {item["id"] for item in listed.json()["items"]}
    assert client.get(BASE + f"/versions/{version_id}/content", headers=teacher).status_code == 404
    assert (
        client.post(BASE + f"/versions/{version_id}/submit", headers=teacher).status_code
        in {403, 404}
    )


def test_curriculum_versions_keep_class_binding(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    client, manager = f[0], f[5]
    _, version_id = make_link(s)
    curriculum = client.post(BASE + "/curricula", headers=manager, json={"title": "Book 1"})
    assert curriculum.status_code == 200, curriculum.text
    curriculum_id, release_id = curriculum.json()["id"], curriculum.json()["version_id"]
    unit = client.post(
        BASE + f"/curriculum-versions/{release_id}/units",
        headers=manager,
        json={"title": "Unit 1", "position": 1},
    )
    assert unit.status_code == 200, unit.text
    assert (
        client.post(
            BASE + f"/curriculum-units/{unit.json()['id']}/materials",
            headers=manager,
            json={"material_version_id": version_id},
        ).status_code
        == 200
    )
    assert (
        client.post(
            BASE + f"/curriculum-versions/{release_id}/publish", headers=manager
        ).status_code
        == 200
    )
    assert (
        client.post(
            BASE + f"/courses/{f[6]['id']}/curricula",
            headers=manager,
            json={"curriculum_version_id": release_id, "primary": True},
        ).status_code
        == 200
    )
    assert (
        client.post(
            BASE + f"/classes/{s['class_id']}/curricula",
            headers=manager,
            json={"curriculum_version_id": release_id, "primary": True},
        ).status_code
        == 200
    )
    newer = client.post(BASE + f"/curricula/{curriculum_id}/clone", headers=manager)
    assert newer.status_code == 200, newer.text
    detail = client.get(BASE + f"/curricula/{curriculum_id}", headers=manager).json()
    assert len(detail["versions"]) == 2
    assert detail["versions"][0]["revision"] == 2
    assert detail["versions"][1]["id"] == release_id
    new_class = client.post(
        "/api/v1/classes", headers=manager, json={**f[9], "code": "CLASS-MATERIALS"}
    )
    assert new_class.status_code == 201, new_class.text
    with Session(f[1]) as db:
        binding = db.scalar(
            select(ClassCurriculum).where(ClassCurriculum.class_id == UUID(new_class.json()["id"]))
        )
        assert binding and str(binding.curriculum_version_id) == release_id


def test_file_range_replay_quota_and_tenant_fk(admissions, monkeypatch, tmp_path):  # noqa: F811
    f = admissions["f"]
    client, manager = f[0], f[5]
    monkeypatch.setattr("app.services.materials.storage_root", lambda: tmp_path)
    monkeypatch.setattr("app.services.materials.scan", lambda _path: "ready")
    material = client.post(BASE, headers=manager, json={"title": "Audio lesson"}).json()
    key = str(uuid4())
    content = b"ID3" + b"a" * 20

    def upload(target, request_key=key):
        return client.post(
            BASE + f"/{target}/versions/file",
            headers=manager,
            data={"request_key": request_key},
            files={"upload": ("lesson.mp3", BytesIO(content), "audio/mpeg")},
        )

    first = upload(material["id"])
    assert first.status_code == 200, first.text
    assert upload(material["id"]).json()["id"] == first.json()["id"]
    another = client.post(BASE, headers=manager, json={"title": "Second lesson"}).json()
    assert upload(another["id"]).status_code == 409
    version_id = first.json()["id"]
    assert client.post(BASE + f"/versions/{version_id}/publish", headers=manager).status_code == 200
    response = client.get(
        BASE + f"/versions/{version_id}/content", headers={**manager, "Range": "bytes=3-7"}
    )
    assert response.status_code == 206 and response.content == b"aaaaa"
    assert response.headers["content-range"] == "bytes 3-7/23"
    assert client.put(BASE + "/quota", headers=manager, json={"quota_bytes": 24}).status_code == 200
    large = client.post(
        BASE + f"/{another['id']}/versions/file",
        headers=manager,
        data={"request_key": str(uuid4())},
        files={"upload": ("large.mp3", BytesIO(content), "audio/mpeg")},
    )
    assert large.status_code == 413
    with Session(f[1]) as db:
        row = db.get(MaterialVersion, UUID(version_id))
        file_key = row.object_key
        duplicate = MaterialVersion(
            organization_id=UUID(f[3]),
            material_id=row.material_id,
            revision=99,
            kind="link",
            file_status="ready",
            source_url="https://example.org",
            metadata_snapshot={},
            size_bytes=0,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
    orphan = tmp_path / uuid4().hex
    orphan.write_bytes(b"old")
    os.utime(orphan, (time.time() - 90000, time.time() - 90000))
    with Session(f[1]) as db:
        assert cleanup_orphans(db, apply=False) == 1
        assert cleanup_orphans(db, apply=True) == 1
    assert not orphan.exists()
    assert (tmp_path / file_key).exists()


def test_parallel_uploads_respect_tenant_quota(admissions, monkeypatch, tmp_path):  # noqa: F811
    f = admissions["f"]
    if f[1].dialect.name != "postgresql":
        pytest.skip("row locking requires PostgreSQL")
    client, manager = f[0], f[5]
    monkeypatch.setattr("app.services.materials.storage_root", lambda: tmp_path)

    def slow_scan(_path):
        time.sleep(0.2)
        return "ready"

    monkeypatch.setattr("app.services.materials.scan", slow_scan)
    targets = [
        client.post(BASE, headers=manager, json={"title": f"Concurrent {i}"}).json()["id"]
        for i in range(2)
    ]
    assert client.put(BASE + "/quota", headers=manager, json={"quota_bytes": 25}).status_code == 200
    gate = Barrier(2)

    def upload(material_id):
        gate.wait(timeout=5)
        return client.post(
            BASE + f"/{material_id}/versions/file",
            headers=manager,
            data={"request_key": str(uuid4())},
            files={"upload": ("lesson.mp3", BytesIO(b"ID3" + b"x" * 20), "audio/mpeg")},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(upload, targets))
    assert sorted(response.status_code for response in outcomes) == [200, 413]
    usage = client.get(BASE + "/quota", headers=manager).json()
    assert usage["used_bytes"] == 23 and usage["quota_bytes"] == 25


def test_scheduled_publication_and_suspension_grant(admissions):  # noqa: F811
    s, f = admissions, admissions["f"]
    approve(s, submit(s))
    _, version_id = make_link(s)
    client, manager = f[0], f[5]
    future = now() + timedelta(days=1)
    planned = client.post(
        BASE + "/assignments",
        headers=manager,
        json={
            "material_version_id": version_id,
            "class_id": s["class_id"],
            "publish_at": future.isoformat(),
            "request_key": str(uuid4()),
        },
    )
    assert planned.status_code == 200, planned.text
    assert client.get(BASE + "/mine", headers=s["learner"]).json()["total"] == 0
    with Session(f[1]) as db:
        row = db.get(MaterialAssignment, UUID(planned.json()["id"]))
        row.publish_at = now() - timedelta(minutes=1)
        enrollment = db.scalar(select(Enrollment).where(Enrollment.class_id == UUID(s["class_id"])))
        enrollment.state = "suspended"
        period = db.scalar(
            select(EnrollmentPeriod).where(EnrollmentPeriod.enrollment_id == enrollment.id)
        )
        period.ends_at = now()
        db.commit()
    assert client.get(BASE + "/mine", headers=s["learner"]).json()["total"] == 1
