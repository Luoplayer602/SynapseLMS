# Kế hoạch tiếp theo — danh mục khóa học, ngôn ngữ và cấp độ

Trạng thái 2026-09-24: người dùng đã duyệt bằng yêu cầu “bắt đầu thực hiện”; lát cắt catalog dưới đây đã triển khai và kiểm thử, chờ nghiệm thu. Đặc tả hiện hành/kết quả/checklist tại [course-catalog.md](./course-catalog.md). Các đoạn “đề xuất” bên dưới giữ nguyên làm lịch sử kế hoạch; không mở rộng sang các lát cắt sau. Phần hồ sơ học viên và sửa theme đã được người dùng nghiệm thu.

## Mục tiêu và thứ tự phụ thuộc

Ưu tiên CRS-01 và CRS-02: trung tâm tạo/công bố khóa học; học viên xem khóa học thuộc trung tâm; chưa gửi yêu cầu đăng ký. Cần khóa học trước khi mở lớp, xác định học phí và xây luồng duyệt đăng ký.

Thứ tự sau đó: hồ sơ/năng lực giáo viên → chi nhánh/phòng và lớp/lịch → học phí/hóa đơn/thông báo → yêu cầu đăng ký, duyệt và xếp lớp. Không triển khai nút duyệt hoạt động khi chưa thể tạo hóa đơn đúng một lần trong transaction như quy tắc đã chốt.

## Phạm vi phiên triển khai kế tiếp

### 1. Chốt đặc tả dữ liệu và quyền

- Danh mục ngôn ngữ; bộ phân cấp và cấp độ có mã ổn định, thứ tự trong cùng bộ, nhãn hiển thị tùy chỉnh theo trung tâm. Không tự quy đổi hai hệ cấp độ hoặc hai ngôn ngữ thành tương đương.
- Khóa học thuộc tenant: mã, tên, mô tả, ngôn ngữ, bộ cấp độ, cấp độ đầu vào tối thiểu tùy chọn, cấp độ đầu ra, mục tiêu/điều kiện bằng văn bản và trạng thái nháp/công bố/lưu trữ. Dùng plain text, chưa rich text/upload.
- Đề xuất mã khóa học duy nhất trong tenant kể cả sau lưu trữ; không tái sử dụng mã để tránh nhầm lịch sử.
- Đề xuất cho phép nháp thiếu thông tin đào tạo; chỉ công bố khi đủ tên/mã/ngôn ngữ/cấp độ đầu ra/mục tiêu. Đầu vào có thể chọn không yêu cầu để hỗ trợ khóa nhập môn.
- Điều kiện đầu vào/đầu ra ở phiên này là mô tả và dữ liệu có cấu trúc cơ bản; chưa tự đánh giá đủ điều kiện đăng ký hoặc kết luận hoàn thành khóa.
- Không thêm giáo trình/thư viện học liệu, rubric đánh giá, học phí/khuyến mãi hoặc xếp lớp vào cùng phiên.

Quyền mặc định đề xuất, cần xác nhận khi duyệt kế hoạch:

| Vai trò | Khóa học | Danh mục cấp độ |
|---|---|---|
| Quản lý trung tâm | Tạo/sửa/công bố/lưu trữ trong tenant | Cấu hình trong tenant |
| Giáo vụ | Tạo/sửa nội dung nháp, xem danh mục; công bố/lưu trữ do quản lý | Xem |
| Học viên | Chỉ đọc khóa đã công bố của tenant hiện hành | Chỉ phần cần hiển thị khóa học |
| Giáo viên | Chưa mở danh sách toàn trung tâm; quyền lớp phụ trách ở module lớp | Chưa mở API riêng |
| Root | Hỗ trợ đúng tenant, có lý do/audit như hiện tại | Qua phiên hỗ trợ |

Chưa mở catalog công khai không đăng nhập trong phiên đầu. Đây là ranh giới triển khai đề xuất, không hủy yêu cầu công khai thông tin sản phẩm về sau.

### 2. Backend và migration

