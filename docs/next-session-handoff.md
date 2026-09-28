# Bàn giao phiên tiếp theo — 2026-09-27

Đây là **hồ sơ lịch sử bàn giao0013**, giữ bằng chứng tại thời điểm triển khai. Trạng thái mới nhất đọc [current-state](./current-state.md): người dùng đã xác nhận nghiệm thu toàn bộ phạm vi đã bàn giao ngày2026-09-27, và đã triển khai0014 theo [kế hoạch bảo lưu/hoàn phí](./plans/reservation-refund.md). Những câu “chờ nghiệm thu” và bảng mới rỗng bên dưới mô tả mốc bàn giao cũ, không phải trạng thái hiện tại.

## Mục tiêu và cách làm

- SynapseLMS: mã nguồn mở, đa trung tâm; một người dùng + AI. Tiếp tục hoàn tất đợt đã duyệt tuyển sinh → học phí → điểm danh → thông báo; không lập lại kế hoạch hoặc tự mở rộng tính năng.
- Người dùng muốn gom nghiệp vụ liên quan để tiết kiệm token. Chỉ đọc checkpoint và file liên quan, không đọc lại toàn bộ myplan. Không chạy lại full test khi có báo cáo hợp lệ.
- Đề cử đã thống nhất cho đợt này: GPT gpt-6-astra high. Khi chuẩn bị một đợt code mới phải ghi đề cử model/effort; sau code luôn có tiêu chí test thủ công.
- Không subagent, commit/stage, reset, sửa .env, seed dữ liệu thật, xóa volume. Giữ thay đổi có sẵn của người dùng ở compose.yaml: db mở cổng 5432:5432. Giữ cả các thay đổi chưa commit khác, không tự dọn tsbuildinfo.
- Workspace Windows PowerShell: C:\Users\ADMIN\VSCode\SynapseLMS. Dùng apply_patch để sửa file, rg để tìm, npm.cmd. Đọc văn bản với Get-Content -Encoding UTF8 để tránh lỗi hiển thị tiếng Việt. Docker/test cần escalation theo quyền công cụ; không gọi shell lồng để sửa/xóa.

## Đã làm xong trong code

- Chính sách phí theo khóa, trả góp, mã giảm giá; học viên/giáo vụ gửi yêu cầu, giáo vụ duyệt/từ chối; duyệt tạo hóa đơn và xếp lớp trong cùng transaction.
- Tự xếp nếu đúng một lớp phù hợp chắc chắn; thiếu dữ liệu/trình độ/lịch rảnh đưa hàng chờ để giáo vụ xử lý. Không vượt sức chứa, lịch trùng hoặc tài nguyên không hợp lệ. Hàng chờ này chưa phải FIFO theo lớp.
- Thu tiền mặt/chuyển khoản thủ công, thu nhiều lần, công nợ, đảo khoản thu sai có lý do và giữ lịch sử; in phiếu qua trình duyệt/Chrome Save as PDF. Không cổng thanh toán, không hoàn phí.
- Học viên xem lịch, hóa đơn, chuyên cần của mình. Giáo viên thực tế của buổi mới được điểm danh; nháp/chốt/sửa có lý do, version/history. Root/giáo vụ không được điểm danh.
- Inbox in-app và đánh dấu đã đọc; đổi/hủy/khôi phục/dạy thay thông báo người liên quan. Snapshot thông báo lấy đúng version SessionHistory, chỉ whitelist tên lớp/giờ/timezone/phòng, không lộ lý do nội bộ hoặc lần sửa tương lai cho giáo viên đã bị thay.
- UI Việt/Anh, sidebar theo vai trò, tiền VND nguyên, snapshot phí bất biến khi duyệt, kỳ hạn theo ngày UTC. Idempotency gắn tenant/actor/payload; transaction chung nghiệp vụ/audit/history/inbox; PostgreSQL khóa tenant đồng bộ với lịch.
- Enrollment chưa có hoàn thành/hủy/chuyển/bảo lưu nên chưa học lại cùng khóa đã placed. Không báo cáo chuyên cần cả lớp, PDF server, deep-link từng record, email/SMS worker, AI, học liệu, QR, calendar tháng. BUG-004 select native Chrome và UI log chung vẫn hoãn.

