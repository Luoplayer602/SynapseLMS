# Mời thành viên qua email — 2026-09-23

Phần mở rộng IAM-03: mời giáo viên, giáo vụ và học viên; Root Admin có phiên hỗ trợ hợp lệ được mời thêm quản lý trung tâm. Không tạo tài khoản hoặc membership trước khi người nhận chấp nhận. Đăng ký khóa học/xét duyệt và chuyển trung tâm vẫn là các luồng độc lập.

## Quyền và quy tắc

- Quản lý trung tâm chỉ xem lời mời của trung tâm mình; không tạo, gửi lại hoặc thu hồi lời mời quản lý. Root phải mở phiên hỗ trợ đúng trung tâm, có lý do và thời hạn. Giáo viên/giáo vụ/học viên không quản lý lời mời.
- Người mời nhập tên, email, vai trò, lý do và thời hạn 1–30 ngày (mặc định 7). Email chuẩn hóa chữ thường; mỗi trung tâm/email chỉ có một lời mời đang chờ chưa hết hạn.
- Người mới tự đặt mật khẩu 12–128 ký tự. Người đã có tài khoản phải đăng nhập đúng email rồi bấm chấp nhận riêng; không đổi mật khẩu hoặc tên hiện có của họ.
- Chấp nhận thành công tạo membership và xác minh email nhờ bằng chứng sở hữu liên kết. Không tự đăng nhập người mới, không duyệt khóa học hoặc tự nâng quyền khác.
- Tài khoản đã có membership chưa kết thúc ở cùng trung tâm bị từ chối; membership ở trung tâm khác yêu cầu luồng chuyển trung tâm. Membership bị đình chỉ cũng không thể bị bỏ qua bằng lời mời. Root không nhận membership nghiệp vụ.
- Gửi lại cần lý do, cách lần gửi trước ít nhất 60 giây; liên kết cũ mất hiệu lực ngay. Có thể gửi lại lời mời hết hạn nếu chưa có lời mời đang chờ khác cho cùng email/trung tâm.
- Thu hồi cần lý do, không xóa lịch sử; không thu hồi lời mời đã chấp nhận để thay cho khóa membership. Muốn đổi vai trò/email của lời mời: thu hồi rồi tạo mới.

## Trạng thái và an toàn

Lời mời: `pending` → `accepted`, `revoked` hoặc `expired`. Hết hạn được tính theo thời điểm hiện tại khi đọc, không cần cron. Gửi lại lời mời hết hạn đưa nó về `pending` với token mới. Trạng thái email độc lập: `queued`, `sent`, `failed`; `sent` chỉ có nghĩa SMTP đã nhận, không chứng minh email vào hộp thư người dùng.

DB chỉ lưu digest token; API quản trị không trả liên kết bí mật. Token nằm trong fragment của liên kết email, được xóa khỏi thanh địa chỉ khi trang mở, không lưu browser storage. Tải lại trang cần mở lại link từ email. Mở link chỉ xem trước, chưa chấp nhận. Không chia sẻ link, ảnh chụp hoặc HAR có token.

Tạo/gửi lại/thu hồi/chấp nhận và kết quả gửi email có audit. API kiểm tra quyền hiện tại, trạng thái trung tâm, email và thời hạn; PostgreSQL khóa giao dịch và ràng buộc duy nhất bảo vệ trước request đồng thời. Rate limit phân biệt phương thức GET/POST, tránh việc tải danh sách tiêu hao hạn mức gửi lời mời.

## API

Các endpoint dưới `/api/v1`, cần `X-Synapse-Client: web`. API quản trị và chấp nhận tài khoản hiện có cần Bearer token; Root gửi thêm `X-Support-Session`.