- Model danh mục ngôn ngữ/cấp độ và khóa học có tenant scope, unique constraint và khóa ngoại bảo vệ việc gán cấp độ khác tenant/bộ/ngôn ngữ.
- API quản trị khóa học: tạo, danh sách, chi tiết, sửa, công bố/lưu trữ; API đọc khóa đã công bố riêng với response tối thiểu cho học viên.
- Tìm kiếm mã/tên, lọc ngôn ngữ/cấp độ/trạng thái, phân trang server. Mặc định danh sách quản trị không trả dữ liệu tenant khác.
- Version chống ghi đè chỉnh sửa cũ; thao tác công bố/lưu trữ có lý do và audit. Không xóa cứng danh mục đang được tham chiếu; cấu hình đã dùng chỉ cho đổi nhãn an toàn, không tùy ý đổi thứ tự/ngữ nghĩa.
- Xác định từ bây giờ rằng lớp/đăng ký sau này phải giữ phiên bản thông tin đào tạo liên quan; chưa tạo bảng lớp hoặc snapshot nghiệp vụ giả trong phiên này.
- Migration chỉ thêm cấu trúc, không tạo khóa học mẫu vào dữ liệu thật. Nếu cung cấp preset cấp độ, quản lý chủ động chọn; kiểm chứng nội dung preset trước khi thêm, không tự suy đoán chuẩn.

### 3. Frontend Việt/Anh

- Quản lý/giáo vụ: sidebar Khóa học → tìm/lọc/phân trang → tạo nháp → chi tiết/chỉnh sửa. Hiển thị rõ thông tin thiếu và trạng thái.
- Quản lý: cấu hình nhãn cấp độ, công bố/lưu trữ có xác nhận. Khóa bị lưu trữ không còn trong catalog học viên.
- Học viên: danh mục khóa đã công bố → chi tiết mục tiêu/đầu vào/đầu ra; chưa có nút đăng ký hoạt động để không tạo kỳ vọng về luồng chưa có.
- Kiểm tra dark/light, mobile/desktop, loading/empty/error/permission, focus bàn phím. Không thay đổi các luồng auth/hồ sơ đã nghiệm thu.

### 4. Kiểm thử bắt buộc

- Tạo trùng mã đồng thời bị chặn tại DB; hai tenant được dùng cùng mã khóa.
- Gán cấp độ sai tenant/ngôn ngữ/bộ bị từ chối; đầu vào/đầu ra được kiểm tra trong cùng hệ phân cấp khi có cả hai.
- Học viên không đọc nháp/lưu trữ qua danh sách, URL trực tiếp hoặc API ID; không xem khóa tenant khác.
- Giáo vụ không tự nâng quyền công bố; Root không bỏ qua phiên hỗ trợ. Chốt lại ma trận nếu người dùng chọn quyền khác trước code.
- Công bố thiếu trường thất bại và không cập nhật một phần; version cũ báo 409; danh mục đang dùng không bị xóa phá khóa học.
- E2E quản lý tạo/công bố → học viên xem → lưu trữ → học viên không còn thấy; kiểm tra Việt/Anh, theme, hồi quy hồ sơ và lời mời.
- Test migration nâng/hạ/nâng trên DB tạm, schema check, lint/build; kiểm tra đồng thời trên PostgreSQL, không chỉ SQLite.

### 5. Bàn giao

- Cập nhật đặc tả dữ liệu/RBAC, myplan và Jira theo phạm vi thực tế; không đóng CRS-02 như thể đã có đánh giá tự động đầu vào/đầu ra.
- Rebuild API/web, áp dụng migration đã test, kiểm tra health và API/UI đang chạy. Không cần tắt database hay xóa volume.
- Checklist nghiệm thu: tạo nháp; kiểm tra trường thiếu; công bố; học viên xem; chặn quyền/truy cập nháp; sửa cùng lúc; lưu trữ; tìm/lọc/phân trang; nhãn cấp độ tùy chỉnh không làm đổi mã định danh.

## Các lát cắt sau, chưa triển khai trong phiên này

1. STU-03: trình độ đầu vào theo từng ngôn ngữ/bộ cấp độ, mục tiêu học và phân biệt tự khai với xác nhận của giáo vụ/giáo viên.
2. TCH-01/TCH-02: hồ sơ giáo viên, ngôn ngữ/cấp độ có thể dạy, chứng chỉ (chưa upload nếu chưa có thiết kế lưu trữ).
3. ORG/CLS/SCH: chi nhánh/phòng, mở lớp từ khóa, sĩ số, phân công nhiều giáo viên, lịch/buổi, kiểm tra trùng lịch và giáo viên dạy thay.
4. FEE/notifications: học phí theo khóa, hóa đơn, ưu đãi và thông báo đủ dùng cho luồng duyệt.
5. ENR/IAM-08 còn lại: yêu cầu đăng ký khóa, hồ sơ bắt buộc/chính sách công nợ, duyệt tạo hóa đơn đúng một lần, tự xếp lớp hoặc chuyển thủ công.

Học liệu và AI tiếp tục để sau khi có dữ liệu nghiệp vụ phù hợp. Không gộp tất cả lát cắt vào một phiên hoặc ấn định ngày hoàn thành khi chưa có số giờ thực tế.
