# Triển khai SynapseLMS

**Phiên bản:** 0.1

## Mục tiêu

- Cùng codebase chạy được self-host và cloud.
- Cài đặt mặc định bằng Docker Compose.
- Không phụ thuộc độc quyền vào một cloud provider.

## Self-host

Các service tối thiểu:

- `web`: frontend build tĩnh hoặc reverse proxy.
- `api`: FastAPI.
- `db`: PostgreSQL.
- `object-storage`: local filesystem cho cài đặt đơn giản hoặc S3-compatible như MinIO.
- AI local là service bên ngoài do người triển khai cấu hình, ví dụ Ollama hoặc LM Studio.

SQLite chỉ dùng cho development/test đơn giản, không dùng cho triển khai multi-tenant production.

## Cloud

- API và frontend chạy bằng container.
- PostgreSQL managed được khuyến nghị.
- File lưu trên S3-compatible object storage.
- Secret lưu trong secret manager hoặc environment secret của nền tảng.
- Nhà cung cấp hạ tầng tham chiếu sẽ được chọn sau; thiết kế không phụ thuộc nền tảng.

## Lưu trữ file

`ObjectStorage` adapter hỗ trợ:

- Local filesystem cho self-host nhỏ.
- S3-compatible cho cloud hoặc self-host nâng cao.
- File private dùng signed URL có thời hạn; không công khai bucket chứa dữ liệu học viên.
- Metadata lưu trong PostgreSQL, binary lưu ở object storage.

## Cấu hình môi trường

- Cấu hình không nhạy cảm qua environment variables.
- API key AI, JWT signing key và database password phải là secret.
- Có `.env.example` không chứa giá trị thật.
- Startup kiểm tra cấu hình bắt buộc và từ chối chạy nếu production dùng secret yếu/mặc định.

## Backup và phục hồi

- Backup PostgreSQL và object storage theo cùng chính sách lưu giữ.
- Mỗi bản phát hành phải có migration và hướng dẫn rollback phù hợp.
- Kiểm tra phục hồi định kỳ; backup chưa từng restore không được xem là đã xác minh.

