# Nền tảng xác thực — AUTH-01

Phạm vi: model và migration phục vụ IAM-01, IAM-02, IAM-08. AUTH-01 là tên bước triển khai, không phải một story Jira mới. API đăng ký/đăng nhập và giao diện chưa được triển khai ở bước này.

## Quy tắc được giữ nguyên

- Tài khoản toàn hệ thống; email duy nhất sau khi bỏ khoảng trắng hai đầu và chuyển chữ thường. Database có unique index trên `lower(trim(email))`; ORM chuẩn hóa khi gán email. API sau này phải validate email và dùng cùng biểu thức khi tra cứu tài khoản cũ.
- Một tài khoản nghiệp vụ chỉ có một membership hoạt động, với một vai trò thuộc `organization_manager`, `staff`, `teacher`, `student`. Membership cũ được giữ khi chuyển trung tâm.
- Root Admin là cờ cấp hệ thống, không phải vai trò membership. Quy tắc cấm gán membership cho Root Admin sẽ được kiểm tra ở service; AUTH-01 chưa có service này.
- Đăng ký tài khoản khác với đăng ký khóa học. Người học có thể đăng nhập/xem hồ sơ trước khi yêu cầu đăng ký khóa được duyệt. Không dùng trạng thái chờ duyệt khóa học để khóa tài khoản.
- Quyền vào tenant sau này phải kiểm tra đồng thời tài khoản, trung tâm và membership còn hoạt động. Root Admin vào tenant qua phiên hỗ trợ có lý do và audit; không tự động bỏ qua kiểm tra tenant.

## Dữ liệu mới

| Bảng | Nội dung |
|---|---|
| `users` | Thêm `display_name`, `password_changed_at` nullable để tương thích dữ liệu cũ; vẫn dùng `is_active` để khóa tài khoản |
| `user_memberships` | Thêm CHECK cấm membership vừa hoạt động vừa có `ended_at`; giữ unique index một membership hoạt động/user |
| `auth_sessions` | Một lần đăng nhập/thiết bị, chủ tài khoản, hạn hết hiệu lực và thời điểm thu hồi |
| `refresh_tokens` | Digest SHA-256 duy nhất, phiên sở hữu, thời hạn và thời điểm đã sử dụng |

Không lưu refresh token thô. `auth_sessions.id` định danh cả chuỗi token xoay vòng; giữ bản ghi token đã sử dụng để API sau này phát hiện phát lại và thu hồi phiên. Khóa ngoại và CHECK hiện bảo vệ quan hệ, độ dài digest và thời hạn sau thời điểm tạo. Việc token thực sự là digest, không quá hạn phiên, xoay vòng nguyên tử và kiểm tra thu hồi thuộc bước service kế tiếp; model đơn thuần chưa cung cấp những bảo đảm đó.

## Migration và kiểm thử

Revision `20260920_0002` bổ sung trên `20260919_0001`. Migration cần kết nối database để kiểm tra dữ liệu cũ; không dùng chế độ sinh SQL offline cho revision này. Nếu có email trùng sau chuẩn hóa hoặc membership hoạt động có ngày kết thúc, migration dừng trước DDL, không tự gộp tài khoản. Email và password hash cũ giữ nguyên.

Test sử dụng database SQLite tạm hoặc schema PostgreSQL tên `test_auth_<uuid>`; schema test được dọn sau mỗi test. Không hạ cấp schema ứng dụng để kiểm thử. Chạy từ thư mục gốc khi database Docker đã hoạt động:

```powershell
docker compose build api
docker compose run --rm --no-deps -e SYNAPSE_TEST_POSTGRES=1 -v "${PWD}/backend/tests:/app/tests:ro" api uv run --locked --group dev pytest
docker compose run --rm --no-deps api .venv/bin/alembic upgrade head
docker compose up -d --no-deps api
```

Test bao gồm email trùng qua SQL trực tiếp, một membership hoạt động, lịch sử chuyển, vai trò sai, membership đã kết thúc nhưng vẫn hoạt động, khóa ngoại phiên, hash trùng, hạn token/phiên, lưu lịch sử rotation và nâng/hạ/nâng migration với dữ liệu cũ. Hạ cấp loại bỏ dữ liệu phiên và các trường bổ sung; chỉ thử trên schema test, không dùng để rollback dữ liệu vận hành. SQLite cần phiên bản >= 3.35 để hạ cấp bằng DROP COLUMN trực tiếp, tránh tái tạo bảng users làm mất membership qua cascade.

## Các bước tiếp theo

Biểu thức `EmailKey` dùng cách biên dịch riêng theo database để khớp dạng index PostgreSQL phản hồi về Alembic; cách mở rộng dựa trên [SQLAlchemy compilation extension](https://docs.sqlalchemy.org/en/20/core/compiler.html). Có test `alembic check` để phát hiện model và schema không đồng bộ. SQLite không phản chiếu đầy đủ expression index nên tính duy nhất được kiểm tra thêm bằng INSERT thực tế.

Kết quả ngày 2026-09-20: Ruff đạt; 19 test cục bộ đạt; 34 test trong Docker trên SQLite/PostgreSQL đạt. Migration `20260920_0002` đã áp dụng vào PostgreSQL phát triển. Còn cảnh báo deprecation của TestClient và cảnh báo reflection expression index của SQLite; chưa có lỗi test. Phiên và token mới chỉ là cấu trúc lưu trữ, chưa có luồng xác thực cho người dùng.

1. IAM-08/IAM-01: validation, hash mật khẩu, đăng ký học viên với trung tâm được chọn, đăng nhập và `/auth/me`; client không được tự gán vai trò/root admin.
2. IAM-02: access token, refresh rotation có khóa giao dịch, phát hiện phát lại, logout/thu hồi phiên. Kiểm thử hai request refresh đồng thời.
3. IAM-04/IAM-05: ma trận quyền và tenant dependency dựa trên membership xác thực, test truy cập chéo tenant; phiên hỗ trợ Root Admin có audit.
4. Giao diện đăng ký/đăng nhập, hồ sơ và sidebar theo vai trò. Không xây màn chọn giữa nhiều membership hoạt động cho tài khoản nghiệp vụ.
