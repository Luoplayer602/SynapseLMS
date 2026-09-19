# Luồng chuyển học viên giữa các trung tâm

**Phiên bản:** 0.1  
**Trạng thái:** Đã chốt luồng chính

## Nguyên tắc

- Học viên là người khởi tạo yêu cầu chuyển.
- Trung tâm cũ phải xác nhận trước, sau đó trung tâm mới xác nhận tiếp nhận.
- Chỉ sau khi cả hai trung tâm đồng ý, membership cũ mới kết thúc và membership mới có hiệu lực.
- Mã học viên giữ nguyên và duy nhất toàn hệ thống.
- Trung tâm mới được xem toàn bộ lịch sử học tập và giao dịch đã chuyển dưới dạng chỉ đọc.
- Dữ liệu tài chính vẫn thuộc sở hữu trung tâm đã phát sinh giao dịch; trung tâm mới không được sửa, hoàn, hủy hoặc thu hộ.
- Công nợ ở trung tâm cũ không chặn chuyển. Hệ thống phải cảnh báo học viên và hai trung tâm, đồng thời giữ công nợ ở sổ cái của trung tâm cũ.

## Trạng thái yêu cầu

```text
DRAFT
  → SUBMITTED
      → SOURCE_APPROVED
          → DESTINATION_APPROVED
              → TRANSFERRED
          → DESTINATION_REJECTED
      → SOURCE_REJECTED
  → CANCELLED
```

## Luồng xử lý

1. Học viên chọn trung tâm đích và gửi yêu cầu.
2. Hệ thống chụp snapshot phạm vi dữ liệu dự kiến chuyển và hiển thị cảnh báo nếu còn công nợ.
3. Trung tâm cũ duyệt hoặc từ chối; từ chối bắt buộc có lý do.
4. Sau khi trung tâm cũ duyệt, trung tâm mới nhận yêu cầu và duyệt hoặc từ chối; từ chối bắt buộc có lý do.
5. Khi cả hai đã duyệt, hệ thống thực hiện trong một transaction:
   - Kết thúc membership cũ.
   - Tạo membership mới với vai trò học viên.
   - Chuyển quyền quản lý hồ sơ hiện tại sang trung tâm mới.
   - Tạo quyền xem chỉ đọc đối với lịch sử học tập và tài chính nguồn.
   - Lưu bản ghi transfer và audit log.
6. Hệ thống thông báo kết quả cho học viên và hai trung tâm.

## Dữ liệu được chuyển hoặc chia sẻ

- Hồ sơ cá nhân và thông tin người giám hộ.
- Trình độ, mục tiêu và kết quả kiểm tra đầu vào.
- Khóa/lớp đã học, điểm danh, điểm số, nhận xét và chứng nhận.
- Bài luyện tập và tóm tắt tiến độ đã công bố.
- Hóa đơn, thanh toán, giảm giá, hoàn phí và công nợ dưới dạng chỉ đọc.

## Quy tắc quyền riêng tư và tài chính

- Yêu cầu do học viên khởi tạo được xem là sự đồng ý chuyển dữ liệu giữa hai trung tâm.
- Trung tâm cũ tiếp tục xem và quản lý dữ liệu do mình tạo theo chính sách lưu trữ.
- Trung tâm mới chỉ được xem lịch sử tài chính nguồn; không được thay đổi sổ cái của trung tâm cũ.
- Các nghiệp vụ mới sau chuyển thuộc trung tâm mới.
- Root Admin có thể xử lý sự cố nhưng mọi can thiệp phải có lý do và audit log.

## Kiểm thử tối thiểu

- Không chuyển trước khi cả hai trung tâm duyệt.
- Từ chối không có lý do bị API từ chối.
- Không tồn tại hai membership hoạt động sau khi chuyển.
- Mã học viên không thay đổi.
- Trung tâm mới xem được lịch sử nguồn nhưng không sửa được.
- Công nợ cũ không chặn chuyển và không đổi chủ sở hữu.
- Retry không tạo transfer hoặc membership trùng.

