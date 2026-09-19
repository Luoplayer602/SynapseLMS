# Kiến trúc hệ thống SynapseLMS

**Phiên bản:** 0.1  
**Trạng thái:** Accepted cho MVP

## Kiến trúc tổng thể

SynapseLMS bắt đầu dưới dạng modular monolith để phù hợp với một người phát triển. Backend FastAPI cung cấp REST API; frontend React gọi API; PostgreSQL lưu dữ liệu nghiệp vụ; object storage lưu file; AI Provider Adapter kết nối dịch vụ bên ngoài hoặc mô hình local.

```text
Browser
  └── React + TypeScript
        └── FastAPI /api/v1
              ├── Auth + RBAC + Tenant Context
              ├── Domain Modules
              ├── Notification Adapter
              ├── Object Storage Adapter
              ├── AI Provider Adapter
              └── PostgreSQL
```

## Module backend

- `auth`: đăng ký, đăng nhập, token và membership.
- `organizations`: tenant, chi nhánh, phòng học và cấu hình.
- `students`, `teachers`: hồ sơ và chuyển trung tâm.
- `courses`, `classes`, `schedules`: chương trình, lớp và buổi học.
- `enrollments`: đăng ký khóa học, duyệt và xếp lớp.
- `attendance`, `assessments`: điểm danh, điểm và kết quả.
- `billing`: học phí, hóa đơn, thanh toán, công nợ, bảo lưu và hoàn phí.
- `practice`: bài luyện tập và lần làm bài.
- `ai`: tư vấn, sinh bài, tóm tắt, provider và usage.
- `notifications`: thông báo trong ứng dụng và adapter mở rộng.
- `audit`: nhật ký thao tác nhạy cảm và phiên hỗ trợ.

## Luồng request bắt buộc

```text
Request
  → Authentication
  → Resolve active membership / support session
  → Resolve tenant context
  → Authorization policy
  → Validation
  → Domain service
  → Repository with tenant scope
  → Audit when required
  → Response
```

Không service nghiệp vụ nào được lấy `organization_id` trực tiếp từ request rồi tin tưởng giá trị đó. Tenant phải đến từ membership đã xác thực hoặc phiên hỗ trợ Root Admin.

## Giao dịch và tác vụ nền

- Giao dịch đồng bộ dùng PostgreSQL transaction.
- Duyệt đăng ký và tạo hóa đơn là một transaction.
- Tạo Enrollment khóa/kiểm tra sĩ số để tránh vượt chỗ.
- Email/SMS, sinh nội dung AI dài và xử lý file có thể chuyển sang worker sau; MVP có thể dùng job table/outbox trước khi thêm message broker.
- Side effect bên ngoài chỉ chạy sau khi transaction chính commit.

## Quan sát hệ thống

- Structured logging với request ID, actor ID và tenant ID; không log dữ liệu cá nhân hoặc API key.
- Health, readiness và migration status endpoint.
- Theo dõi độ trễ/lỗi AI, token, chi phí và provider.
- Audit log là dữ liệu nghiệp vụ, tách khỏi application log.

