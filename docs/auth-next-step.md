# Kế hoạch bước tiếp theo — Xác thực sử dụng được

Trạng thái: API/UI xác thực và quản trị tài khoản/trung tâm đã triển khai. Phạm vi thực tế, cấu hình, kiểm thử và phần còn lại ở [hướng dẫn vận hành](./auth-operations.md). Quyền nghiệp vụ lớp/buổi/chi nhánh sẽ làm cùng các module tương ứng.

## Mục tiêu và giới hạn

Hoàn thiện một luồng: chọn trung tâm được phép đăng ký → tạo tài khoản học viên → đăng nhập → xem hồ sơ → làm mới phiên → đăng xuất. Thực hiện tuần tự bởi một người và AI, dùng ID IAM hiện có, không tạo thêm story AUTH trùng Jira.

Giữ một membership hoạt động và một vai trò/tài khoản. Tạo tài khoản không đồng nghĩa duyệt đăng ký khóa học. Root Admin không có membership nghiệp vụ; quyền hỗ trợ tenant cần phiên riêng có lý do và audit.

## Các checkpoint

| Thứ tự | Backlog | Công việc | Điều kiện hoàn tất |
|---|---|---|---|
| 1 | IAM-08, IAM-01; phụ thuộc ORG-06 | Cấu hình secret, bootstrap Root Admin bằng CLI, dữ liệu hai trung tâm test; API đăng ký/đăng nhập và `/auth/me` | Tạo tài khoản và membership học viên trong một transaction; đăng nhập đúng/sai và trùng email được kiểm thử |
| 2 | IAM-02 | Access token, refresh token rotation, phát hiện dùng lại token và logout | Hai refresh đồng thời không sinh hai nhánh token hợp lệ; logout/khóa user thu hồi quyền truy cập |
| 3 | IAM-04, IAM-05, IAM-03 | Dependency xác thực, membership, tenant và quyền; khóa tài khoản/trung tâm | Mọi API bảo vệ kiểm tra trạng thái hiện tại; test chéo hai tenant và từng vai trò đạt |
| 4 | IAM-01, IAM-08, PLT-09 | UI Việt/Anh đăng ký/đăng nhập, hồ sơ và sidebar theo vai trò | Luồng E2E từ trình duyệt đạt, lỗi/đang tải/phiên hết hạn có trạng thái rõ |

Checkpoint 1 phải có cấu hình tenant cho phép đăng ký trước khi mở public registration. Dùng seed/CLI cho phát triển trong khi màn hình ORG-06 chưa hoàn tất. Trung tâm không công khai chỉ nhận đăng ký qua mã mời; không cho người dùng tự truyền một UUID bất kỳ để tham gia.

## Hợp đồng API dự kiến

Tất cả đường dẫn dưới `/api/v1` và lỗi theo `api-conventions.md`.

| Endpoint | Nội dung |
|---|---|
| `GET /organizations/public` | Danh sách thông tin công khai tối thiểu của trung tâm đang cho đăng ký |
| `POST /auth/register` | Email, mật khẩu, tên hiển thị, trung tâm công khai hoặc mã mời; vai trò luôn là student |
| `POST /auth/login` | Kiểm tra email/mật khẩu, tạo phiên và cấp token |
| `GET /auth/me` | Hồ sơ, trạng thái tài khoản, membership hiện tại và khả năng truy cập tenant |
| `POST /auth/refresh` | Tiêu thụ refresh token cũ một lần, phát hành token mới trong cùng transaction |
| `POST /auth/logout` | Thu hồi phiên hiện tại, xóa cookie; gọi lại vẫn thành công |

Đăng ký từ chối trường tự gán `is_root_admin`, `role` và trạng thái tài khoản. Nếu đã có tài khoản/membership, phải đăng nhập và dùng luồng chuyển trung tâm, không tạo membership thứ hai. Root Admin được bootstrap qua CLI dùng nhập mật khẩu ẩn; không có public endpoint tạo Root Admin hoặc mật khẩu mặc định.

## Quyết định triển khai đề xuất

- Mật khẩu dùng Argon2id; thư viện và tham số được kiểm tra khi triển khai. Không ghi mật khẩu, token hay mã mời vào log. Chặn brute force trên login/register/refresh; lỗi login không phân biệt email không tồn tại với mật khẩu sai.
- Access token JWT ngắn hạn, đề xuất 15 phút; refresh session tối đa 7 ngày, có cấu hình. Claim chứa user/session, issuer/audience và thời hạn; tenant/quyền hiện tại phải được kiểm chứng trong database, không chỉ tin claim cũ.
- Frontend giữ access token trong bộ nhớ. Refresh token trong cookie HttpOnly; production dùng Secure, cấu hình SameSite/CORS/Origin và CSRF phù hợp. Không lưu refresh token trong localStorage. Đường dẫn cookie phải bao phủ cả refresh và logout.
- Dùng khóa giao dịch PostgreSQL để rotation nguyên tử. Token cũ bị dùng lại sẽ thu hồi cả phiên; commit việc thu hồi trước khi trả lỗi, không rollback mất thao tác thu hồi. Frontend gộp request refresh đồng thời và phối hợp giữa các tab để hạn chế tự kích hoạt phát hiện replay.
- Mỗi request xác thực kiểm tra user/session còn hoạt động, phiên chưa hết hạn/thu hồi. API tenant kiểm tra thêm organization và membership hiện tại. Khóa user/logout có hiệu lực ngay ở request tiếp theo. User không có tenant hợp lệ vẫn có thể xem phần hồ sơ cá nhân được phép.
- Đổi membership hoặc vai trò thu hồi các phiên liên quan; tài liệu/khóa học luôn tính quyền từ trạng thái hiện tại. Root không có phiên hỗ trợ hợp lệ thì từ chối API dữ liệu tenant.
- Xác minh email, đổi/quên mật khẩu và kênh email là hạng mục tiếp theo; trước khi mở đăng ký công khai trên internet phải hoàn thiện kiểm chứng email và chống lạm dụng. Không báo email đã xác minh nếu chưa có luồng đó.

## Kiểm thử và nghiệm thu

- Register: email hoa/thường, hai request trùng đồng thời, trung tâm khóa/không công khai, mã mời sai/hết hạn, chèn vai trò đặc quyền; không để lại user mồ côi khi tạo membership lỗi.
- Login/me: mật khẩu sai, user khóa, JWT sai chữ ký/issuer/audience/hết hạn, session thu hồi; không trả password hash/digest.
- Refresh/logout: token hết hạn, replay, hai request đồng thời, logout lặp lại, lỗi transaction; digest tồn tại nhưng token thô không có trong DB/log.
- RBAC: tenant A không đọc/sửa tài nguyên B, root không tự bỏ qua tenant, giáo viên không lấy quyền giáo vụ; kiểm tra sau đổi quyền/khóa trung tâm.
- Chạy unit/API test cục bộ, integration/concurrency bằng PostgreSQL Docker và E2E trên trình duyệt. Không chỉ dùng SQLite để chứng minh khóa giao dịch.
- Chỉ đánh dấu story Done khi đạt AC của story, không coi việc đã có model là đã hoàn tất endpoint hoặc UI.

Không cần tắt toàn bộ Docker. Giữ PostgreSQL, chạy integration trong schema test riêng; rebuild API/web khi thay mã nguồn vì Compose hiện không hot-reload. Khi schema thay đổi: test migration trước, áp dụng migration rồi cập nhật service.
