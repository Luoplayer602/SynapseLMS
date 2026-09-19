# Luồng đăng ký khóa học và xếp lớp

**Phiên bản:** 0.1  
**Trạng thái:** Đã chốt luồng chính

## Nguyên tắc

- Học viên đăng ký **khóa học**, không đăng ký trực tiếp một lớp cụ thể.
- Giáo vụ có thể tạo yêu cầu thay học viên.
- Mọi yêu cầu phải được giáo vụ duyệt hoặc từ chối.
- Từ chối bắt buộc có lý do và lý do được hiển thị cho học viên.
- Khi duyệt, hệ thống tạo hóa đơn ngay theo học phí và ưu đãi của khóa học.
- Sau khi duyệt, hệ thống thử xếp lớp tự động. Nếu không có lớp phù hợp, yêu cầu chuyển sang hàng chờ xếp lớp thủ công.
- Trung tâm có cấu hình cho phép hoặc chặn gửi yêu cầu mới khi học viên còn công nợ.

## Trạng thái yêu cầu đăng ký

```text
DRAFT
  → SUBMITTED
      → REJECTED
      → APPROVED
          → AUTO_PLACEMENT_PENDING
              → PLACED
              → MANUAL_PLACEMENT_REQUIRED
                  → PLACED
                  → CANCELLED
```

## Luồng chính

1. Học viên hoặc giáo vụ chọn khóa học.
2. Hệ thống kiểm tra hồ sơ bắt buộc và chính sách công nợ của trung tâm.
3. Nếu chính sách chặn công nợ đang bật và học viên còn nợ, hệ thống không cho gửi yêu cầu và hiển thị lý do.
4. Yêu cầu hợp lệ chuyển sang `SUBMITTED`; giáo vụ nhận thông báo trong ứng dụng.
5. Giáo vụ duyệt hoặc từ chối:
   - Từ chối: bắt buộc nhập lý do, chuyển `REJECTED` và thông báo học viên.
   - Duyệt: chuyển `APPROVED`, tạo hóa đơn ngay và bắt đầu xếp lớp.
6. Bộ xếp lớp lọc các lớp thuộc khóa học theo trạng thái, sĩ số, trình độ, chi nhánh, hình thức và lịch rảnh.
7. Nếu chỉ có một kết quả đủ điều kiện hoặc đạt ngưỡng cấu hình, hệ thống tạo Enrollment và chuyển `PLACED`.
8. Nếu không thể xếp chắc chắn, chuyển `MANUAL_PLACEMENT_REQUIRED`; giáo vụ chọn lớp hoặc chờ lớp mới mở.

## Quy tắc giao dịch

- Duyệt yêu cầu và tạo hóa đơn phải nằm trong một transaction nghiệp vụ.
- Xếp lớp phải kiểm tra lại sĩ số khi tạo Enrollment để tránh vượt chỗ do xử lý đồng thời.
- Một yêu cầu không được tạo nhiều hóa đơn hoặc nhiều Enrollment do retry; các thao tác phải idempotent.
- Thay đổi lớp sau khi xếp phải lưu lịch sử.
- Hóa đơn vẫn tồn tại nếu chưa xếp được lớp vì nghĩa vụ học phí phát sinh ngay khi yêu cầu được duyệt.

## Thông báo

- Giáo vụ: có yêu cầu mới và có yêu cầu cần xếp lớp thủ công.
- Học viên: được duyệt/từ chối, hóa đơn đã tạo và đã được xếp lớp.

## Kiểm thử tối thiểu

- Không gửi được yêu cầu khi thiếu hồ sơ bắt buộc.
- Chính sách công nợ bật thì chặn; tắt thì vẫn cho gửi.
- Từ chối không có lý do bị từ chối bởi API.
- Duyệt tạo đúng một hóa đơn dù request được gửi lại.
- Xếp tự động không vượt sĩ số và không tạo trùng Enrollment.
- Không tìm được lớp thì chuyển sang hàng chờ thủ công.

