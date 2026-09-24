# STU-03 — Trình độ đầu vào và mục tiêu học

Ngày 2026-09-25. Trạng thái: kế hoạch đề xuất, chưa triển khai. Theo yêu cầu người dùng, BUG-004 trên Chrome hoãn xử lý, không còn là điều kiện bắt đầu bước nghiệp vụ này. Không tự đánh dấu các bản trước đã nghiệm thu.

## Mục tiêu và phạm vi

Trong hồ sơ học viên, lưu trình độ theo ngôn ngữ/bộ cấp độ của trung tâm, phân biệt tự khai với trung tâm xác nhận, kèm mục tiêu học và lịch sử cập nhật. Đây là nền dữ liệu cho tư vấn/đăng ký sau này, chưa tự xét điều kiện khóa học, duyệt, xếp lớp hoặc tạo hóa đơn.

Không triển khai bài thi đầu vào, chấm điểm, upload chứng chỉ, quy đổi chuẩn, AI, thư viện học liệu hoặc chuyển trung tâm trong cùng phiên. Quyền nhập điểm chỉ giáo viên vẫn giữ nguyên; xác nhận hồ sơ trình độ không phải nhập bảng điểm.

## Mặc định đề xuất cần duyệt trước code

- Mỗi hồ sơ học viên có tối đa một mục hiện hành cho mỗi cặp ngôn ngữ/bộ cấp độ. Có thể có nhiều ngôn ngữ hoặc nhiều bộ; không tự coi hai bộ tương đương.
- Hai phần độc lập: học viên tự khai và trung tâm xác nhận. Tự khai mới không được ghi đè hoặc tự thay đổi phần đã xác nhận. UI luôn ghi rõ nguồn và thời điểm, không chỉ hiển thị một nhãn cấp độ thiếu ngữ cảnh.
- Cho phép chưa biết trình độ (null), khác với cấp thấp nhất hoặc “không yêu cầu đầu vào” của khóa. Không tự suy ra trình độ từ khóa đã xem/đăng ký.
- Mục tiêu gồm nội dung văn bản, cấp độ đích tùy chọn trong cùng bộ và ngày mong muốn tùy chọn. Không bắt buộc đích cao hơn trình độ hiện tại vì học viên có thể muốn ôn lại.
- Quản lý/giáo vụ được ghi nhận hoặc xác nhận trình độ từ kết quả kiểm tra/chứng chỉ đã kiểm tra thủ công; bắt buộc nguồn/căn cứ và lý do. Root thực hiện qua hỗ trợ có audit. Đây là đề xuất quyền cho STU-03, không thay đổi quyền điểm số.
- Giáo viên chưa mở quyền khi chưa có phân công lớp/đánh giá phù hợp. Học viên chỉ tự khai, sửa mục tiêu và đọc thông tin công khai của chính mình; không tự xác nhận hay sửa căn cứ nội bộ.
- Sửa/thu hồi xác nhận phải có lý do và lưu lịch sử; không xóa cứng. Hồ sơ lưu trữ chỉ đọc cho phần trình độ/mục tiêu đến khi khôi phục.

## Các hạng mục triển khai

### 1. Đặc tả và dữ liệu

- Bảng mục trình độ liên kết student_profile, organization, language, framework; phần tự khai, phần xác nhận và mục tiêu không dùng chung trường có thể ghi đè lẫn nhau.
- Lịch sử nghiệp vụ giữ phiên bản/nội dung cần đối chiếu, người thực hiện, thời điểm và nguồn; audit kỹ thuật chỉ ghi hành động/tên trường, không chép tự do thông tin cá nhân/căn cứ.
- Tách lịch sử công khai cho học viên khỏi căn cứ/ghi chú nội bộ. Không trả trường nội bộ qua API học viên rồi chỉ ẩn bằng CSS.
- FK tổng hợp bảo vệ cùng tenant/ngôn ngữ/bộ, unique theo hồ sơ/bộ; version chống cập nhật cũ. Thống nhất thứ tự khóa với BUG-003, không phát sinh vòng chờ audit mới.
- Migration chỉ thêm cấu trúc, không gán cấp độ mặc định cho học viên cũ. Không tạo dữ liệu bằng GET.

### 2. API và quyền

