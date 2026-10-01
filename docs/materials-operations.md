# Vận hành học liệu 0016

Học liệu dùng DB PostgreSQL cho metadata/quyền và volume Docker `synapselms_material_data` cho file riêng tư. API chỉ cấp nội dung qua `/api/v1/materials/versions/{id}/content` sau khi xác thực; không phục vụ trực tiếp volume. ClamAV chạy nội bộ, upload chưa quét được giữ `pending_check` và không thể công bố; người có quyền có thể gọi `POST /api/v1/materials/versions/{id}/retry-scan`. File bị từ chối được xóa, bản ghi giữ lịch sử. Giới hạn mặc định 2 GiB/tenant, 25 MB cho PDF/ảnh và 50 MB cho MP3.

## Sao lưu và khôi phục

Chụp `pg_dump -Fc` và bản sao volume học liệu tại **cùng một mốc bảo trì**, sau khi tạm ngừng upload/gắn học liệu. Lưu kèm checksum của cả hai. DB dump riêng không đủ khôi phục nội dung file; volume riêng không đủ khôi phục quyền và metadata. Trước khi restore DB thật, diễn tập trên DB và volume mới: chạy migration tới head, so khớp số bản ghi và SHA-256 từng file với `material_versions.checksum`, đăng nhập bằng từng vai trò để mở một bản đã cấp, thử thu hồi và Range. Không dùng `docker compose down -v` cho thao tác này. Dừng API và worker `material-gc` trong khi restore; chỉ bật lại khi cả DB lẫn volume cùng mốc đã sẵn sàng. Giữ bản backup trước restore để quay lại nếu kiểm tra thất bại.

`python -m app.material_gc` chỉ báo số file mồ côi hơn 24 giờ; `--apply` mới xóa. Worker `material-gc` chạy định kỳ mỗi ngày với cùng volume, tra DB trước khi xóa. Không xóa file đã tham chiếu dù tài liệu đã lưu trữ/thu hồi, vì lịch sử và khả năng phục hồi còn cần chúng.

## Kiểm tra sau cập nhật

Kiểm tra revision `20261001_0016`, `alembic check`, health API/web, OpenAPI có `/api/v1/materials`, `docker compose ps` cho `db`, `mailpit`, `clamav`, `api`, `web`, `material-gc`, và đối chiếu count/hash bảng cũ với baseline trước migration. Dùng tenant test cô lập để thử PDF/ảnh/audio/link và quyền; không tạo dữ liệu thử trong tenant thật. Sau khi restart API, file đã cấp vẫn mở được. Kiểm tra ClamAV `healthy`; khi tạm ngừng scanner, file upload mới phải ở `pending_check` và không thể phát hành.

Checklist nghiệp vụ theo vai trò nằm tại [kế hoạch học liệu](./plans/learning-materials.md#7-checklist-nghiệm-thu-thủ-công-theo-vai-trò).