## File chính

- Hợp đồng API/quyền/giới hạn/checklist: docs/admissions-delivery.md.
- Model 11 bảng: backend/app/models/admissions.py, export models/__init__.py. AdmissionSettings, FeePolicy, DiscountCode, AdmissionOpening, AdmissionRequest, Enrollment, Invoice, Payment, AttendanceSheet, BusinessOperation, Notification.
- Migration backend/alembic/versions/20260927_0013_admissions.py chỉ thêm bảng, không backfill. Downgrade từ chối khi có dữ liệu trong bất kỳ bảng mới nào.
- DTO backend/app/api/admission_schemas.py; service backend/app/services/admissions.py; routes admissions.py, attendance.py, notifications.py và đăng ký api/router.py.
- Tích hợp cũ: routes/courses.py thêm quyền/guard tham chiếu; students.py chặn archive khi còn yêu cầu/enrollment tương lai; session_operations.py chặn trùng lịch học viên và tạo thông báo.
- UI frontend/src/Admissions.tsx, admissions.css, Admissions.test.tsx; App.tsx/i18n.ts. Receipt dùng portal vào body để in chỉ có phiếu; form chống double-submit/khóa khi kết quả không chắc chắn, không tự retry mutation.
- Tests backend/tests/test_admissions.py, frontend/e2e/admissions.spec.ts. Helper đồng hồ điểm danh chỉ ở tests/e2e_server.py, không có trong API thật. E2E mới tạo trung tâm riêng admission-e2e để không ảnh hưởng fixture demo-a của test cũ.

## Kết quả kiểm thử xác nhận

- Full backend: backend/test-results/admissions-full.xml, 507 ca = 449 passed / 58 skipped / 0 failures / 0 errors, 950.128 giây. Các skip là biến thể SQLite cần concurrency PostgreSQL; ca PostgreSQL đã chạy.
- Sau full có hai tinh chỉnh: roster max 500 → 10000 khớp capacity lớp và whitelist snapshot thông báo đúng version. Test schema mới đạt riêng (admissions-schema.xml).
- Vòng cuối ĐÃ XONG, đọc XML trong phiên bàn giao: backend/test-results/admissions-final.xml, 51 ca = 48 passed / 3 skipped / 0 failures / 0 errors, 309.556 giây. Không còn cần chờ session 48512; không chạy lại full 16 phút.
- UI mới nhất 72 passed, report frontend/admissions-ui-results.json (gitignored, ngoài thư mục Playwright dọn).
- Full 15 E2E Chromium passed (2.5 phút); sau tinh chỉnh hiển thị thông báo/receipt, E2E admissions chạy lại passed 34.4 giây. Đã xem ảnh mobile dark 390px không tràn và ảnh print chỉ có phiếu trắng không menu.
- Ruff, ESLint, TypeScript/Vite build, git diff --check đạt. ESLint từng race với Playwright xóa artifacts, đã thêm global ignores rồi chạy lại đạt; .dockerignore bỏ artifacts. Không phải lỗi nghiệp vụ còn mở.
- Có thể báo chính xác: full backend 449 đạt + vòng cuối 48 đạt (có trùng); đừng cộng thành 497 test độc lập. Tổng unique sau thêm schema là 450 pass/58 skip, nhưng không có một full report duy nhất cho 508 ca.

## Docker: đã triển khai và xác minh ngày 2026-09-27

