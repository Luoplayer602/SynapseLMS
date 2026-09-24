# Tài liệu SynapseLMS

Thư mục này là nguồn tài liệu chính thức của dự án. Jira dùng để theo dõi tiến độ; các quyết định dài hạn và đặc tả phải được cập nhật tại đây.

## Tài liệu hiện có

- [PRD](./prd.md): mục tiêu, phạm vi và tiêu chí thành công của sản phẩm.
- [Ma trận phân quyền](./rbac.md): quyền của từng vai trò và giới hạn dữ liệu.
- [Mô hình dữ liệu](./data-model.md): thực thể chính và quy tắc multi-tenant.
- [Nền tảng xác thực AUTH-01](./auth-foundation.md): model, phiên đăng nhập, migration và các bước triển khai IAM.
- [Kế hoạch bước xác thực tiếp theo](./auth-next-step.md): checkpoint, hợp đồng API và tiêu chí nghiệm thu.
- [Vận hành xác thực và phân quyền](./auth-operations.md): bootstrap Root Admin, cấu hình, API, Docker và kiểm thử.
- [Vòng đời tài khoản](./account-lifecycle.md): xác minh email, khôi phục mật khẩu, quản lý phiên và Mailpit.
- [Mời thành viên qua email](./membership-invitations.md): quyền mời, tiếp nhận, gửi lại/thu hồi, API và checklist nghiệm thu.
- [Hồ sơ học viên](./student-profiles.md): danh tính/mã toàn hệ thống, hồ sơ tenant, liên hệ phụ huynh, quyền và nghiệm thu.
- [Kế hoạch trình độ và mục tiêu học STU-03](./student-proficiency-next-step.md): tự khai/xác nhận, lịch sử, quyền và bảo vệ danh mục tham chiếu; chưa triển khai.
- [Danh mục khóa học](./course-catalog.md): ngôn ngữ/bộ/cấp độ, nháp/công bố/lưu trữ, quyền và checklist nghiệm thu.
- [Kế hoạch catalog và các bước sau](./course-catalog-next-step.md): phạm vi CRS-01/CRS-02 và thứ tự phụ thuộc các lát cắt tiếp theo.
- [Phản hồi nghiệm thu](./test-feedback.md): lỗi nhãn/theme và trạng thái xử lý.
- [Luồng giáo trình và tài liệu tham khảo](./workflows/learning-materials.md): thư viện, phiên bản, quyền truy cập và backlog MAT đề xuất.
- [Luồng đăng ký và xếp lớp](./workflows/enrollment.md): duyệt khóa học, tạo hóa đơn và xếp lớp.
- [Luồng bảo lưu và hoàn phí](./workflows/reservation-refund.md): bảo lưu từ buổi học, đề xuất và thực hiện hoàn phí.
- [Luồng chuyển trung tâm](./workflows/student-transfer.md): phê duyệt hai phía và chuyển lịch sử học viên.
- [Định hướng UI/UX](./ui-ux.md): nguyên tắc giao diện desktop/mobile theo phong cách macOS/iOS.
- [Wireframe v0.1](./wireframes.md): bố cục màn hình chính theo từng vai trò.
- [Kiến trúc hệ thống](./architecture.md): module, ranh giới tenant và luồng request.
- [Quy ước API](./api-conventions.md): URL, lỗi, phân trang, idempotency và versioning.
- [Tích hợp AI](./ai-integration.md): provider adapter, cấu hình, bảo mật và fallback.
- [Triển khai](./deployment.md): Docker self-host, cloud và lưu trữ file.
- [ADR-001](./decisions/ADR-001-foundation.md): các quyết định nền tảng đã chốt.

## Quy ước làm việc

- Một người phát triển chính, AI hỗ trợ phân tích, viết mã, kiểm thử và tài liệu.
- Làm theo lát cắt dọc nhỏ: dữ liệu → API → UI → test → tài liệu.
- Mỗi quyết định kiến trúc quan trọng được ghi thành ADR.
- Không coi nội dung do AI sinh là hoàn tất nếu chưa có test hoặc kiểm tra thủ công phù hợp.
- Sau hai iteration đầu tiên mới dùng vận tốc thực tế để dự báo ngày phát hành.
