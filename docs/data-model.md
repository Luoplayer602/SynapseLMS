# Mô hình dữ liệu sơ bộ

**Phiên bản:** 0.1  
**Mục tiêu:** xác định ranh giới tenant và các quan hệ cần có trước khi viết migration.

## Phân cấp sở hữu

```text
System
└── Organization (trung tâm/tenant)
    ├── Branch
    │   └── Classroom
    ├── UserMembership
    ├── Student
    │   └── GuardianContact
    ├── Teacher
    ├── Course
    │   ├── CourseLevel
    │   ├── AssessmentTemplate
    │   └── FeePlan
    └── Class
        ├── ClassTeacher
        ├── ClassSession
        │   ├── SessionTeacher
        │   └── Attendance
        ├── CourseRegistrationRequest
        ├── ClassPlacement
        ├── Enrollment
        ├── Assessment
        │   └── Score
        ├── Invoice
        │   ├── Payment
        │   └── Refund
        ├── EnrollmentReservation
        └── PracticeAssignment
            └── PracticeAttempt
```

## Thực thể hệ thống

- `users`: danh tính đăng nhập toàn hệ thống.
- `organizations`: tenant của một trung tâm.
- `user_memberships`: lịch sử liên kết user với organization và một vai trò; mỗi user chỉ có một membership hoạt động tại một thời điểm.
- `branches`: chi nhánh thuộc organization.
- `audit_logs`: hành động nhạy cảm, actor, tenant, thời gian và thay đổi.
- `support_sessions`: phiên Root Admin truy cập tenant, lý do, thời hạn và người thực hiện.
- `notifications`: thông báo trong ứng dụng, người nhận và trạng thái đã đọc.

## Quy tắc multi-tenant

Cập nhật triển khai hồ sơ: `student_identities` giữ mã duy nhất toàn hệ thống gắn user; `student_profiles` chứa thông tin thuộc tenant và liên kết identity; `guardian_contacts` thuộc hồ sơ cha. Không đổi chủ sở hữu hồ sơ cũ khi xây luồng chuyển. Chi tiết và API tại [hồ sơ học viên](./student-profiles.md).

- Mọi bảng nghiệp vụ phải có `organization_id`, trực tiếp hoặc qua quan hệ cha không thể nhập nhằng.
- Khóa duy nhất nghiệp vụ thường gồm `organization_id`, ví dụ mã học viên hoặc mã lớp.
- Riêng mã học viên có unique constraint toàn hệ thống, không phụ thuộc `organization_id`.
- Backend lấy tenant từ membership đã xác thực, không tin `organization_id` tùy ý từ request body.
- Repository/service layer áp dụng tenant scope mặc định.
- Test bắt buộc phải chứng minh người dùng tenant A không đọc, sửa hoặc suy ra dữ liệu tenant B.
- Root Admin dùng phiên hỗ trợ riêng có tenant, lý do và thời hạn; mọi truy cập trong phiên phải được audit.
- Tài khoản nghiệp vụ không được đồng thời thuộc nhiều organization hoặc giữ nhiều vai trò.
- Chuyển trung tâm đóng membership hiện tại, tạo membership mới và lưu `student_transfers`; lịch sử nguồn không bị sửa hoặc xóa.
- `student_transfers` lưu học viên, tenant nguồn/đích, trạng thái duyệt hai phía, lý do từ chối, snapshot phạm vi dữ liệu và thời điểm hoàn tất.
- `transferred_record_grants` cấp quyền xem chỉ đọc lịch sử nguồn cho tenant mới mà không đổi quyền sở hữu bản ghi.
- Công nợ và giao dịch tài chính giữ `organization_id` nguồn; tenant mới chỉ có quyền đọc qua transfer grant.

## Quy tắc tài chính

- Tiền dùng kiểu `DECIMAL` và có mã tiền tệ.
- Payment không bị xóa cứng; điều chỉnh bằng giao dịch đảo hoặc hoàn tiền.
- Giáo vụ có thể tạo giao dịch hoàn tiền nhưng phải nhập lý do; actor và thay đổi được ghi audit log.
- `enrollment_reservations` lưu buổi bắt đầu bảo lưu, lý do và các buổi bị ảnh hưởng.
- `refund_proposals` lưu công thức, học phí sau giảm giá, phí khấu trừ, dữ liệu nguồn và số tiền đề xuất.
- `refund_offsets` lưu công nợ trước/sau và số tiền đã bù trừ; `refunds` chỉ lưu phần thực hoàn bằng tiền mặt/chuyển khoản.
- Bảo lưu không tự động thay đổi lịch trả góp; mọi thay đổi công nợ phải được biểu diễn bằng điều chỉnh tài chính riêng.
- Yêu cầu thanh toán có idempotency key.
- Công nợ bằng tổng nghĩa vụ sau giảm giá trừ thanh toán hợp lệ và điều chỉnh.

## Quy tắc học tập

- `class_sessions` biểu diễn từng buổi học thực tế.
- Giáo viên mặc định nằm ở `class_teachers`; giáo viên dạy thay nằm ở `session_teachers`.
- Một học viên chỉ có một Attendance cho mỗi session.
- `course_registration_requests` lưu yêu cầu đăng ký khóa học và quyết định duyệt/từ chối; từ chối bắt buộc có lý do.
- Duyệt yêu cầu tạo hóa đơn ngay và khởi tạo `class_placements` để xếp lớp tự động hoặc thủ công.
- `class_placements` lưu chế độ AUTO/MANUAL, trạng thái, lý do không xếp được và người quyết định.
- Assessment dựa trên template của Course nhưng có thể được snapshot khi mở lớp để tránh thay đổi lịch sử.

## Quy tắc AI

- `ai_interactions` lưu loại tác vụ, provider/model, phiên bản prompt, độ trễ, token/chi phí và trạng thái.
- Dữ liệu gửi AI phải qua bước dựng payload có whitelist.
- Kết quả AI không trực tiếp tạo Enrollment, Payment, Attendance hoặc Score.
