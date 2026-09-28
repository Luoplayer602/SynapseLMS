# Checkpoint để tiếp tục nhanh

> Bàn giao mới nhất: đọc `docs/next-session-handoff.md` trước. Docker 0013 và comment 19 story Jira đã hoàn tất ngày 2026-09-27. Chờ người dùng nghiệm thu thủ công; không còn process kiểm thử hay triển khai đang chờ.

Cập nhật 2026-09-27. Chỉ mở đặc tả/file liên quan; `myplan.txt` giữ lịch sử, không cần đọc lại toàn bộ mỗi phiên.

## Đợt đã triển khai, chờ nghiệm thu: tuyển sinh → thu phí → điểm danh → thông báo

- Đã có backend/UI Việt–Anh cho phí khóa/trả góp/mã giảm giá, gửi/duyệt/xếp lớp, hóa đơn/thu/đảo thu/in phiếu, lịch học viên, điểm danh và inbox.
- File chính: `docs/admissions-delivery.md`, `backend/app/models/admissions.py`, `api/admission_schemas.py`, `api/routes/admissions.py`, `attendance.py`, `notifications.py`, `services/admissions.py`, migration 0013; `frontend/src/Admissions.tsx`, `Admissions.test.tsx`, `e2e/admissions.spec.ts`.
- Kiểm thử đã hoàn tất: full backend 449 đạt/58 skip/0 lỗi (507 ca, admissions-full.xml); vòng cuối 48 đạt/3 skip/0 lỗi (51 ca, admissions-final.xml), có trùng full; schema bổ sung 1 đạt. Các ca concurrency PostgreSQL đã chạy, skip thuộc biến thể SQLite. UI 72 đạt (frontend/admissions-ui-results.json), full 15 E2E đạt; ca admissions cuối 34.4s đạt. Ruff/ESLint/build đạt; ảnh mobile dark 390px không tràn, ảnh in chỉ phiếu trắng không menu. Không cộng hai vòng backend thành 497 test độc lập.
- Phiên bàn giao đã đọc lại XML/JSON, không chạy lại full test. Hash 75 file trong image API và 34 file web khớp workspace, không rebuild. Đã dừng riêng API, migrate 0012 → 0013, cập nhật API/web bằng `up -d --no-deps`.
- Xác minh thực tế: `20260927_0013 (head)`, Alembic check sạch; API health8000/web5173/module Admissions/Mailpit8025 HTTP 200. OpenAPI có 24 path admissions/attendance/notifications, không `__test`.
- Count/hash cả 10 bảng cũ khớp trước/sau: 2 trung tâm/8 users/2 hồ sơ học viên/1 hồ sơ giáo viên/1 khóa/2 lớp/83 buổi/83 liên kết giáo viên/2 mẫu/0 session history. 11 bảng mới rỗng tại mốc bàn giao. Bộ hash toàn hàng ORDER BY id, image IDs và container IDs được lưu bền vững ở `docs/next-session-handoff.md`.
- DB/Mailpit giữ nguyên container và StartedAt, volume `synapselms_postgres_data`; giữ compose.yaml mở cổng DB 5432. Không .env/seed DB thật/volume/commit/stage, không dọn tsbuildinfo hoặc thay đổi có sẵn của người dùng.
- Jira: đã comment phạm vi/test/deployment/checklist riêng cho đủ 19 story 80/81/82/147/155/161/162/86/87/88/89/90/92/95/96/97/98/99/149, comment IDs 10108–10126 theo bảng trong checkpoint và myplan mục30. Giữ In Progress, chưa Done.
- Giới hạn: VND nguyên, kỳ hạn UTC; chưa hoàn/bảo lưu/chuyển/hủy enrollment/hoàn thành/học lại cùng khóa placed; chưa PDF server, deep-link record, email/SMS worker, báo cáo chuyên cần cả lớp. Root không giả danh inbox trung tâm. ATT-05/FEE-07 chỉ một phần; không đóng toàn bộ story.
- Việc tiếp theo: người dùng nghiệm thu theo vai trò tại `docs/admissions-delivery.md`, báo kết quả để xử lý đúng phạm vi; chưa tự triển khai nghiệp vụ tiếp theo.

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
- Chỉ scheduled chiếm tài nguyên. Hủy tạo thông báo in-app từ 0013, không tự hoàn phí hoặc sinh buổi bù. Khôi phục kiểm tra lại, buổi cũ/mới đều tương lai. Mẫu tuần/cấu trúc lớp không mở lại.
- Dạy thay có thể ngoài class_teachers, vẫn cùng tenant và active; thiếu năng lực cần waiver. API teacher không trả lý do/waiver/history; chỉ lịch hiện hành của mình.
- Mã lớp/chi nhánh/phòng giữ tham chiếu lịch sử; guard lớp nháp cũ vẫn áp dụng dù đã hủy hết buổi. Lịch sử buổi khác với UI log toàn hệ thống.

## Lịch sử kiểm chứng và vận hành 0012

- Kết quả đợt 0012 ngày 2026-09-27 (đã được thay thế bởi checkpoint 0013 ở đầu file): 402 backend đạt, 55 skip là các ca concurrency không áp dụng trên SQLite (đã chạy trên PostgreSQL); 0 lỗi. Báo cáo backend/test-results/session-operations.xml (gitignored), tổng 457 ca, thời gian 1026.26 giây. 66 UI và toàn bộ 14 E2E Chromium đạt; Ruff/ESLint/build đạt, đã xem ảnh mobile sáng/tối. Không cần chạy lại toàn bộ chỉ để tiếp tục bàn giao.
- Docker API/web đã rebuild và đồng bộ code đã kiểm thử; xác minh DB ở `20260926_0012 (head)`, Alembic check không phát hiện thay đổi schema. DB đã ở 0012 lúc nối phiên, không coi lệnh upgrade hôm nay là migration mới từ 0011. Không tắt db/Mailpit, không xóa volume/.env, không seed dữ liệu giả. Web 5173/API health 8000/Mailpit 8025 và module SessionOperations đều HTTP 200; OpenAPI có đủ 6 đường dẫn class-sessions, không có test helpers.
- Đối chiếu trước/sau triển khai 2026-09-27 không đổi: 83 class_sessions, 83 session_teachers, 2 class_teachers, 2 schedule_plans. Checksum dữ liệu session cũ `b1880ab31c6374ee29269db1bf0307b3e41e1ae77e33865fadc349577bfa2bd6`, teacher-link `7dcfacda230a968622945faf25e8f6a8ee7891ab2c3341b64170fbd2e8af089d` (tuple các cột cũ sắp xếp theo id, SHA256 repr). Không chứa nội dung cá nhân.
- Chạy backend PostgreSQL: Docker one-off với SYNAPSE_TEST_POSTGRES=1 và mount app/alembic/tests vào /app; test tạo schema tạm, không public. UI `npm.cmd run test`, lint/build; E2E dùng API8011/web5180 và SQLite tạm.

## Chưa làm / bước sau

Kế hoạch cũ thông báo/học phí/đăng ký/xếp lớp/điểm danh đã được gộp và duyệt trong đợt 0013 ở đầu file. Sau đợt này còn bảo lưu/hoàn phí/chuyển lớp, vòng đời hoàn thành/học lại, kết quả học tập, lịch rảnh giáo viên/ngày nghỉ/bù hàng loạt/link online, calendar tháng, AI/học liệu. BUG-004 select native Chrome và màn hình log chung vẫn hoãn. Không tự triển khai phần ngoài đợt đã duyệt.
