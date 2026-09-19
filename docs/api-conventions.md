# Quy ước API SynapseLMS

**Phiên bản:** 0.1

## URL và versioning

- Base path: `/api/v1`.
- Resource dùng danh từ số nhiều và kebab-case khi có nhiều từ.
- Không đưa tenant ID vào URL cho request thông thường; tenant lấy từ phiên đăng nhập.
- Root Admin mở support session riêng trước khi truy cập tenant.

Ví dụ:

```text
POST /api/v1/auth/login
GET  /api/v1/students
POST /api/v1/course-registration-requests
POST /api/v1/course-registration-requests/{id}/approve
POST /api/v1/enrollments/{id}/reservations
POST /api/v1/student-transfers/{id}/source-approval
```

## Response và lỗi

Response thành công trả resource trực tiếp hoặc envelope phân trang. Lỗi dùng cấu trúc ổn định:

```json
{
  "error": {
    "code": "ENROLLMENT_DEBT_BLOCKED",
    "message": "Không thể gửi yêu cầu khi còn công nợ.",
    "details": {},
    "request_id": "..."
  }
}
```

- `code` ổn định để frontend dịch thông báo.
- `message` an toàn, không lộ stack trace hoặc dữ liệu tenant khác.
- Validation trả lỗi theo từng field.

## Phân trang và lọc

- Danh sách dùng cursor pagination khi có thể; màn hình quản trị nhỏ có thể dùng page/limit ở MVP.
- Filter và sort phải được whitelist.
- Mọi danh sách có giới hạn tối đa để tránh truy vấn không kiểm soát.

## Idempotency và concurrency

- Các API tạo thanh toán, duyệt đăng ký, tạo Enrollment, hoàn phí và chuyển trung tâm nhận `Idempotency-Key`.
- Backend lưu kết quả theo actor + tenant + operation + key.
- Dữ liệu có nguy cơ ghi đè dùng version/updated_at để optimistic concurrency hoặc row lock cho sĩ số/tài chính.

## Xác thực và bảo mật

- Access token ngắn hạn, refresh token xoay vòng và có thể thu hồi.
- Cookie refresh dùng `HttpOnly`, `Secure`, `SameSite`; access token không lưu lâu trong localStorage.
- Rate limit cho login, reset password và AI endpoints.
- OpenAPI không hiển thị secret; endpoint quản trị khóa AI không bao giờ trả plaintext sau khi lưu.

## Đăng ký học viên

- Học viên có thể chọn trung tâm trong danh sách công khai hoặc nhập mã mời/mã trung tâm.
- Mã mời có thời hạn, trạng thái và giới hạn lượt dùng.
- Trung tâm có thể tắt xuất hiện công khai và chỉ nhận đăng ký bằng mã.