| Endpoint | Dữ liệu / kết quả |
|---|---|
| `GET /organization/membership-invitations` | `status` tùy chọn; `limit` mặc định 20, tối đa 100; `offset`; trả `items`, `total`, `limit`, `offset` |
| `POST /organization/membership-invitations` | `email`, `display_name`, `role`, `reason`, `expires_days`; trả 201 |
| `POST /organization/membership-invitations/{id}/resend` | `reason`, `expires_days`; xoay token, cập nhật hạn dùng |
| `POST /organization/membership-invitations/{id}/revoke` | `reason`; trả 204 |
| `POST /membership-invitations/preview` | `token`; thông tin tối thiểu để người giữ link xem trước |
| `POST /membership-invitations/accept-new` | `token`, `display_name`, `password`; trả 201, không phát phiên đăng nhập |
| `POST /membership-invitations/accept` | `token`; cần đăng nhập đúng email, trả 200 |

Lỗi chính: `INVALID_INVITATION`, `INVITATION_CONFLICT`, `INVITATION_MEMBER_EXISTS`, `INVITATION_COOLDOWN`, `INVITATION_NOT_PENDING`, `INVITATION_LOGIN_REQUIRED`, `INVITATION_EMAIL_MISMATCH`, `INVITATION_TRANSFER_REQUIRED`. UI có thông báo Việt/Anh.

## Chạy bằng Docker

```powershell
docker compose build api web
docker compose up -d db mailpit
docker compose run --rm --no-deps api .venv/bin/alembic upgrade head
docker compose run --rm --no-deps api .venv/bin/alembic check
docker compose up -d --no-deps api web
```

Migration `20260922_0005` chỉ thêm bảng/index lời mời, không sửa tài khoản, mật khẩu hay membership hiện có. Không cần tắt database. Cấu hình SMTP và giới hạn môi trường phát triển xem [vòng đời tài khoản](./account-lifecycle.md). App: `http://localhost:5173`; hộp thư Mailpit: `http://localhost:8025`. Mailpit không gửi email ra ngoài.

## Checklist nghiệm thu thủ công

Dùng email thử nghiệm và cửa sổ ẩn danh riêng cho người nhận để không nhầm phiên Root/manager. Bấm làm mới danh sách sau thao tác ở cửa sổ khác; hiện chưa có cập nhật thời gian thực.

| Thao tác | Kết quả đạt | Dấu hiệu lỗi |
|---|---|---|
| Đăng nhập quản lý; hoặc Root → Trung tâm → nhập lý do mở hỗ trợ → Lời mời thành viên | Có form mời; chỉ Root có lựa chọn quản lý trung tâm | Giáo viên/giáo vụ/học viên quản lý được lời mời, hoặc Root thao tác tenant không cần hỗ trợ |
| Mời giáo viên bằng email mới, tên, lý do; mở Mailpit | Danh sách chờ tiếp nhận, có email; chưa có thành viên mới | Tạo membership trước khi người nhận chấp nhận; email không tới nhưng hiển thị đã gửi |
| Mở link trong cửa sổ ẩn danh; chưa bấm chấp nhận | Hiện trung tâm, email, vai trò và form đặt mật khẩu; lời mời vẫn chờ | Chỉ mở link đã kích hoạt tài khoản/membership |
| Nhập/xác nhận mật khẩu hợp lệ rồi chấp nhận, quay lại đăng nhập | Hồ sơ đúng trung tâm/vai trò, email đã xác minh; quản lý thấy đã tiếp nhận | Sai vai trò/trung tâm, mật khẩu không dùng được, hoặc chấp nhận lặp sinh thêm membership |
| Mở lại link đã dùng | Báo link không hợp lệ/hết hạn | Cho chấp nhận lần thứ hai |
| Tạo lời mời khác; gửi lại ngay rồi sau ít nhất 60 giây, có lý do | Lần đầu báo cần chờ; lần sau email mới tới, link cũ bị từ chối, link mới xem được | Cả hai link còn hiệu lực hoặc không có thông báo khi bị chặn |
| Thu hồi lời mời đang chờ, nhập lý do và xác nhận | Trạng thái đã thu hồi, link bị từ chối; hủy xác nhận thì không thay đổi | Link vẫn tạo được thành viên sau thu hồi |
| Mời email tài khoản có sẵn nhưng chưa có membership hiện hành | Phải đăng nhập bằng mật khẩu cũ rồi xác nhận riêng; tên/mật khẩu giữ nguyên | Link cho đặt lại mật khẩu tài khoản có sẵn hoặc tự tiếp nhận khi đăng nhập |
| Mời tài khoản đang thuộc trung tâm khác rồi thử chấp nhận | Thông báo cần chuyển trung tâm; không tạo membership thứ hai | Tự chuyển trung tâm hoặc bỏ qua membership đình chỉ |
| Đổi Việt/Anh; lọc trạng thái, làm mới, phân trang khi có hơn 20 lời mời | Nhãn/lỗi đúng ngôn ngữ; dữ liệu chỉ của trung tâm hiện tại | Lẫn dữ liệu trung tâm khác, mất/lặp bản ghi khi dữ liệu không đổi |

