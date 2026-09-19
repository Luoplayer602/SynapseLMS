# ADR-001 — Nền tảng và ranh giới hệ thống

**Trạng thái:** Accepted  
**Ngày:** 2026-09-19

## Bối cảnh

SynapseLMS cần phục vụ nhiều trung tâm, cho phép tự host, hỗ trợ AI từ nhiều nhà cung cấp và vẫn phù hợp với năng lực thực hiện của một người phát triển cùng AI hỗ trợ.

## Quyết định

- Backend: FastAPI và Python.
- Frontend: React, TypeScript và Vite.
- Production database: PostgreSQL; SQLite chỉ dùng cho thử nghiệm cục bộ đơn giản nếu cần.
- ORM/migration: SQLAlchemy và Alembic.
- Kiến trúc ban đầu: modular monolith, không tách microservice.
- Multi-tenancy: shared database/shared schema với `organization_id` và tenant scope bắt buộc.
- AI: interface `AIProvider`; nghiệp vụ không phụ thuộc trực tiếp OpenAI/Gemini/Ollama.
- Gemini API là provider mặc định của bản demo; hỗ trợ thêm OpenAI, Claude, Hugging Face và endpoint local tương thích OpenAI như Ollama/LM Studio.
- Root Admin quản lý tập trung provider và API key; trung tâm không tự nhập khóa trong MVP.
- Triển khai: Docker Compose cho self-host; cùng container có thể dùng trên cloud.
- File dùng local storage khi self-host đơn giản và S3-compatible object storage trên cloud.
- Giao diện: i18n Việt/Anh từ đầu.
- Giấy phép đề xuất: AGPL-3.0, có thể xem xét dual licensing nếu phát sinh nhu cầu thương mại.

## Hệ quả

- Modular monolith giảm chi phí vận hành và phù hợp đội một người.
- Shared schema đơn giản hơn nhưng đòi hỏi test cách ly tenant nghiêm ngặt.
- Provider adapter làm tăng ít mã ban đầu nhưng tránh khóa nhà cung cấp AI.
- AGPL bảo vệ tính mở của các bản triển khai đã sửa đổi, nhưng có thể làm một số doanh nghiệp dè dặt; dual licensing là phương án xử lý sau này.

## Chưa quyết định

- Hạ tầng cloud tham chiếu đầu tiên.
