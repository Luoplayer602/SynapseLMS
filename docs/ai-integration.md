# Tích hợp AI SynapseLMS

Trạng thái triển khai: xem [checkpoint hiện tại](./current-state.md) và [kế hoạch/nghiệm thu cụm AI](./plans/ai-cluster.md). AI **tắt mặc định** trên từng trung tâm. Không có model, API key hay prompt mẫu nào được tự nhập vào tenant thật.

## Cấu hình và quyền

Root mở **Thiết lập AI** để tạo nhiều nguồn OpenAI, Gemini, Claude, API tương thích OpenAI, Ollama và LM Studio. Mỗi nguồn có model ID, tác vụ cho phép, timeout, output token/quota và trạng thái bật/tắt. Root gán danh sách ưu tiên/fallback riêng cho `class_recommendation`, `practice_generation`, `progress_summary`. Quản lý trung tâm bật từng tác vụ và đặt quota/timezone của trung tâm; không thấy key hoặc URL nguồn hệ thống. Thiết lập một nguồn không tự bật AI cho trung tâm.

Credential chỉ nhập mới/thay, **không có API đọc lại**. DB lưu ciphertext Fernet có xác thực và `credential_key_version`. Compose mount `/run/secrets/synapse_ai_master_key` từ file ngoài repository (`C:\Users\ADMIN\SynapseLMS-secrets\ai-master-key` trên máy hiện tại). Sao lưu DB phải đi cùng bản sao an toàn của file khóa; không đưa file khóa vào Git hay backup công khai. Thiếu khóa sẽ làm nguồn dùng credential không hoạt động; tuyển sinh, học phí, học liệu và bài luyện đã duyệt vẫn hoạt động. Khi quay khóa, mount khóa mới tạm thời, ngừng traffic AI, chạy `python -m app.ai_key_rotation --new-key-file <đường-dẫn>` để kiểm tra rồi thêm `--apply` để mã hóa lại trong một transaction; sau đó chuyển Compose secret sang khóa mới và khởi động lại API. Giữ khóa cũ an toàn cho đến khi xác minh decrypt/restore.

Nguồn cloud chính hãng dùng endpoint cố định trên server. API tương thích tùy chỉnh chỉ nhận HTTPS hostname trong `SYNAPSE_AI_CUSTOM_HOSTS` (JSON array do vận hành cấp). Ollama/LM Studio chỉ nhận IP private nằm trong `SYNAPSE_AI_LOCAL_HOSTS`; địa chỉ phải truy cập được **từ container API**. Không nhận localhost, URL chứa credential/query, redirect hoặc URL tuỳ ý từ học viên. Hai allowlist mặc định rỗng, không sửa `.env` để mở rộng; cấu hình qua Compose override hoặc biến môi trường lúc vận hành. Không mở local model ra Internet chỉ để kết nối LMS.

## Prompt Studio

Root tạo prompt riêng theo tác vụ và VI/EN, dùng biến cho phép `{task}` và `{locale}`; bản nháp bất biến theo revision. `test` hiện kiểm tra **cấu trúc/biến và policy ghép server**, không gọi model hay dữ liệu học viên. Sau khi Root xem nội dung và ghi lý do, `publish` chuyển active pointer trong transaction; rollback là publish lại revision cũ. UI có lịch sử và so sánh dòng. Mỗi AI run ghim prompt ID, provider ID, digest input và source refs, không log nội dung PII/prompt đầy đủ. Policy về quyền/nguồn/schema đầu ra luôn ở server, người sửa prompt không thể thay chúng. Trước khi đưa prompt mới vào dùng thật, Root vẫn phải thử output trên dữ liệu giả và kiểm tra thủ công từng tác vụ/provider; nút test cấu trúc không thay thế đánh giá chất lượng nội dung.

## Ba tác vụ và bài luyện

- **Gợi ý lớp:** server gọi `admissions.candidates()` trước, AI chỉ được trả thứ tự của đúng candidate ID. Cảnh báo trình độ/lịch vẫn còn; xếp lớp thủ công tái kiểm tra điều kiện/chỗ/version ngay lúc ghi. Không có candidate hoặc một candidate dùng quy tắc; AI lỗi/tắt dùng thứ tự deterministic.
- **Bài luyện:** quản lý sinh bản nháp từ mục tiêu khóa học hoặc nhập bài dự phòng đã kiểm duyệt; giáo viên được phân công khóa học và quản lý duyệt/ẩn. Học viên chỉ nhận câu đã phát hành của khóa có enrollment đang hiệu lực, không thấy đáp án trước khi nộp. Câu trả lời đóng được chấm ở server. Một câu chỉ hoàn thành một lần/học viên; request key lặp trả cùng kết quả; row lock/unique bảo vệ nộp song song. Không có bài đã duyệt thì UI báo chưa có bài mới, không tự cấp streak từ output lỗi.
- **Tiến độ:** chỉ lấy điểm tổng kết đã công bố, chuyên cần đã chốt và số bài luyện; thiếu điểm không biến thành 0. AI chỉ chọn fact ID đã cấp và một hành động từ allowlist; UI hiển thị giá trị gốc kèm đường mở nguồn. Giáo viên chỉ xem tổng hợp lớp được phân công. Cache theo viewer, phạm vi, facts digest, prompt và route; sửa nguồn/quyền ở request tiếp theo làm cache cũ không còn hợp lệ. AI lỗi/tắt trả tóm tắt theo quy tắc.

Streak tính một ngày khi hoàn thành ít nhất một bài hợp lệ theo timezone trung tâm ở thời điểm nộp, không cần đạt điểm tối thiểu. Mốc 3/7/14 ngày mở Neo Pop/Clay Garden/Liquid Glass; Synapse Soft luôn có. Bỏ ngày ngắt chuỗi hiện tại nhưng không thu hồi theme đã mở; theme và lựa chọn tách theo tenant. ASR/TTS/VAD thuộc đợt tiếng nói khác.

## Vận hành và kiểm tra

Migration `20261001_0017` chỉ thêm bảng, không sửa bảng cũ hay seed tenant. Trước rollout cần `pg_dump -Fc`, baseline count/hash; diễn tập restore → nâng/hạ/nâng trên DB scratch, kiểm tra Alembic schema. Sau rollout kiểm tra `/api/v1/health`, `/openapi.json`, UI Root/quản lý/học viên/giáo viên, backup+restore cả DB và khóa. Không xóa volume DB/Mailpit/học liệu.

Test dùng fake provider, không gọi API trả phí. `backend/tests/test_ai_config.py`, `test_ai_prompts.py`, `test_ai_recommendations.py`, `test_ai_progress.py`, `test_practice.py` bao gồm key masking/rotation, prompt version, tenant/facts, idempotency và streak; ca đồng thời chạy trên PostgreSQL schema test. `frontend/e2e/ai-cluster.spec.ts` chạy với SQLite tạm. Test kết nối trên UI Root gọi nguồn thật, nên chỉ dùng khi chủ động kiểm tra nguồn/chi phí. Hiện usage ghi lượt và output token; giá thành theo nhà cung cấp thay đổi nên chưa hiện ước tính tiền.