- Trước triển khai: DB ở `20260926_0012`; cả 10 count/hash khớp baseline bên dưới. Đọc lại XML full/final/schema và JSON UI xác nhận kết quả đạt, không chạy lại full test.
- Đối chiếu SHA256 75 file API (app/alembic/config/lock) và 34 file web (src/package/lock/Vite/index) trong image với workspace: không khác biệt. Dùng image đã build, không rebuild hoặc sửa code trong phiên bàn giao.
- Đã chạy thành công theo thứ tự: `docker compose stop api`; `docker compose run --rm --no-deps api .venv/bin/alembic upgrade head`; `docker compose up -d --no-deps api web`.
- Sau triển khai: `alembic current` = `20260927_0013 (head)`; `alembic check` = `No new upgrade operations detected.` API `/api/v1/health` trả HTTP 200 và `status=ok`; web5173, `/src/Admissions.tsx`, Mailpit8025 đều HTTP 200. OpenAPI có 24 path admissions/attendance/notifications, không có `__test`.
- Count và SHA256 toàn hàng của cả 10 bảng cũ trước/sau khớp baseline. Cả 11 bảng mới đều 0 hàng: admission_settings, fee_policies, discount_codes, admission_openings, admission_requests, enrollments, invoices, payments, attendance_sheets, business_operations, notifications. Đây là mốc trước nghiệm thu, không phải yêu cầu giữ rỗng sau khi người dùng thao tác.
- API chạy image `sha256:93cdf231b25e97125af1c0cad77dfec9ade60bcd4a65a615ad1862df643e6078`; web chạy image `sha256:bf0916e794b861ec5a50bf6900058741594ce0d9edce2e91f7ea112542ee6e13`.
- DB giữ container `18c0b2202fedf62e1f6efc06d2b7cbc02797d4c1879a59f738ac0ca68eef46c5`, StartedAt `2026-09-27T15:51:46.637635301Z`, volume `synapselms_postgres_data`. Mailpit giữ container `e1376460d90970631472cefd9d409ffdc4ec9c157ff3a5bcc166044720c33950`, StartedAt `2026-09-27T15:51:46.63115817Z`. Cả hai healthy, không bị dừng/recreate khi cập nhật API/web.
- Giữ nguyên compose.yaml mở DB `5432:5432`, .env, dữ liệu và các thay đổi chưa commit; không seed, không stage/commit. Kiểm tra sau triển khai chỉ đọc, chưa thực hiện nghiệm thu bằng dữ liệu thật.

Baseline trước 0013: SELECT * FROM từng bảng ORDER BY id, lấy tuple từng hàng bằng SQLAlchemy, SHA256 của repr([tuple(row) for row in rows]). Không in dữ liệu cá nhân. Python chạy qua docker compose exec -T api .venv/bin/python, import engine từ app.db.sync và text từ sqlalchemy. Không dùng hash cũ của 0012 chỉ lấy một số cột để so với hash ALL columns này.

| Bảng | Count | SHA256 |
| --- | ---: | --- |
| organizations | 2 | e29bab76ed85170fbc609bb112d4e05a13d86d24fe49f0b720e7b3afe7d3be09 |
| users | 8 | 98d52ab0f7ba9c6ed8a6af43e5a008e9652483374b6bab05d0a77d5201abb55d |
| student_profiles | 2 | 315fb199695f3168fb601c6c52b737e35cefb59a52d9678485993e8dfcc3c0d7 |
| teacher_profiles | 1 | 7b0a24b1e4bcbb33bf31f8a92dd88478585c3adbd7d84ceb908ad652c5516096 |
| courses | 1 | 5d25fd698b8132a16e23017edbaaba1c03ecdc3e75e07501628963dc98f0084a |
| learning_classes | 2 | 247ad4858dec29bbe568f7101c2169f4ededba1fb04576a6c5fa510745a7b43b |
| class_sessions | 83 | ff48cb00c0d2fa83aef8306fa54103f7f6e95d43cb08087efd4dcbdc7afc6aa4 |
| session_teachers | 83 | 7dcfacda230a968622945faf25e8f6a8ee7891ab2c3341b64170fbd2e8af089d |
| schedule_plans | 2 | 4566d8c11f4cf55351b6264dfb451db9d9f398082b64eb6f3701452ca22c1f35 |
| session_history | 0 | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |

## Jira và tài liệu đã chốt

