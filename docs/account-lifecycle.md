# Vòng đời tài khoản — 2026-09-22

Phạm vi: xác minh email, quên/đặt lại mật khẩu và tự quản lý phiên đăng nhập. Tiếp nối IAM-06, IAM-02 và phần email của IAM-08; giữ một membership hoạt động/tài khoản. Cập nhật 2026-09-23: đã bổ sung [mời thành viên qua email](./membership-invitations.md). Bắt buộc đổi mật khẩu khởi tạo, hồ sơ học viên và chi nhánh vẫn thuộc các bước tiếp theo.

## Cách thử bằng Docker

```powershell
docker compose build api web
docker compose up -d db mailpit
docker compose run --rm --no-deps api .venv/bin/alembic upgrade head
docker compose up -d --no-deps api web
```

Migration `20260922_0004` thêm `users.email_verified_at`, thông tin trình duyệt của phiên và bảng `account_tokens`. Tài khoản cũ giữ nguyên mật khẩu/quyền, email mặc định chưa xác minh; không gửi email hàng loạt khi migration. Phiên cũ không có nhãn trình duyệt sẽ hiển thị thiết bị không xác định.

1. Mở ứng dụng `http://localhost:5173`, đăng ký học viên tại trung tâm đang nhận đăng ký.
2. Mở hộp thư `http://localhost:8025`, tìm email vừa tạo. Mở liên kết và bấm **Xác minh email**. Đăng nhập để xem trạng thái trên Hồ sơ; có nút gửi lại.
3. Ở trang đăng nhập chọn **Quên mật khẩu**, nhập email và kiểm tra Mailpit. Mở liên kết, nhập/xác nhận mật khẩu mới. Mọi phiên cũ bị thu hồi; đăng nhập lại bằng mật khẩu mới.
4. Đăng nhập cùng tài khoản ở hai trình duyệt hoặc một cửa sổ ẩn danh. Trong sidebar chọn **Phiên đăng nhập**, kết thúc riêng một phiên, các phiên khác hoặc toàn bộ. Trình duyệt bị thu hồi bị từ chối ở yêu cầu API tiếp theo; chưa có thông báo đẩy tức thời.

