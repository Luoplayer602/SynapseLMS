# Kế hoạch phiên tiếp theo — sửa giao diện và hồ sơ học viên

Trạng thái: người dùng đã duyệt triển khai với Astra High. Phần A và B đã có code và kiểm thử; hợp đồng thực tế, giới hạn và checklist ở [hồ sơ học viên](./student-profiles.md). Nội dung dưới đây giữ lại kế hoạch đã duyệt, không thay thế trạng thái bàn giao trong myplan. Căn cứ: người dùng báo test OK luồng lời mời; lỗi nghiệm thu nằm trong `test-feedback.md`.

## Phần A — khép lại phản hồi giao diện

1. Tái hiện BUG-001 và BUG-002, ghi nhận giao diện sáng/tối trước sửa.
2. Đổi riêng nhãn tên trung tâm bằng khóa dịch Việt/Anh; không đổi nhãn họ tên ở hồ sơ người dùng.
3. Chuẩn hóa màu nút theo theme, gồm đổi ngôn ngữ/đăng xuất; rà hover, focus bàn phím, disabled và nút primary. Không thiết kế lại toàn giao diện hoặc thêm bộ chọn theme trong phần này.
4. Thêm hướng dẫn ngắn cho Root về mở phiên hỗ trợ để thấy chức năng theo trung tâm (UX-001), không nới phân quyền.
5. Chạy UI test, E2E auth/lời mời, lint/build; kiểm tra sáng/tối, Việt/Anh, desktop/mobile. Rebuild web, không cần migration hoặc tắt database.

Điều kiện bàn giao: nhãn đúng ngữ cảnh; nút đọc rõ trên cả hai theme; đăng xuất/đổi ngôn ngữ không hồi quy; Root chưa mở hỗ trợ vẫn không truy cập tenant. Cập nhật trạng thái từng lỗi sau khi xác minh, không đóng chỉ vì đã sửa CSS.

## Phần B — hồ sơ học viên cơ bản

Backlog liên quan: STU-01, STU-02, STU-07 và phần hoàn thiện hồ sơ của IAM-08. Không đánh dấu toàn bộ IAM-08 Done vì chưa có luồng đăng ký/duyệt khóa học.

### 1. Chốt hợp đồng dữ liệu và quyền trước migration

- Tách danh tính đăng nhập (`User`) khỏi hồ sơ học viên và thông tin nghiệp vụ thuộc trung tâm. Thiết kế mã học viên duy nhất toàn hệ thống, ổn định khi chuyển trung tâm; không tái cấp mã chỉ vì đổi tenant.
- Đề xuất phần đầu chỉ tạo hồ sơ cho tài khoản có membership học viên hợp lệ trong tenant. Học viên chưa có tài khoản được mời trước; hồ sơ ngoại tuyến/chưa gắn tài khoản là phần mở rộng, cần xác nhận nếu muốn đưa vào ngay.
- Trường đề xuất: mã tự sinh, họ tên hồ sơ, ngày sinh, điện thoại, địa chỉ; ghi chú nội bộ tách riêng. Email đăng nhập chỉ đọc, không thay đổi qua API hồ sơ. Không thu giấy tờ định danh hoặc upload tài liệu trong phần này.
- Liên hệ phụ huynh: họ tên, quan hệ, điện thoại, email tùy chọn, liên hệ chính. Không tạo tài khoản phụ huynh. Mỗi hồ sơ có thể có nhiều liên hệ nhưng tối đa một liên hệ chính.
- Chốt trường bắt buộc và quy tắc hoàn thiện hồ sơ trong đặc tả trước code; đề xuất lưu nháp thiếu thông tin, hiển thị phần còn thiếu, không tạo thêm quy trình duyệt hồ sơ riêng hoặc chặn đăng nhập.
- Quản lý/giáo vụ xem và sửa trong tenant; học viên chỉ xem/sửa phần cá nhân của mình, không xem ghi chú nội bộ hay tự đổi mã/tenant/user/trạng thái lưu trữ. Root cần phiên hỗ trợ. Giáo viên chưa được mở danh sách toàn trung tâm; quyền xem học viên lớp mình sẽ làm cùng module lớp.
- Hồ sơ lưu trữ mềm, có lý do/audit; không xóa user hoặc tự khóa đăng nhập. Tách rõ trạng thái hồ sơ và trạng thái membership.