- CloudID đã dùng: 10aa9420-83e0-48d9-a5f6-ec5eb78b0150. Phiên mới khám phá tool Jira sẵn có; nếu cần site context lấy accessible resources một lần. Không cần cài plugin mới.
- Đã đối chiếu 19 story đều In Progress và thêm comment phạm vi thực tế, kết quả kiểm thử, triển khai/bảo toàn dữ liệu và tiêu chí nghiệm thu riêng từng story. Không gọi transition, chưa Done.
- Map: 80 đăng ký;81 sức chứa;82 trùng;147 cảnh báo trình độ;155 duyệt;161 tự xếp/manual;162 chặn nợ;86 phí khóa;87 hóa đơn;88 thu;89 nợ;90 mã giảm;92 phiếu PDF;95 roster;96 điểm danh;97 trạng thái;98 lịch sử;99 chuyên cần;149 inbox.
- 92/FEE-07 mới browser print/PDF;99/ATT-05 mới tỷ lệ cá nhân, chưa báo cáo lớp: comment nêu rõ PHẠM VI MỘT PHẦN, KHÔNG đóng toàn bộ story. Không đụng ticket ngoài scope như hoàn phí/chuyển lớp/AI.
- Tool đã dùng: `mcp__atlassian__addOrEditJiraIssueComment`; tất cả 19 lần trả thành công. Comment IDs thực tế:

| Story SYNAPSELMS- | Comment ID |
| --- | --- |
| 80 | 10108 |
| 81 | 10109 |
| 82 | 10110 |
| 147 | 10111 |
| 155 | 10112 |
| 161 | 10113 |
| 162 | 10114 |
| 86 | 10115 |
| 87 | 10116 |
| 88 | 10117 |
| 89 | 10118 |
| 90 | 10119 |
| 92 | 10120 |
| 95 | 10121 |
| 96 | 10122 |
| 97 | 10123 |
| 98 | 10124 |
| 99 | 10125 |
| 149 | 10126 |

- `docs/current-state.md` gộp checkpoint cuối và đánh dấu kiểm chứng 0012 là lịch sử; hủy buổi đã có thông báo in-app từ 0013. `myplan.txt` mục30, `docs/auth-operations.md` và `docs/admissions-delivery.md` đã ghi triển khai thực tế/chờ nghiệm thu.
- README/docs README/data-model/rbac/class-foundation/session-operations/workflows enrollment đã cập nhật đợt mới; chỉ sửa nếu còn mâu thuẫn, không mở thêm công việc.

## Bàn giao cho người dùng sau deployment

Nêu gọn tính năng, kết quả test, Docker/migration, dữ liệu cũ bảo toàn, chưa commit. Checklist theo vai trò và link docs/admissions-delivery.md:

1. Root mở hỗ trợ trung tâm → thiết lập tuyển sinh: phí 1 triệu, 2 kỳ 50/50, mã giảm10%, mở lớp có lịch tương lai.
2. Học viên đủ hồ sơ gửi đăng ký; giáo vụ duyệt một lần tạo hóa đơn900k, mỗi kỳ450k; đủ điều kiện thì tự xếp, không thì manual có lý do.
3. Thu300k còn600k; đảo khoản thu có lý do nợ trở lại900k, khoản cũ vẫn có lịch sử; in/lưuPDF chỉ có phiếu.
4. Giáo viên đúng buổi điểm danh sau khi buổi bắt đầu; nháp chưa lộ cho học viên, chốt hiển thị, sửa sau chốt yêu cầu lý do. Không sửa đồng hồ DB thật để test.
5. Học viên chỉ xem của mình; inbox hiển thị thông báo liên quan. Root xem inbox của chính Root, không tự thấy inbox của người khác.
6. Trùng lịch/hết chỗ/sai quyền/staleversion/thu quá nợ phải bị chặn, không tạo dữ liệu dở dang.

Sau khi bàn giao thì chờ người dùng nghiệm thu; chưa tự triển khai đợt bảo lưu/hoàn phí/chuyển lớp tiếp theo.
