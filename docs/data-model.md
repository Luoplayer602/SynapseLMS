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

Nền lớp học, migration `20260926_0010`: `branches`, `rooms`, `learning_classes` và unique index course `(id, organization_id)`. FK tổng hợp giữ lớp/phòng đúng tenant/chi nhánh và snapshot giữ FK gốc của ngôn ngữ/bộ/cấp độ; không cho xóa/đổi mã danh mục đã được lớp (kể cả lưu trữ) tham chiếu. Lớp chỉ draft/archived, snapshot khóa không đổi; ngày dự kiến chưa tạo session/reservation. Không seed/backfill. Chi tiết [class-foundation.md](./class-foundation.md).

Lịch cơ bản, migration `20260926_0011`: `class_teachers` (phân công và lý do override nội bộ), `schedule_plans` (một mẫu JSON/lớp, digest và khóa xác nhận), `class_sessions` (UTC, múi giờ, phòng/chi nhánh, sĩ số/hình thức), `session_teachers` (giáo viên từng buổi); unique index lớp `(id, organization_id)` và FK tổng hợp tenant. Không seed/backfill. Nháp không tạo session; xác nhận tạo toàn bộ session/link cùng transaction. PostgreSQL dùng khóa tenant và tài khoản giáo viên để tuần tự hóa kiểm tra-xác nhận, không dựa vào kiểm tra UI; chưa có exclusion constraint bảo vệ ghi SQL trực tiếp. SQLite dành cho đơn người dùng/test, không cam kết tương đương khóa hàng PostgreSQL. Chi tiết [scheduling.md](./scheduling.md).

TCH-01/TCH-02, migration `20260926_0009`: `teacher_profiles` unique user/tenant; `teaching_capabilities` unique profile/ngôn ngữ và `teaching_capability_levels` giữ cấp cụ thể, có thể nhiều bộ cùng ngôn ngữ. `teacher_credentials` lưu chứng chỉ văn bản/ngày. `teacher_history` và `teacher_history_levels` giữ snapshot public/internal cùng FK gốc. Không backfill/cascade/xóa cứng; catalog guard bao gồm năng lực và lịch sử. Chi tiết [teacher-profiles.md](./teacher-profiles.md).

Cập nhật triển khai hồ sơ: `student_identities` giữ mã duy nhất toàn hệ thống gắn user; `student_profiles` chứa thông tin thuộc tenant và liên kết identity; `guardian_contacts` thuộc hồ sơ cha. Không đổi chủ sở hữu hồ sơ cũ khi xây luồng chuyển. Chi tiết và API tại [hồ sơ học viên](./student-profiles.md).

STU-03, migration `20260925_0008`: `student_proficiencies` unique theo profile/bộ cấp độ, tách tự khai/xác nhận/mục tiêu và version. `proficiency_history` lưu snapshot public/internal sau từng mutation, FK giữ cả cấp độ lịch sử. FK tổng hợp ràng buộc profile/tenant/ngôn ngữ/bộ; unique index profile `(id, organization_id)` phục vụ tham chiếu. Không xóa/đổi mã danh mục được mục hiện hành hoặc lịch sử dùng, không backfill. Xem [trình độ và mục tiêu](./student-proficiencies.md).

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

- Đã triển khai migration `20260924_0007`: `course_languages` → `level_frameworks` → `course_levels`, và `courses`. Các bảng có organization_id/version; khóa ngoại tổng hợp đảm bảo cùng tenant/ngôn ngữ/bộ. Khóa có mã duy nhất theo tenant kể cả lưu trữ, trạng thái draft/published/archived, mục tiêu và điều kiện plain text; đầu vào/đầu ra tham chiếu cấp độ trong cùng bộ. Rank/quan hệ cha danh mục bất biến qua API; nhãn được sửa. Bổ sung sau BUG-003: quản lý được sửa mã/xóa mục chưa sử dụng và không có con; khóa phải là nháp chưa từng công bố. Audit giữ lịch sử công bố và xóa; không có cascade. Khi thêm module mới phải mở rộng kiểm tra tham chiếu khi xóa/sửa mã. Các bảng lớp/đăng ký phía dưới vẫn là thiết kế tương lai. Chi tiết: [course-catalog.md](./course-catalog.md).

- `class_sessions` biểu diễn từng buổi học thực tế.
- Giáo viên lớp nằm ở `class_teachers`; tập giáo viên từng buổi nằm ở `session_teachers`. Bản hiện hành yêu cầu giáo viên buổi thuộc phân công lớp; luồng dạy thay chưa triển khai.
- Một học viên chỉ có một Attendance cho mỗi session.
- `course_registration_requests` lưu yêu cầu đăng ký khóa học và quyết định duyệt/từ chối; từ chối bắt buộc có lý do.
- Duyệt yêu cầu tạo hóa đơn ngay và khởi tạo `class_placements` để xếp lớp tự động hoặc thủ công.
- `class_placements` lưu chế độ AUTO/MANUAL, trạng thái, lý do không xếp được và người quyết định.
- Assessment dựa trên template của Course nhưng có thể được snapshot khi mở lớp để tránh thay đổi lịch sử.

## Quy tắc AI

- `ai_interactions` lưu loại tác vụ, provider/model, phiên bản prompt, độ trễ, token/chi phí và trạng thái.
- Dữ liệu gửi AI phải qua bước dựng payload có whitelist.
- Kết quả AI không trực tiếp tạo Enrollment, Payment, Attendance hoặc Score.
