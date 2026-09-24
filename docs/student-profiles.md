# Hồ sơ học viên — hợp đồng triển khai

Phạm vi được triển khai từ kế hoạch `student-profile-next-step.md`: tài khoản học viên đã có membership hoạt động, hồ sơ trung tâm và liên hệ phụ huynh; không có tài khoản phụ huynh hay duyệt khóa học.

## Dữ liệu và quyền

- `student_identities`: một danh tính học viên/user, mã `SL-` kèm 12 ký tự hex in hoa ngẫu nhiên, ràng buộc duy nhất toàn hệ thống. Mã không chứa ngày sinh/email; danh tính độc lập tenant để giữ mã khi xây luồng chuyển sau này.
- `student_profiles`: một hồ sơ/identity/trung tâm, họ tên bắt buộc 1–200 ký tự; ngày sinh, điện thoại, địa chỉ tùy chọn để lưu nháp. Email đăng nhập chỉ đọc. Không tạo hồ sơ tự động bằng GET hoặc migration.
- Điện thoại nếu nhập: 5–30 ký tự gồm số, dấu +, khoảng trắng, dấu ngoặc/dấu gạch. Ngày sinh không ở tương lai. UI nhắc bổ sung điện thoại nếu thiếu; không coi đây là quyết định đủ điều kiện đăng ký khóa học.
- Ghi chú nội bộ chỉ quản lý/giáo vụ/Root hỗ trợ thấy và sửa, không trả cho học viên. Không đồng bộ tên hồ sơ sang tên đăng nhập.
- Liên hệ phụ huynh tối đa 10/hồ sơ: họ tên, quan hệ, điện thoại bắt buộc; email tùy chọn; tối đa một liên hệ chính. Danh sách liên hệ được lưu thay thế nguyên tử cùng hồ sơ để kiểm tra một version thống nhất; ID liên hệ có thể đổi sau khi lưu. Chưa có bản ghi nghiệp vụ tham chiếu ID liên hệ.
- Quản lý/giáo vụ quản lý hồ sơ của tenant, Root cần phiên hỗ trợ; giáo viên chưa có quyền khi chưa có module phân công lớp. Học viên chỉ đọc/sửa hồ sơ cá nhân trong tenant hiện hành, không đổi mã/user/tenant/ghi chú nội bộ/trạng thái lưu trữ.
- Lưu trữ/khôi phục chỉ nhân sự được phép, có lý do và audit. Hồ sơ lưu trữ chỉ đọc đối với học viên; không khóa tài khoản. Không xóa cứng hồ sơ.
- Mọi cập nhật có `version` để từ chối ghi đè bản cũ (409). Audit chỉ ghi tên trường thay đổi, không ghi giá trị thông tin cá nhân hoặc nội dung ghi chú.

## API dưới /api/v1

- `GET /students`: tìm mã/tên (`q`), `status=active|archived|all`, phân trang `limit` 20–tối đa 100 và `offset`; danh sách không có ghi chú/liên hệ.
- `GET /students/candidates`: tài khoản student đang hoạt động trong tenant chưa có hồ sơ, tìm tên/email và phân trang; không dùng danh sách tài khoản toàn hệ thống.
- `POST /students`: nhân sự tạo hồ sơ từ `user_id` hợp lệ, `full_name`, trường cá nhân/ghi chú/liên hệ tùy chọn.
- `GET /students/me`: hồ sơ của học viên, trả 404 nếu chưa tạo; `POST /students/me` tạo từ chính tài khoản; `PATCH /students/me` cập nhật phần cá nhân kèm `version`.
- `GET/PATCH /students/{id}`: nhân sự xem/cập nhật hồ sơ tenant; PATCH kèm `version`.
- `POST /students/{id}/archive`: `version`, `archived` boolean, `reason`. Thao tác không đổi membership.
- Các request cần header khách web và xác thực như API hiện tại. Root gửi thêm phiên hỗ trợ. Không chấp nhận `organization_id` từ body.

Hồ sơ chưa gắn tài khoản, chuyển trung tâm, import, trình độ đầu vào, lịch sử khóa học/học phí, file/ảnh và AI nằm ngoài phần này.

## Lưu dữ liệu và giới hạn

PATCH hiện là cập nhật nguyên bộ phần hồ sơ được phép: gửi đầy đủ các trường form; trường tùy chọn bỏ qua nhận giá trị mặc định và có thể bị xóa. `guardians` thay thế toàn danh sách trong cùng transaction. Luôn gửi `version` từ lần GET gần nhất; lỗi 409 cần tải lại, không tự retry ghi đè. Học viên không được gửi `internal_notes`; server giữ nguyên ghi chú khi học viên sửa phần cá nhân.

Danh sách tìm kiếm không phân biệt hoa/thường theo database, chưa hỗ trợ tìm bỏ dấu tiếng Việt. Dữ liệu hiện chưa có module lớp/chi nhánh. Các request hồ sơ được tuần tự hóa bằng khóa tenant ngắn trên PostgreSQL để recheck quyền và bảo vệ cập nhật; cần đánh giá lại mức khóa nếu tải lớn. Không gửi dữ liệu hồ sơ cho AI.

## Docker và nghiệm thu

