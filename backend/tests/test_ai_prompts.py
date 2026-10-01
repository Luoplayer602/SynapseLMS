from app.services.ai.prompts import render, validate_template
from tests.test_auth_api import login, seed_user

BASE = "/api/v1/ai/prompts"


def test_prompt_version_publish_and_rollback(api):
    client, engine, (org, _), _ = api
    seed_user(engine, org, root=True, email="prompt-root@example.com")
    root = login(client, "prompt-root@example.com")
    body = {
        "task": "progress_summary",
        "locale": "vi",
        "body": "Bạn giúp học viên xem tiến độ {task} bằng ngôn ngữ {locale}. "
        "Chỉ dùng nguồn dữ liệu được cung cấp.",
    }
    first = client.post(BASE, headers=root, json=body)
    assert first.status_code == 200, first.text
    one = first.json()["id"]
    assert (
        client.post(f"{BASE}/{one}/publish", headers=root, json={"reason": "Kiểm thử"}).status_code
        == 409
    )
    assert client.post(f"{BASE}/{one}/test", headers=root).status_code == 200
    assert (
        client.post(
            f"{BASE}/{one}/publish", headers=root, json={"reason": "Đã kiểm thử"}
        ).status_code
        == 200
    )
    body["body"] += " Trình bày thật ngắn gọn."
    two = client.post(BASE, headers=root, json=body).json()["id"]
    assert client.post(f"{BASE}/{two}/test", headers=root).status_code == 200
    assert (
        client.post(
            f"{BASE}/{two}/publish", headers=root, json={"reason": "Đổi giọng văn"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{BASE}/{one}/publish", headers=root, json={"reason": "Quay lại bản cũ"}
        ).status_code
        == 200
    )
    rows = client.get(BASE, headers=root).json()["items"]
    assert next(x for x in rows if x["id"] == one)["active"]
    assert not next(x for x in rows if x["id"] == two)["active"]


def test_prompt_variables_do_not_control_server_policy():
    from app.core.errors import APIError

    for body in ["hello {secrets}" * 5, "hello {task.__class__}" * 5, "hello {task[0]}" * 5]:
        try:
            validate_template(body)
        except APIError:
            pass
        else:
            raise AssertionError("Invalid placeholder accepted")
    text = render("Hãy tóm tắt {task} cho {locale}. Nguồn từ server.", "progress_summary", "vi")
    assert "Use only the supplied facts" in text