Nếu lỗi, ghi bước, vai trò, trung tâm thử nghiệm, thời điểm, thông báo và ảnh chụp đã che email/token. Không gửi mật khẩu hoặc `.env`.

## Kiểm thử tự động và phần còn lại

Kết quả 2026-09-23: **169 backend đạt, 10 skip**, **12 UI đạt, 6 E2E Chromium đạt**. Các skip là bản SQLite của test concurrency; các bản PostgreSQL đã chạy và đạt, gồm hai trung tâm đồng thời tiếp nhận cùng tài khoản mới/cũ. Ruff lint, ESLint và TypeScript/Vite build đạt. Format check các file thuộc luồng mời đạt; format check toàn backend còn 14 file có định dạng cũ chưa chỉnh để tránh thay đổi ngoài phạm vi. Cảnh báo dependency TestClient và reflection expression index SQLite vẫn như checkpoint trước.

Docker phát triển đã áp dụng migration 0005, schema check đạt và cập nhật API/web. Kiểm tra cuối: API/web/Mailpit HTTP 200, API/UI lời mời đã có; không có test helper trong OpenAPI. Chưa thay thế nghiệm thu thủ công của người dùng.

- Backend: vòng đời lời mời, quyền từng vai trò/root hỗ trợ, cách ly tenant, phân trang, chuẩn hóa email, hết hạn/thu hồi/gửi lại, SMTP lỗi/tác vụ cũ, bảo toàn tài khoản cũ, membership đình chỉ, atomic single-use và race giữa hai trung tâm trên PostgreSQL.
- UI: mở link không tự chấp nhận, mật khẩu xác nhận, tài khoản cũ, đăng nhập sai người, lựa chọn vai trò và xác nhận thu hồi. E2E: người mới hoàn tất lời mời/đăng nhập và người cũ đăng nhập/chấp nhận riêng; các luồng auth trước đó vẫn chạy.
- Test dùng schema PostgreSQL/SQLite tạm, email in-memory. Test helper reset rate limit/hộp thư không được đăng ký trong app thật.
- Email hiện chạy background trong process, chưa có queue bền vững/retry tự động. Nếu process dừng khi `queued`, hoặc gửi `failed`, quản lý cần gửi lại. Không ghi token thô ra log để khôi phục.
- Luồng tạo thành viên trực tiếp bằng mật khẩu khởi tạo vẫn giữ tương thích; chưa bắt buộc đổi mật khẩu lần đầu. Khuyến nghị dùng email mời cho nhân sự mới.
- IAM-03 chưa hoàn tất toàn bộ: còn tìm kiếm/phân trang danh sách thành viên, chính sách mật khẩu khởi tạo và hồ sơ nghiệp vụ. Bước tiếp theo đề xuất là hồ sơ học viên/thông tin liên hệ phục vụ xét duyệt; cần chốt phạm vi trước khi triển khai. Học liệu tiếp tục ở backlog bổ sung.