- Nhân sự: danh sách/chi tiết trình độ theo hồ sơ, ghi nhận/xác nhận/điều chỉnh/thu hồi có lý do, xem lịch sử và mục tiêu.
- Học viên: endpoints riêng cho bản thân, khai trình độ/sửa mục tiêu/xem lịch sử công khai; body không chọn user/tenant hoặc trạng thái xác nhận.
- Tùy chọn ngôn ngữ/bộ/cấp độ dùng API tối thiểu được cấp quyền cho STU-03, không mở API quản trị catalog cho học viên. Không chỉ lấy cấp độ từ khóa đang công bố vì hồ sơ có thể dùng cấp độ chưa có khóa.
- Từ chối hồ sơ khác tenant, bộ/cấp độ sai quan hệ, version cũ, giả mạo người xác nhận/ngày xác nhận; phân trang lịch sử.

### 3. Bảo vệ danh mục đang được sử dụng

- Mở rộng `require_unused`: ngôn ngữ/bộ/cấp độ được trình độ hiện hành, cấp độ đích hoặc lịch sử STU-03 tham chiếu phải chặn xóa/sửa mã; nhãn vẫn được sửa theo quyền cũ.
- Snapshot mã/nhãn trong lịch sử để đổi nhãn danh mục không làm sai cách hiểu sự kiện cũ; không bỏ FK để né bảo vệ sử dụng.
- Viết test đối đầu giữa tạo trình độ/mục tiêu và xóa/sửa mã cấp độ trên PostgreSQL. Không triển khai STU-03 rồi mới bổ sung bảo vệ này sau.

### 4. Giao diện

- Bổ sung mục “Trình độ và mục tiêu” trong chi tiết học viên và “Hồ sơ học viên của tôi”, không cần sidebar mới.
- Hiển thị rõ tự khai, xác nhận của trung tâm, mục tiêu và lịch sử; form xác nhận/thu hồi có lý do, trạng thái rỗng/loading/lỗi/xung đột.
- Việt/Anh, responsive; kiểm thử trên Chrome. BUG-004 vẫn được ghi là lỗi tồn tại, không tuyên bố select dark mode đã đạt hoặc âm thầm mở rộng phiên này thành sửa theme.

### 5. Kiểm thử và bàn giao

- Unit/integration SQLite và PostgreSQL: quyền, tenant/FK, version, lịch sử, bảo vệ danh mục, thu hồi, archived và đồng thời với thay đổi quyền/support.
- E2E: học viên tự khai → giáo vụ xác nhận → học viên tự khai lại không đổi phần xác nhận → điều chỉnh/thu hồi có lịch sử. Kiểm tra endpoint học viên không có trường nội bộ.
- Chạy hồi quy hồ sơ, catalog, sửa mã/xóa và BUG-003, lint/build, migration nâng/hạ/nâng trên DB tạm.
- Sau khi test đạt mới cập nhật Docker/migration; không cần tắt database hoặc xóa volume. Cập nhật tài liệu, myplan/Jira theo phạm vi thực tế và bàn giao checklist. Không commit khi chưa được yêu cầu.

## Tiêu chí nghiệm thu chính

1. Một học viên có nhiều ngôn ngữ/bộ, không lẫn cấp độ và không tự quy đổi.
2. Học viên tự khai/sửa mục tiêu được nhưng không tự xác nhận; không nhìn thấy ghi chú/căn cứ nội bộ.
3. Giáo vụ/quản lý xác nhận có căn cứ/lý do; đổi tự khai sau đó giữ nguyên xác nhận cũ.
4. Điều chỉnh hoặc thu hồi để lại lịch sử, người/thời điểm đúng; không mất dữ liệu cũ.
5. Cấp độ dùng bởi trình độ, mục tiêu hoặc lịch sử không xóa/đổi mã được; đổi nhãn không làm sai lịch sử.
6. Hai tab sửa cùng phiên bản: tab cũ bị chặn; sai tenant/quyền và hồ sơ lưu trữ bị từ chối.
7. Không có yêu cầu đăng ký, hóa đơn hoặc xếp lớp phát sinh từ việc cập nhật trình độ.

Thứ tự sau STU-03: hồ sơ/năng lực giáo viên → chi nhánh/phòng/lớp/lịch → tài chính/thông báo → đăng ký/duyệt/xếp lớp. Mỗi lát cắt có kế hoạch và nghiệm thu riêng.