Đầu ra: cập nhật đặc tả dữ liệu/RBAC và hợp đồng API với các mặc định được xác nhận; nếu cần thay đổi quy tắc sản phẩm thì hỏi trước, không tự mở rộng.

### 2. Backend và migration

- Thêm cấu trúc hồ sơ/liên hệ, khóa ngoại và ràng buộc tenant; mã học viên unique toàn hệ thống ở DB, không chỉ kiểm tra trên form.
- API dự kiến dưới `/api/v1`: `GET/POST /students`, `GET/PATCH /students/{id}`, thao tác lưu trữ/khôi phục có lý do; `GET/PATCH /students/me` cho học viên; API liên hệ được scope qua hồ sơ cha. Khai báo route `me` trước route ID động.
- Danh sách tìm theo mã/tên, lọc trạng thái, phân trang server; không trả toàn bộ liên hệ hoặc ghi chú trong danh sách.
- Kiểm tra ngày sinh không ở tương lai, độ dài/định dạng đầu vào, liên hệ chính duy nhất, chống tạo hồ sơ trùng khi gửi đồng thời và chống ghi đè cập nhật cũ.
- Audit thao tác, actor, tenant và trường thay đổi; không sao chép toàn bộ thông tin liên hệ nhạy cảm vào log. Không tin tenant từ body.
- Tài khoản học viên hiện có không bị khóa hoặc bắt buộc hoàn thiện ngay khi migration; hồ sơ được tạo khi thao tác hợp lệ đầu tiên, không sinh dữ liệu cá nhân giả để lấp chỗ trống.

### 3. Giao diện Việt/Anh

- Quản lý/giáo vụ: sidebar Học viên → danh sách tìm kiếm/lọc/phân trang → tạo từ tài khoản học viên phù hợp → chi tiết/chỉnh sửa/liên hệ → lưu trữ có xác nhận.
- Học viên: Hồ sơ học viên của tôi → cập nhật thông tin và liên hệ → thông báo phần còn thiếu; tách khỏi trang bảo mật tài khoản.
- Đầy đủ loading, danh sách rỗng, lỗi validation, hết phiên, không có quyền và lưu thành công; kiểm tra theme sáng/tối từ phần A.

### 4. Kiểm thử và bàn giao

- Backend: CRUD, liên hệ chính, lưu trữ/khôi phục; mã duy nhất, tạo đồng thời trên PostgreSQL; tenant A không đọc/sửa/liệt kê dữ liệu B; học viên không đọc hồ sơ người khác/ghi chú nội bộ; giáo viên không xem danh sách tenant; Root phải có hỗ trợ.
- Migration nâng/hạ/nâng trên DB test, giữ tài khoản/membership/lời mời cũ và kiểm tra schema. Không downgrade database người dùng để thử.
- UI/E2E: giáo vụ tạo/sửa hồ sơ; học viên cập nhật phần được phép; tìm/lọc/phân trang; lưu trữ và thông báo lỗi. Chạy lại auth/lời mời để bảo đảm không hồi quy.
- Cập nhật tài liệu, myplan và Jira theo phạm vi thực sự hoàn thành; build API/web, áp dụng migration sau khi test, kiểm tra Docker. Không cần tắt database.
- Bàn giao checklist với từng bước, kết quả mong đợi và dấu hiệu lỗi; chờ người dùng nghiệm thu trước khi chuyển module.

## Chưa đưa vào phần này

Đăng ký/duyệt khóa học, xếp lớp, học phí, điểm danh, kết quả, chuyển trung tâm thực tế, import CSV, AI, thư viện học liệu và hồ sơ ngoại tuyến. Trình độ đầu vào/mục tiêu học STU-03 sẽ làm khi chốt cấu trúc ngôn ngữ/cấp độ, không thêm trường tự do thay thế mô hình đã thống nhất.

## Mốc thực hiện

1. Bàn giao sửa lỗi giao diện và nghiệm thu riêng.
2. Chốt trường hồ sơ, quyền và mô hình mã học viên.
3. Triển khai migration/API + test backend.
4. Triển khai UI + E2E, cập nhật Docker/tài liệu và bàn giao.

Không cam kết gộp cả bốn mốc vào một phiên. Nếu thời lượng phiên không đủ, dừng ở mốc đã kiểm chứng và ghi rõ phần còn lại.
