# Checkpoint để tiếp tục nhanh

Cập nhật 2026-09-27. Đọc file này trước, chỉ mở đặc tả/file liên quan; `myplan.txt` giữ lịch sử, không cần đọc lại toàn bộ mỗi phiên.

## Phạm vi hiện tại

- Đã nghiệm thu: auth/root-support/membership, catalog, hồ sơ/trình độ học viên, hồ sơ/năng lực giáo viên, chi nhánh/phòng/lớp nháp, phân công/mẫu tuần/xác nhận lịch/chống trùng.
- Đang bàn giao: đổi ngày/giờ/phòng từng buổi tương lai, hủy/khôi phục, dạy thay, history/idempotency; bổ sung lịch tuần dạng agenda có lọc chi nhánh/phòng/giáo viên/trạng thái. SCH-04/78, SCH-06/152, một phần SCH-05/79 (chưa tháng/kéo-thả).
- User muốn gộp phạm vi liên quan để giảm token/đọc lại context. Một người + AI, không tự dùng subagent; giữ đề cử GPT gpt-6-astra high. Sau code phải nêu checklist nghiệm thu, không tự commit/stage.

## File cần mở khi làm lịch

- Đặc tả/API/checklist: `docs/session-operations.md`; xác nhận mẫu ban đầu: `docs/scheduling.md`.
- Model/migration: `backend/app/models/schedule.py`, `backend/alembic/versions/20260926_0012_session_operations.py`.
- API: `routes/session_operations.py`, `routes/schedules.py`; resource_conflicts dùng chung. Guard tài nguyên tại classrooms.py/teachers.py.
- UI: `frontend/src/SessionOperations.tsx`, `Scheduling.tsx`, App/i18n.
- Test: `backend/tests/test_session_operations.py`, `test_schedules.py`; UI SessionOperations.test.tsx, E2E scheduling.spec.ts (bao gồm cả vận hành mới).

## Bất biến cần giữ

- Tenant → actor/support → tài khoản giáo viên; không đổi thứ tự gây deadlock. Kiểm tra lại quyền sau khóa. PostgreSQL cho concurrency, SQLite không có bảo đảm khóa hàng tương đương.
- Version riêng từng buổi; key idempotency unique tenant + hash payload/đích. Buổi+history+audit cùng transaction; lỗi không mất giữ chỗ cũ. Không xóa history hoặc sửa SQL demo để “test”.
- Chỉ scheduled chiếm tài nguyên. Hủy không tự hoàn phí/thông báo/sinh buổi bù. Khôi phục kiểm tra lại, buổi cũ/mới đều tương lai. Mẫu tuần/cấu trúc lớp không mở lại.
- Dạy thay có thể ngoài class_teachers, vẫn cùng tenant và active; thiếu năng lực cần waiver. API teacher không trả lý do/waiver/history; chỉ lịch hiện hành của mình.
- Mã lớp/chi nhánh/phòng giữ tham chiếu lịch sử; guard lớp nháp cũ vẫn áp dụng dù đã hủy hết buổi. Lịch sử buổi khác với UI log toàn hệ thống.

## Kiểm chứng và vận hành

- Kết quả cuối 2026-09-27: 402 backend đạt, 55 skip là các ca concurrency không áp dụng trên SQLite (đã chạy trên PostgreSQL); 0 lỗi. Báo cáo backend/test-results/session-operations.xml (gitignored), tổng 457 ca, thời gian 1026.26 giây. 66 UI và toàn bộ 14 E2E Chromium đạt; Ruff/ESLint/build đạt, đã xem ảnh mobile sáng/tối. Không cần chạy lại toàn bộ chỉ để tiếp tục bàn giao.
- Docker API/web đã rebuild và đồng bộ code đã kiểm thử; xác minh DB ở `20260926_0012 (head)`, Alembic check không phát hiện thay đổi schema. DB đã ở 0012 lúc nối phiên, không coi lệnh upgrade hôm nay là migration mới từ 0011. Không tắt db/Mailpit, không xóa volume/.env, không seed dữ liệu giả. Web 5173/API health 8000/Mailpit 8025 và module SessionOperations đều HTTP 200; OpenAPI có đủ 6 đường dẫn class-sessions, không có test helpers.
- Đối chiếu trước/sau triển khai 2026-09-27 không đổi: 83 class_sessions, 83 session_teachers, 2 class_teachers, 2 schedule_plans. Checksum dữ liệu session cũ `b1880ab31c6374ee29269db1bf0307b3e41e1ae77e33865fadc349577bfa2bd6`, teacher-link `7dcfacda230a968622945faf25e8f6a8ee7891ab2c3341b64170fbd2e8af089d` (tuple các cột cũ sắp xếp theo id, SHA256 repr). Không chứa nội dung cá nhân.
- Chạy backend PostgreSQL: Docker one-off với SYNAPSE_TEST_POSTGRES=1 và mount app/alembic/tests vào /app; test tạo schema tạm, không public. UI `npm.cmd run test`, lint/build; E2E dùng API8011/web5180 và SQLite tạm.

## Chưa làm / bước sau

Chưa thông báo tự động, học phí/đăng ký/xếp lớp/điểm danh/điểm, lịch rảnh/ngày nghỉ/bù hàng loạt/link online, calendar tháng, AI/học liệu. BUG-004 select native Chrome và màn hình log chung được user hoãn. Sau nghiệm thu, ưu tiên lập kế hoạch **thông báo trong ứng dụng + nền học phí** (chốt quy tắc tài chính trước code), rồi duyệt đăng ký tạo hóa đơn/xếp lớp. Không tự triển khai bước sau khi chưa duyệt.
