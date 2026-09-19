# Tài liệu SynapseLMS

Thư mục này là nguồn tài liệu chính thức của dự án. Jira dùng để theo dõi tiến độ; các quyết định dài hạn và đặc tả phải được cập nhật tại đây.

## Tài liệu hiện có

- [PRD](./prd.md): mục tiêu, phạm vi và tiêu chí thành công của sản phẩm.
- [Ma trận phân quyền](./rbac.md): quyền của từng vai trò và giới hạn dữ liệu.
- [Mô hình dữ liệu](./data-model.md): thực thể chính và quy tắc multi-tenant.
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