Mailpit chỉ giữ email cục bộ, không chuyển tiếp tới người nhận bên ngoài. UI/SMTP chỉ mở trên loopback; API dùng tên nội bộ `mailpit`. Mailpit không có volume bền vững: email thử nghiệm có thể mất khi tái tạo container; không ảnh hưởng PostgreSQL. Cổng mặc định theo [tài liệu Mailpit](https://mailpit.axllent.org/docs/install/docker/).

Không cần tắt database để sửa mã. Rebuild API/web và áp dụng migration trước khi chạy bản mới. Link được xóa khỏi thanh địa chỉ sau khi trang tải; nếu tải lại trang hành động, hãy mở lại liên kết từ email.

## Hợp đồng API

Tiền tố `/api/v1/auth`; các endpoint sau yêu cầu `X-Synapse-Client: web`, kiểm tra Origin khi có và có rate limit. Endpoint phiên cần Bearer token. Phản hồi thành công đặt `Cache-Control: no-store`; lỗi chuẩn không trả lại giá trị token/mật khẩu.

| Endpoint | Dữ liệu / kết quả |
|---|---|
| `POST /request-verification` | `{email}` → `202 {status: "accepted"}` |
| `POST /verify-email` | `{token}` → `204`; không cần đăng nhập |
| `POST /forgot-password` | `{email}` → cùng phản hồi 202 với email tồn tại/không tồn tại/bị khóa |
| `POST /reset-password` | `{token, password}` → `204`, thu hồi mọi phiên và liên kết còn hiệu lực |
| `GET /me` | Bổ sung `email_verified_at`, null khi chưa xác minh |
| `GET /sessions` | Phiên còn hiệu lực của chính tài khoản: ID, ngày tạo/hết hạn UTC, trình duyệt, `is_current` |
| `DELETE /sessions/{id}` | `204`; chỉ phiên của chính tài khoản, kể cả Root không được thao tác phiên người khác qua API này |
| `POST /sessions/revoke` | `{scope: "others"}` giữ phiên hiện tại; `{scope: "all"}` kết thúc toàn bộ và xóa cookie |

Không có GET làm thay đổi trạng thái xác minh/mật khẩu. Trang hành động cần bấm xác nhận để trình quét email không tự dùng liên kết. Token ở URL fragment, được gửi trong POST body và không lưu vào localStorage/sessionStorage. URL được tạo từ `SYNAPSE_FRONTEND_URL`, không lấy Host/Origin do client gửi.

Xác minh email ghi nhận quyền sở hữu địa chỉ; chưa đặt thêm điều kiện chặn đăng nhập hoặc tenant API theo trạng thái này. Xét duyệt đăng ký khóa học vẫn là quy trình nghiệp vụ riêng. Khôi phục mật khẩu không tự mở khóa tài khoản/membership/trung tâm, không đổi vai trò và không tự đánh dấu email đã xác minh.

## Quy tắc và vận hành email

- Token ngẫu nhiên 48 byte, DB chỉ lưu SHA-256; gắn với user, email khi phát hành và mục đích. Token sai mục đích, hết hạn, dùng rồi, thu hồi, user bị khóa hoặc đổi email đều không hợp lệ.
- Xác minh mặc định 24 giờ, đặt lại mật khẩu 30 phút. Sau 60 giây có thể gửi lại; phát hành mới vô hiệu hóa liên kết cũ cùng mục đích. Cooldown theo tài khoản dùng DB, áp dụng cả khi thay IP. Yêu cầu email giới hạn 5 lần/phút/IP; xác nhận link/thao tác phiên mặc định 10 lần/phút theo action/IP.
- PostgreSQL khóa user để tuần tự hóa phát hành/tiêu thụ token, đổi/reset mật khẩu, đăng nhập và thu hồi phiên. Tiêu thụ thêm conditional update để chỉ một request thành công. SQLite phục vụ phát triển, không thay thế kiểm thử concurrency trên PostgreSQL.
- Đổi mật khẩu bằng mật khẩu hiện tại vô hiệu hóa các link khôi phục đang chờ. Reset thu hồi mọi phiên và link chưa dùng; access/refresh cũ bị từ chối, không tự đăng nhập sau reset.
- Audit ghi yêu cầu email, lỗi gửi, xác minh, reset và thu hồi phiên. Log/audit không chứa token thô, mật khẩu hay nội dung email. User-Agent là nhãn do client cung cấp, không phải bằng chứng định danh thiết bị.
- Gửi email chạy sau phản hồi HTTP trong tác vụ nền của process. Lỗi SMTP được ghi audit và hủy link đã tạo, không tiết lộ tài khoản qua phản hồi công khai. Chưa có hàng đợi bền vững/retry tự động: nếu API dừng giữa chừng hoặc SMTP lỗi, người dùng cần yêu cầu lại sau một phút. Không bật SMTP debug logging.

Adapter dùng thư viện chuẩn [smtplib](https://docs.python.org/3/library/smtplib.html), hỗ trợ kết nối nội bộ, STARTTLS và SSL/TLS với kiểm tra chứng chỉ.

| Biến cấu hình | Mặc định / ý nghĩa |
|---|---|
| `SYNAPSE_FRONTEND_URL` | `http://localhost:5173`, địa chỉ tin cậy dùng trong email |
| `SYNAPSE_MAIL_BACKEND` | `disabled` khi chạy trực tiếp; Compose cấu hình `smtp` tới Mailpit |
| `SYNAPSE_MAIL_FROM` | `noreply@example.com`; thay bằng địa chỉ thuộc tên miền gửi thật khi triển khai |
| `SYNAPSE_SMTP_HOST`, `SYNAPSE_SMTP_PORT` | `localhost`, `1025`; Compose đặt host `mailpit` |
| `SYNAPSE_SMTP_SECURITY` | `none`, `starttls` hoặc `ssl` |
| `SYNAPSE_SMTP_USERNAME`, `SYNAPSE_SMTP_PASSWORD` | Tài khoản SMTP nếu cần, mật khẩu là secret |
| `SYNAPSE_SMTP_TIMEOUT` | 10 giây, giới hạn 1–30 giây |
| `SYNAPSE_VERIFICATION_MINUTES` | 1440, giới hạn 5–1440 |
| `SYNAPSE_RESET_MINUTES` | 30, giới hạn 5–60 |

API chạy trực tiếp: đặt cấu hình vào `backend/.env` hoặc biến môi trường process, bật `smtp` rồi `docker compose up -d mailpit`. `.env` ở root dùng cho Compose nội suy; Compose hiện cố định SMTP cục bộ và không tự nhận thông tin SMTP thật từ đó. Production cần deployment riêng: HTTPS frontend/CORS, cookie Secure, JWT secret cố định và SMTP có TLS; cấu hình production từ chối mail disabled hoặc SMTP không TLS.

## Kiểm thử

```powershell
Set-Location backend
uv run ruff check .
uv run pytest
uv run python -m tests.mailpit_smoke
Set-Location ..
docker compose run --rm --no-deps -e SYNAPSE_TEST_POSTGRES=1 -v "${PWD}/backend/tests:/app/tests:ro" api uv run --locked --group dev pytest
Set-Location frontend
npm.cmd run lint
npm.cmd run test
npm.cmd run build
npm.cmd run test:e2e
```

Backend mặc định chặn SMTP thật bằng hộp thư in-memory. PostgreSQL test tạo schema riêng và dọn sau test. SMTP smoke là lệnh riêng, chỉ gửi email tổng hợp tới Mailpit, kiểm tra liên kết qua API Mailpit và không tạo tài khoản. E2E dùng DB tạm và hộp thư chỉ đăng ký trong `tests/e2e_server.py`; endpoint hộp thư test không tồn tại ở app thật.

Các tình huống: dùng lại/hết hạn/sai mục đích/đổi email/khóa tài khoản; gửi lại/cooldown/lỗi SMTP không lộ thông tin; reset vô hiệu access/refresh của nhiều phiên; đổi mật khẩu hủy link reset; không xem/thu hồi phiên người khác; xác nhận thao tác trên UI; PostgreSQL đồng thời dùng link/gửi lại; migration nâng/hạ/nâng bảo toàn dữ liệu cũ.

Kết quả 2026-09-22: 126 test backend SQLite/PostgreSQL đạt, 5 skip chỉ thuộc SQLite concurrency (các bản PostgreSQL đạt); 8 test UI và 4 E2E Chromium đạt. Ruff, ESLint, TypeScript/Vite build, SMTP smoke và Alembic schema check đạt. Migration đã áp dụng vào Docker phát triển; API/web/Mailpit đều trả HTTP 200. Còn các cảnh báo dependency TestClient và giới hạn reflection expression index trên SQLite như giai đoạn trước.
