# Luồng bảo lưu và hoàn phí

**Phiên bản:** 0.1  
**Trạng thái:** Đã chốt luồng chính

## Nguyên tắc

- Bảo lưu có hiệu lực từ một buổi học cụ thể, không bắt buộc bảo lưu toàn bộ khóa từ đầu.
- Giáo vụ chọn buổi bắt đầu bảo lưu và nhập lý do.
- Bảo lưu không tự động dừng hoặc xóa các kỳ trả góp; nghĩa vụ thanh toán tiếp tục theo lịch đã lập.
- Sau khi ghi nhận bảo lưu, hệ thống tính và đề xuất số tiền có thể hoàn dựa trên phần chưa học.
- Buổi được chọn làm mốc bắt đầu bảo lưu được tính là buổi chưa học và đủ điều kiện xem xét hoàn.
- Giá trị hoàn được tính trên học phí ròng sau giảm giá; trung tâm có thể cấu hình phí khấu trừ.
- Giáo vụ có quyền xác nhận hoặc điều chỉnh khoản hoàn, nhưng phải nhập lý do khi khác đề xuất.
- Khoản hoàn được bù trừ công nợ trước; chỉ phần còn lại mới được hoàn bằng tiền mặt hoặc chuyển khoản.
- Không giữ tiền thành ví hoặc số dư dùng cho khóa sau.

## Trạng thái bảo lưu

```text
REQUESTED
  → CONFIRMED
      → REFUND_PROPOSED
          → REFUND_APPROVED
              → REFUNDED
          → NO_REFUND
  → REJECTED
  → CANCELLED
```

## Cách tính đề xuất

Phiên bản MVP sử dụng công thức cấu hình được theo trung tâm:

```text
giá trị mỗi buổi = học phí ròng / tổng số buổi tính phí
giá trị chưa học = giá trị mỗi buổi × số buổi đủ điều kiện hoàn
đề xuất hoàn = min(số tiền đã thanh toán, giá trị chưa học) - phí khấu trừ
bù trừ công nợ = min(đề xuất hoàn, công nợ hiện tại)
tiền hoàn thực tế = max(0, đề xuất hoàn - công nợ hiện tại)
công nợ sau bù trừ = max(0, công nợ hiện tại - đề xuất hoàn)
```

Trong đó:

- Học phí ròng là học phí sau giảm giá.
- Buổi bắt đầu bảo lưu và các buổi sau được xem xét là chưa học.
- Trung tâm có thể cấu hình phí khấu trừ hoặc tỷ lệ không hoàn.
- Đề xuất không bao giờ âm và không vượt tổng tiền thực tế đã thu.
- Khoản trả góp chưa thanh toán vẫn là công nợ cho đến khi có điều chỉnh tài chính rõ ràng.

## Luồng xử lý

1. Giáo vụ chọn Enrollment và buổi bắt đầu bảo lưu.
2. Hệ thống kiểm tra buổi thuộc lớp, chưa bị bảo lưu trước đó và hiển thị các buổi bị ảnh hưởng.
3. Giáo vụ xác nhận, nhập lý do; Enrollment chuyển trạng thái bảo lưu từ buổi đã chọn.
4. Hệ thống không thay đổi lịch trả góp hiện tại.
5. Hệ thống tạo bản đề xuất hoàn phí kèm công thức và dữ liệu nguồn.
6. Giáo vụ chấp nhận đề xuất hoặc điều chỉnh có lý do.
7. Hệ thống dùng khoản hoàn để bù trừ công nợ và hiển thị phép tính.
8. Nếu còn tiền phải trả cho học viên, giáo vụ ghi nhận hoàn bằng tiền mặt hoặc chuyển khoản cùng mã tham chiếu nếu có.
9. Hệ thống tạo điều chỉnh công nợ và giao dịch hoàn tương ứng, lưu audit log; không tạo số dư nội bộ.

## Quy tắc dữ liệu và audit

- Không xóa hóa đơn, thanh toán hoặc giao dịch hoàn.
- Đề xuất và số tiền hoàn thực tế phải được lưu riêng.
- Số bù trừ công nợ và công nợ trước/sau bù trừ phải được lưu để đối soát.
- Mọi điều chỉnh khỏi số tiền đề xuất phải có lý do.
- Refund có idempotency key để tránh hoàn hai lần.
- Audit log lưu Enrollment, buổi bắt đầu, công thức, dữ liệu nguồn, người thao tác và thời điểm.

## Kiểm thử tối thiểu

- Không thể chọn buổi không thuộc Enrollment.
- Bảo lưu không tự động hủy kỳ trả góp.
- Đề xuất không vượt số tiền đã thanh toán.
- Buổi bắt đầu bảo lưu được tính trong phần chưa học.
- Học phí ròng sau giảm giá và phí khấu trừ cấu hình được được áp dụng đúng.
- Khoản hoàn được bù trừ công nợ trước; chỉ phần dư mới tạo giao dịch chi tiền.
- Giảm giá được phản ánh trong học phí ròng.
- Điều chỉnh đề xuất không có lý do bị từ chối.
- Retry không tạo giao dịch hoàn trùng.
- Chỉ chấp nhận phương thức tiền mặt hoặc chuyển khoản cho phần thực chi.