Migration `20260923_0006` chỉ thêm bảng/index mới. Không đổi dữ liệu tài khoản, phiên, lời mời hoặc membership hiện có. Sau khi test migration trên DB tạm:

```powershell
docker compose build api web
docker compose up -d db mailpit
docker compose run --rm --no-deps api .venv/bin/alembic upgrade head
docker compose run --rm --no-deps api .venv/bin/alembic check
docker compose up -d --no-deps api web
```

Không cần tắt database hoặc xóa volume. App ở `http://localhost:5173`. Nếu còn giao diện cũ, tải lại trang; Root có thể cần mở lại phiên hỗ trợ vì trạng thái hỗ trợ ở giao diện không giữ qua reload.

### Checklist người dùng

Chuẩn bị tài khoản học viên đã tiếp nhận lời mời hoặc tự đăng ký vào trung tâm. Chỉ mời mà chưa tiếp nhận thì chưa có tài khoản/membership để tạo hồ sơ. Dùng cửa sổ ẩn danh riêng cho học viên.

| Thao tác | Kết quả mong đợi / dấu hiệu lỗi |
|---|---|
| Mở chế độ tối/sáng; đổi Việt/Anh; thử đăng xuất | Chữ nút rõ trên nền tương ứng; đổi ngôn ngữ/đăng xuất hoạt động. Chữ đen trên nền tối là chưa đạt. |
| Root → Trung tâm → xem form thêm | Nhãn Tên trung tâm / Center name; có hướng dẫn mở hỗ trợ. Nhãn Họ và tên ở form tài khoản vẫn đúng. |
| Root mở hỗ trợ, hoặc đăng nhập quản lý/giáo vụ → Học viên → Tạo hồ sơ học viên | Chỉ tìm/chọn tài khoản student hoạt động của trung tâm chưa có hồ sơ; không thấy người của trung tâm khác. |
| Điền tên, điện thoại; thêm hai liên hệ, chọn liên hệ chính và lưu | Có mã SL- riêng, lưu đủ dữ liệu; chọn liên hệ thứ hai làm chính tự bỏ lựa chọn ở liên hệ thứ nhất. Lưu trùng cùng tài khoản bị chặn. |
| Giáo vụ nhập ghi chú nội bộ; học viên mở Hồ sơ học viên của tôi | Học viên thấy thông tin/liên hệ của mình, không có ghi chú nội bộ hoặc danh sách toàn trung tâm. |
| Học viên cập nhật địa chỉ/liên hệ, lưu rồi tải lại | Dữ liệu còn nguyên; tên đăng nhập, email, mật khẩu không bị đổi. |
| Học viên chưa có hồ sơ mở trang riêng, lưu chỉ tên | Có form tạo nháp, không tạo dữ liệu chỉ bằng mở trang. Lưu được, có nhắc thiếu điện thoại; vẫn đăng nhập bình thường. |
| Nhập ngày sinh tương lai, số điện thoại sai hoặc liên hệ thiếu trường bắt buộc | Form/API từ chối, không lưu một nửa hồ sơ. |
| Hai cửa sổ mở cùng hồ sơ; cửa sổ A lưu, B sửa rồi lưu | B báo hồ sơ đã thay đổi, giữ bản đang gõ để sao chép; cần Làm mới danh sách trước khi sửa tiếp. Không ghi đè thay đổi A. |
| Giáo vụ lưu trữ hồ sơ, xác nhận lý do; học viên làm mới | Danh sách mặc định ẩn hồ sơ; bộ lọc Đã lưu trữ thấy lại. Học viên xem được nhưng không sửa; vẫn đăng nhập được. Hủy xác nhận không đổi trạng thái. |
| Giáo vụ khôi phục có lý do | Giữ mã/thông tin/liên hệ; học viên sửa lại được sau làm mới. |
| Tìm theo tên/mã, lọc, chuyển trang khi có hơn 20 hồ sơ | Tổng/trang đúng, không lẫn tenant. Truy cập trái phép phải bị API chặn, không chỉ ẩn nút. |

Test tự động dùng tài khoản/schema/DB tạm; không seed hồ sơ cá nhân thật vào database Docker. Chưa thay thế nghiệm thu người dùng.

## Kết quả kiểm chứng

- Bàn giao Docker ngày 2026-09-24: xác nhận migration `20260923_0006 (head)`, schema check đạt; API/web/Mailpit HTTP 200. API/UI hồ sơ và CSS sửa theme đã triển khai; không có test helper trong OpenAPI.
- Toàn bộ backend SQLite/PostgreSQL: **199 passed, 12 skipped**. Các skip là bản SQLite của test concurrency; bản PostgreSQL đã chạy đạt. Bao gồm migration nâng/hạ/nâng và schema khớp model.
- Frontend: **17 UI tests, 8 E2E Chromium đạt**; Ruff lint, ESLint, TypeScript/Vite build đạt. Test theme đã thất bại đúng lỗi chữ đen trước sửa, sau sửa đạt cả sáng/tối và desktop/mobile; ảnh mobile đã được kiểm tra.
- Giữ mã khi membership chuyển được kiểm chứng bằng fixture, không có nghĩa luồng chuyển trung tâm thật đã được triển khai.
- Cảnh báo dependency TestClient/anyio và reflection expression index SQLite vẫn còn như trước; không có lỗi test. Chưa có audit accessibility toàn website hoặc load test production.
