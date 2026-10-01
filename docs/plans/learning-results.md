# Kế hoạch: đầu điểm, sổ điểm và công bố kết quả học tập

Ngày2026-09-30. Người dùng đã duyệt triển khai đợt kết quả học tập. Code, kiểm thử và deployment migration0015 đã hoàn tất; người dùng chưa nghiệm thu thủ công đợt này. Đợt0014 trước đó mới được test nhanh, chưa xác nhận toàn checklist.

Đề cử model: GPT gpt-6-astra — high. Lý do: đợt này cần giữ nhất quán điểm thập phân, tenant/RBAC, roster theo thời điểm, lịch sử sau công bố, thao tác đồng thời và migration bảo toàn dữ liệu.

## 1. Mục tiêu, phạm vi và phần chưa làm

Mục tiêu là hoàn tất một chu trình kết quả học tập có thể vận hành: quản lý cấu hình mẫu đầu điểm của khóa học → giáo viên phụ trách khởi tạo sổ điểm lớp → nhập điểm/nhận xét → hẹn hoặc công bố → quản lý khóa sổ → học viên xem tổng hợp và tiến độ theo kỹ năng.

Phạm vi đề xuất bao gồm RES-01 đến RES-05 và phần khóa bảng điểm của RES-07:

- Mẫu chấm điểm có phiên bản theo khóa học, các đầu điểm nghe/nói/đọc/viết/tổng hợp, điểm tối đa và trọng số.
- Sổ điểm duy nhất cho một lớp, snapshot mẫu tại lúc khởi tạo; thay đổi mẫu sau đó không viết lại sổ lớp cũ.
- Giáo viên được phân công lớp nhập/sửa điểm và nhận xét công khai; roster được xác định theo quyền học tại thời điểm đánh giá.
- Tính tổng điểm chuẩn hóa về thang100 và tổng hợp theo kỹ năng; hiển thị tỷ lệ trọng số đã được đánh giá.
- Hẹn thời điểm công bố, học viên chỉ đọc kết quả đã đến giờ; quản lý/Root hỗ trợ khóa hoặc mở khóa có lý do và lịch sử.
- UI Việt–Anh cho cấu hình mẫu, sổ điểm theo lớp và kết quả cá nhân; giữ responsive, keyboard/focus và phong cách Soft hiện có.

Điểm kết thúc: một khóa học có mẫu hợp lệ, giáo viên phụ trách nhập được điểm cho roster đúng thời điểm, công bố và khóa sổ; học viên chỉ thấy dữ liệu của mình; quản lý/giáo vụ xem đúng quyền; migration, tenant, concurrency, tính toán và E2E đạt; triển khai được đối chiếu dữ liệu trước khi bàn giao nghiệm thu.

Chưa làm trong đợt này: RES-06 xuất Excel/PDF; tự chuyển enrollment sang hoàn thành, chứng chỉ hoặc học lại/chuyển lớp; bài thi trực tuyến, câu hỏi, bài nộp và chấm tự động; rubric tự do/file đính kèm; AI sinh bài, tóm tắt, streak và mở theme; thông báo theo lịch bằng background worker; điều kiện đạt kết hợp điểm/chuyên cần/xác nhận; báo cáo liên lớp hoặc dashboard mới. Chuyên cần chỉ hiển thị làm ngữ cảnh, không tự quyết định đạt/rớt.

## 2. Quy tắc nghiệp vụ, quyền, dữ liệu và API

### 2.1 Mẫu đầu điểm của khóa học

- Quản lý trung tâm và Root trong phiên hỗ trợ đúng tenant được tạo/sửa bản nháp, công bố và ngừng dùng mẫu; giáo vụ chỉ xem. Giáo viên/học viên không sửa mẫu.
- Một mẫu gồm mã, tên, phiên bản và danh sách đầu điểm. Mỗi đầu điểm có mã/tên, kỹ năng `listening`, `speaking`, `reading`, `writing` hoặc `general`, điểm tối đa dương, trọng số nguyên theo basis point và thứ tự hiển thị.
- Tổng trọng số phải đúng10.000 basis point trước khi công bố; không dùng float cho trọng số hoặc phép tính. Điểm đầu vào/đầu ra của khóa không bị suy diễn thành điểm bài kiểm tra.
- Mẫu đã công bố là bất biến. Muốn đổi phải sao chép thành phiên bản nháp mới; mỗi khóa chỉ có một phiên bản đang công bố để khởi tạo sổ mới. Sổ lớp đã tạo giữ snapshot phiên bản cũ.
- Không cho xóa cứng mẫu/đầu điểm đã được sổ lớp tham chiếu. Ngừng dùng chỉ ngăn khởi tạo mới.

### 2.2 Sổ điểm, roster và nhập điểm

- Một lớp chỉ có một sổ điểm. Giáo viên phải có hồ sơ chưa lưu trữ và có `ClassTeacher` của lớp; chỉ được phân công một buổi thay thế qua `SessionTeacher` không đủ quyền sửa sổ điểm cả lớp.
- Giáo viên khởi tạo sổ từ mẫu đang công bố của đúng course. Server khóa và kiểm tra lại tenant, lớp, course, mẫu và phân công trước khi tạo; unique + `request_key` ngăn tạo trùng khi retry/đồng thời.
- Mỗi đầu điểm của lớp có `assessed_at` UTC. Giáo viên đặt thời điểm trước khi nhập điểm; sau khi đã có điểm thì không đổi để tránh thay roster lịch sử. Có thể liên kết `session_id` cùng lớp nếu đánh giá diễn ra trong buổi học, nhưng không bắt buộc.
- Roster của từng đầu điểm dùng `EnrollmentPeriod` tại `assessed_at`, không chỉ trạng thái enrollment hiện tại. Bảo lưu/hủy sau đó không xóa điểm quá khứ; học viên chưa có quyền học tại thời điểm đánh giá không được ghi điểm.
- Điểm lưu chính xác hai chữ số thập phân, từ0 đến điểm tối đa; không nhận NaN/float sai số. Không có bản ghi nghĩa là chưa chấm, không tự coi là0. Nhận xét là nội dung học viên sẽ thấy, giới hạn độ dài và không có trường ghi chú nội bộ trá hình.
- Lưu theo đầu điểm bằng payload hàng loạt, kiểm tra roster đầy đủ/ID trùng, `version` và `request_key`; transaction hoặc thành công toàn bộ hoặc rollback. Retry cùng payload trả cùng kết quả, cùng key khác payload bị từ chối.
- Trước thời điểm công bố, giáo viên sửa không cần lý do. Khi kết quả đã có hiệu lực công bố, mọi sửa điểm/nhận xét bắt buộc lý do và lưu snapshot trước/sau. Khi sổ bị khóa, giáo viên không thể sửa.

### 2.3 Tính tổng, công bố và khóa sổ

- Điểm tổng chuẩn hóa thang100: tổng của `(điểm đạt / điểm tối đa) × trọng số`; dùng Decimal và quy tắc làm tròn hai chữ số thống nhất ở server. UI không tự tính nguồn sự thật riêng.
- Mỗi học viên chỉ tính các đầu điểm mà enrollment có hiệu lực tại `assessed_at`. Nếu tổng trọng số đủ điều kiện nhỏ hơn10.000, server chuẩn hóa trên phần đủ điều kiện và trả thêm `coverage_percent`; nếu còn bất kỳ đầu điểm đủ điều kiện nào chưa chấm thì `final_score=null`, không hiện kết quả tạm như kết quả cuối.
- Tổng theo kỹ năng chuẩn hóa trong các đầu điểm cùng kỹ năng. `general` chỉ góp tổng chung. Không suy ra cấp độ CEFR/JLPT hoặc pass/fail từ điểm.
- Giáo viên phụ trách đặt `publish_at` hiện tại hoặc tương lai. Trước khi đến giờ có thể đổi lịch; sau khi đã đến giờ không được lùi/hủy để che kết quả đã thấy. Học viên chỉ đọc điểm của enrollment bản thân khi `publish_at <= now`; manager/staff/teacher xem theo quyền trước công bố.
- Không thêm background worker trong đợt này nên hẹn giờ làm dữ liệu tự hiển thị theo đồng hồ server, chưa gửi notification đúng thời điểm. Công bố tức thì cũng không tạo thông báo để hai chế độ có hành vi nhất quán; đây là giới hạn được bàn giao rõ.
- Quản lý/Root hỗ trợ được khóa sổ sau công bố; giáo vụ chỉ xem. Mở khóa để sửa sai bắt buộc lý do, version và audit/history. Quản lý không được sửa nội dung điểm, kể cả khi sổ mở.
- Chuyên cần từ các `AttendanceSheet` đã chốt được trả như thông tin tham khảo; không đưa vào công thức và không sửa dữ liệu điểm danh.

### 2.4 Dữ liệu và API dự kiến

Các file/bảng dưới đây là tên dự kiến tạo khi triển khai; chưa tồn tại tại lúc lập kế hoạch:

- `course_grading_schemes`: tenant, course, số phiên bản, trạng thái draft/published/retired, version optimistic, actor/time.
- `course_grading_components`: scheme, code/name, skill, max score Decimal, weight basis point, display order.
- `class_gradebooks`: tenant, class/course/scheme, snapshot mẫu, `publish_at`, lock state/actor/time, version.
- `class_grade_items`: bản sao đầu điểm theo gradebook, `assessed_at`, session tùy chọn và thứ tự.
- `student_scores`: tenant/class/gradebook/item/enrollment, Decimal score, comment, actor/time/version; unique theo item + enrollment.
- Tái sử dụng `BusinessOperation` cho idempotency và lịch sử thay đổi. Thêm unique composite cần thiết cho `LearningClass(id, course_id, organization_id)` và `Enrollment(id, class_id, organization_id)` để FK tenant/class được bảo vệ ở DB, sau khi kiểm tra dữ liệu hiện hữu không trùng.

API dự kiến dưới `/api/v1`:

- `GET/POST /grading-schemes`, `GET/PATCH /grading-schemes/{id}`, `POST /grading-schemes/{id}/publish`, `/clone`, `/retire`.
- `GET /results/classes` theo quyền; `POST /results/classes/{class_id}/gradebook` khởi tạo; `GET /results/classes/{class_id}` đọc sổ.
- `PUT /results/classes/{class_id}/items/{item_id}` lưu roster điểm; `POST /results/classes/{class_id}/publication`; `POST /results/classes/{class_id}/lock` và `/unlock`.
- `GET /results/mine` chỉ trả kết quả đã công bố của học viên hiện tại, có pagination và không nhận student/user ID từ client.
- Mọi read dùng no-store, tenant scope và DTO whitelist. Root không có API kết quả tenant nếu thiếu support session; mất membership/support/teacher assignment phải bị chặn ở request kế tiếp.

## 3. Bản đồ thay đổi đã xác minh

Các đường dẫn hiện hữu đã được kiểm tra ngày2026-09-30. Đường dẫn mới ghi rõ “dự kiến tạo”; symbol mới chỉ mô tả trách nhiệm, không khẳng định đã tồn tại.

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol hoặc trách nhiệm thay đổi | Test tương ứng |
| --- | --- | --- | --- | --- |
| Model kết quả | `backend/app/models/results.py` | Dự kiến tạo | Năm bảng mục2.4, constraints/version/FK | `test_results.py`: constraints/tenant/decimal |
| Export và khóa FK | `backend/app/models/__init__.py`; `backend/app/models/classroom.py`; `backend/app/models/admissions.py` | Sửa | Export model; composite keys cho LearningClass/Enrollment | migration + model/schema test |
| Migration0015 | `backend/alembic/versions/20260930_0015_learning_results.py` | Dự kiến tạo | Bảng/index/FK mới, không backfill nghiệp vụ | upgrade/downgrade/roundtrip PostgreSQL + SQLite |
| DTO | `backend/app/api/result_schemas.py` | Dự kiến tạo | Scheme/component/score/publication/lock payload; Decimal, version, reason, request_key | payload biên/extra field/precision |
| Nghiệp vụ | `backend/app/services/results.py` | Dự kiến tạo | roster theo period, snapshot, tính tổng/kỹ năng/chuyên cần, replay/history/locking | unit-integration/concurrency |
| API kết quả | `backend/app/api/routes/results.py`; `backend/app/api/router.py` | File đầu dự kiến tạo; router sửa | Endpoint mục2.4 và đăng ký router | auth/RBAC/tenant/OpenAPI |
| Quyền và khóa actor | `backend/app/api/dependencies.py`; `backend/app/api/routes/courses.py` | Tái sử dụng, chỉ sửa nếu cần helper chung | `tenant_access`, `lock_actor`, mẫu `authorize`; không nới quyền global | `test_auth_identity.py`; `test_results.py` |
| Course/class/teacher | `backend/app/models/course.py`; `backend/app/models/schedule.py`; `backend/app/api/routes/classrooms.py` | Tái sử dụng | Course, LearningClass, ClassTeacher, SessionTeacher; snapshot course hiện hữu | mismatch course, substitute-only denied |
| Enrollment theo thời điểm | `backend/app/models/enrollment_lifecycle.py`; `backend/app/services/enrollment_lifecycle.py` | Tái sử dụng | EnrollmentPeriod, `active_clause`; không sửa vòng đời tiền | roster trước/trong/sau bảo lưu |
| Điểm danh tham khảo | `backend/app/api/routes/attendance.py`; `backend/app/models/admissions.py` | Tái sử dụng | AttendanceSheet finalized và quy tắc denominator hiện hữu | tổng chuyên cần không làm đổi điểm |
| Idempotency/inbox | `backend/app/services/admissions.py`; `backend/app/models/admissions.py` | Tái sử dụng | `scoped`, `expected`, `replay`, `finish`, BusinessOperation; chưa gọi `notify` | retry/fingerprint/history |
| Backend test mới | `backend/tests/test_results.py` | Dự kiến tạo | Fixture nghiệp vụ, migration, quyền, tính toán, đồng thời | SQLite + PostgreSQL bắt buộc |
| Hồi quy backend | `backend/tests/test_admissions.py`; `test_courses.py`; `test_schedules.py`; `test_auth_identity.py`; `test_models.py` | Tái sử dụng/Sửa ca bị ảnh hưởng | Enrollment/class/course/assignment/schema | hồi quy theo rủi ro |
| UI mẫu điểm | `frontend/src/GradingSchemes.tsx`; `frontend/src/GradingSchemes.test.tsx` | Dự kiến tạo | Quản lý mẫu/version/trọng số, staff read-only | Vitest quyền/validation/stale |
| UI sổ điểm | `frontend/src/Results.tsx`; `frontend/src/Results.test.tsx`; `frontend/src/results.css` | Dự kiến tạo | Danh sách lớp, bảng nhập mobile/desktop, publish/lock, kết quả cá nhân | Vitest role/loading/error/bulk edit |
| Điều hướng/ngôn ngữ | `frontend/src/App.tsx`; `frontend/src/App.test.tsx`; `frontend/src/i18n.ts` | Sửa | Route `/grading-settings`, `/gradebook`, `/my-results`; guard theo role | route/tenant/support/Vi–Anh |
| Tái sử dụng UI | `frontend/src/Admissions.tsx`; `frontend/src/admissions.css`; `frontend/src/styles.css` | Tái sử dụng; chỉ sửa nếu component dùng chung thật sự cần | Attendance/MyLearning và responsive shell; không refactor ngoài phạm vi | UI regression |
| E2E | `frontend/e2e/results.spec.ts` | Dự kiến tạo | manager tạo mẫu → teacher nhập/công bố → manager khóa → student xem | Playwright DB tạm |
| Đồng hồ E2E | `backend/tests/e2e_server.py` | Sửa | test-only clock cho publication; tuyệt đối không thêm vào app production | E2E trước/sau publish |
| Tài liệu hợp đồng | `docs/results.md` | Dự kiến tạo khi triển khai | Hành vi/API/giới hạn/checklist thực tế | review tài liệu |
| Tài liệu hiện hữu | `docs/rbac.md`; `docs/data-model.md`; `docs/prd.md`; `docs/README.md`; `docs/auth-operations.md` | Sửa khi triển khai | Đồng bộ quyền/mô hình/vận hành, không chép lại kế hoạch | đối chiếu code/OpenAPI |
| Trạng thái | `docs/plans/learning-results.md`; `docs/current-state.md`; `myplan.txt` | Plan tạo; checkpoint/mốc sửa | Phạm vi, quyết định, kết quả cuối | review handoff |
| Triển khai | `compose.yaml` | Tái sử dụng nguyên trạng | Không sửa cấu hình/port của người dùng | health + endpoint dùng DB |

## 4. Thứ tự triển khai và dependency

1. Khi được duyệt, kiểm tra git status/HEAD và diff/hash các file ở mục3. Đợt auth đã được người dùng commit tại HEAD `8846d942b322926c9002acdfc940120b2097fd2d`; tài liệu kế hoạch hiện còn ở working tree. Không khảo sát lại toàn dự án hoặc ghi đè thay đổi người dùng.
2. Chốt model/FK/migration0015 và test dữ liệu cũ, decimal, unique, tenant trước khi viết route. Không backfill mẫu/sổ/điểm giả.
3. Làm mẫu đầu điểm và state machine draft → published → retired; kiểm chứng concurrent publish/clone và course scope.
4. Làm gradebook snapshot, roster theo `EnrollmentPeriod`, bulk score + history/idempotency. Chạy PostgreSQL cho row lock/concurrency trước khi mở UI.
5. Làm tính tổng/kỹ năng/coverage, publication monotonic và lock/unlock; tích hợp chuyên cần chỉ đọc.
6. Làm UI quản lý, giáo viên và học viên, route guards/Vi–Anh/responsive; sau đó E2E xuyên vai trò.
7. Chạy hồi quy theo rủi ro, lint/build, migration check; cập nhật tài liệu thực tế và trạng thái kế hoạch.
8. Chỉ khi đã được duyệt triển khai: backup/baseline, build image, migrate, update API/web, kiểm tra DB-backed endpoint/source/schema và bàn giao. Không tự đổi Jira sang Done hoặc coi test tự động là nghiệm thu người dùng.

## 5. Migration, deployment, rủi ro và bảo vệ dữ liệu

- Dự kiến revision `20260930_0015`, down revision `20260928_0014`; tên0015 hiện chưa tồn tại. Trước code phải kiểm tra lại head để tránh tạo nhánh migration nếu repository đã đổi.
- Migration chỉ thêm bảng/index/FK; không tạo scheme/gradebook/score và không sửa course snapshot, enrollment period, attendance hay dữ liệu tài chính. Dữ liệu cũ tiếp tục hoạt động khi chưa cấu hình mẫu.
- Baseline read-only lúc lập kế hoạch: Alembic0014(head),1 course,2 lớp,1 enrollment,2 class_teachers,83 sessions,0 attendance_sheets. Đây chỉ là mốc tham khảo; phải chụp lại revision/count/hash projection ngay trước deploy vì dữ liệu có thể đổi.
- Kiểm tra duplicate và tenant mismatch trước khi tạo composite unique/FK. Test upgrade từ0014 có course/class/enrollment/period/assignment/attendance, DB trống lên head, và metadata khớp schema.
- Downgrade chỉ cho DB test hoặc DB chưa có dữ liệu năm bảng mới; nếu đã có nghiệp vụ kết quả thì chủ động từ chối để tránh mất điểm. Không downgrade DB thật để thử.
- Trước deploy: pg_dump nhất quán vào vị trí backup hiện hành, thử restore/migrate trên PostgreSQL cách ly; không log secret hoặc dữ liệu cá nhân. So count/hash projection các bảng cũ sau migration và xác nhận năm bảng mới rỗng.
- Rollout dự kiến: build api/web; dừng riêng API; chạy `alembic upgrade head`; chạy lại API/web. Giữ DB/Mailpit, volume, `.env`, seed thật và `compose.yaml`.
- Sau deploy kiểm tra `/health` và ít nhất một endpoint dùng DB (`/organizations/public` hoặc endpoint result có xác thực), Alembic current/check, OpenAPI không có test helper, module frontend và hash source image. Bài học ngày2026-09-30: health nông200 không đủ chứng minh DNS DB hoạt động.
- Rủi ro chính: điểm float sai; tổng trọng số không100%; giáo viên khác lớp sửa điểm; substitute có quyền quá rộng; roster thay đổi do bảo lưu; công bố bị lùi sau khi học viên đã xem; lost update khi hai tab lưu; manager sửa nội dung; downgrade làm mất điểm. Test mục6 là điều kiện chặn bàn giao.

## 6. Lệnh kiểm thử dự kiến và tiêu chí thành công

Phiên lập kế hoạch không chạy test. Khi triển khai, từ `backend`:

~~~powershell
uv run pytest tests/test_results.py --junitxml=test-results/results-targeted.xml
uv run pytest tests/test_results.py tests/test_admissions.py tests/test_courses.py tests/test_schedules.py tests/test_auth_identity.py tests/test_models.py --junitxml=test-results/results-regression.xml
uv run ruff check app tests
~~~

Từ gốc dự án, PostgreSQL bắt buộc cho FK/lock/concurrency; fixture phải tạo schema `test_auth_<uuid>`, không chạm `public`:

~~~powershell
docker compose run --rm --no-deps -e SYNAPSE_TEST_POSTGRES=1 -v "${PWD}/backend/app:/app/app:ro" -v "${PWD}/backend/alembic:/app/alembic:ro" -v "${PWD}/backend/tests:/app/tests:ro" -v "${PWD}/backend/test-results:/app/test-results" api uv run --frozen pytest tests/test_results.py tests/test_admissions.py tests/test_courses.py tests/test_schedules.py tests/test_auth_identity.py tests/test_models.py --junitxml=test-results/results-postgres.xml
~~~

Từ `frontend`:

~~~powershell
npm.cmd run test -- Results.test.tsx GradingSchemes.test.tsx App.test.tsx
npm.cmd run test
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e -- e2e/results.spec.ts e2e/admissions.spec.ts
~~~

Cuối vòng chạy `git diff --check`. Không chạy full backend sau mỗi chỉnh sửa; chỉ mở rộng khi dependency thay đổi hoặc test mục tiêu phát hiện rủi ro.

Ma trận bắt buộc:

- Tính toán: 0, điểm tối đa, số lẻ hai chữ số, vượt biên, nhiều trọng số, làm tròn, coverage thiếu, thiếu điểm không thành0, breakdown kỹ năng khớp tổng.
- Quyền/tenant: manager cấu hình/lock nhưng không sửa điểm; staff chỉ xem; đúng ClassTeacher được nhập; teacher khác/substitute-only bị chặn; student chỉ bản thân đã công bố; Root cần support đúng tenant.
- Thời điểm: enrollment trước/trong/sau bảo lưu, học viên vào lớp muộn, assessed_at đổi trước điểm nhưng bị khóa sau điểm, publish tương lai/trước/sau mốc, không lùi sau hiệu lực.
- Transaction/concurrency: retry cùng key, key trùng payload khác, hai tab cùng version, publish/score/lock đồng thời, rollback toàn bộ khi roster sai hoặc một điểm vượt max.
- Migration: dữ liệu0014 giữ count/hash projection; constraints cả SQLite/PostgreSQL; downgrade/re-upgrade DB trống và từ chối downgrade khi có điểm.
- UI/E2E: loading/empty/error/stale version/double submit; bảng mobile không mất tên học viên/hành động; bàn phím; Việt–Anh; manager → teacher → student; auth/attendance/admissions không hồi quy.

Tiêu chí thành công: mọi lệnh đã chọn chạy có test thực sự được collect,0 lỗi; PostgreSQL concurrency/FK đạt; lint/build đạt; E2E xuyên vai trò đạt; image/schema/source/baseline sau deploy khớp; chưa đánh dấu người dùng nghiệm thu.

## 7. Checklist nghiệm thu thủ công theo vai trò

- Quản lý/Root hỗ trợ: tạo mẫu nháp, tổng trọng số sai bị chặn; công bố rồi clone phiên bản mới; không sửa được điểm; xem sổ, khóa/mở khóa có lý do và lịch sử đúng tenant.
- Giáo vụ: xem mẫu/sổ/tổng hợp/chuyên cần nhưng mọi nút sửa điểm, publish, lock đều không có hoặc bị403 nếu gọi API trực tiếp.
- Giáo viên phụ trách: chỉ thấy lớp được phân công; khởi tạo sổ từ đúng mẫu; nhập điểm lẻ/nhận xét; lỗi một hàng không lưu nửa bảng; hẹn công bố; sửa sau công bố đòi lý do; bị chặn khi khóa.
- Giáo viên thay một buổi hoặc giáo viên lớp khác: không được đọc/sửa sổ lớp ngoài quyền; thu hồi assignment có hiệu lực ở request kế tiếp.
- Học viên: trước giờ công bố không thấy điểm; sau giờ chỉ thấy bản thân, tổng/coverage/kỹ năng/nhận xét và chuyên cần; bảo lưu sau bài không làm mất điểm cũ; không đọc được lý do sửa/mở khóa nội bộ.
- Mọi vai trò: refresh/hai tab/mạng chậm không tạo trùng hoặc ghi đè im lặng; tenant/support hết hạn bị chặn; Việt–Anh, desktop/mobile, bàn phím, light/dark vẫn dùng được.
- Vận hành: restart container rồi kiểm tra cả health và endpoint dùng DB; DB/Mailpit/volume/dữ liệu giữ nguyên; không có test helper trong OpenAPI production.

## 8. Những quyết định còn cần người dùng trả lời

Không có câu hỏi bắt buộc trước khi duyệt kế hoạch. Kế hoạch dùng các quyết định đã có trong PRD/RBAC: quản lý cấu hình và khóa, giáo viên phụ trách là người duy nhất sửa nội dung điểm, giáo vụ chỉ xem, học viên chỉ xem kết quả đã công bố.

Các mặc định thiết kế để tránh mở rộng phạm vi: điểm từng đầu mục có max linh hoạt nhưng tổng chuẩn hóa100; trọng số dùng basis point; thiếu điểm không tự thành0; chưa tự xét đạt/rớt hoặc hoàn thành enrollment; chưa gửi notification hẹn giờ. Nếu muốn thay một trong các mặc định này, cần chốt trước khi duyệt triển khai vì sẽ đổi schema/test hoặc cần background worker.

Việc người dùng nói đã test khả năng tích hợp UI được ghi nhận là xác nhận tích hợp; chưa tự đổi checkbox nghiệm thu toàn bộ auth cho thiết bị thật/email. Trạng thái này không chặn đợt kết quả học tập.

## 9. Trạng thái thực thi

- [x] Đọc `docs/current-state.md`, kiểm tra git status/HEAD và trạng thái đợt trước.
- [x] Xác minh file/symbol phụ thuộc và revision0014; không đọc lại toàn bộ myplan.
- [x] Đọc baseline DB liên quan bằng truy vấn count không chứa dữ liệu cá nhân.
- [x] Lưu kế hoạch backend/UI/test/migration/checklist.
- [x] Người dùng duyệt triển khai.
- [x] Code/test/deploy đợt kết quả học tập.
- [ ] Người dùng nghiệm thu.

Kết quả thực tế ngày2026-09-30:

- API mẫu đặt dưới `/api/v1/results/schemes` cùng module kết quả, thay vì đường dẫn `/api/v1/grading-schemes` dự kiến lúc lập kế hoạch; [hợp đồng thực tế](../results.md) ghi đầy đủ endpoint.
- Backend: `test_results.py` SQLite/PostgreSQL 18 đạt, 2 skip concurrency trên SQLite; có thử singleton khi tạo sổ đồng thời, roster, Decimal, bản nháp/công bố/khóa, lịch sử sửa sau công bố, rollback và từ chối downgrade có dữ liệu. Hồi quy chọn lọc `test_results`, admissions, courses, schedules, auth identity, models thu thập253 ca:224 đạt,27 skip,2 assertion migration cũ ghim head0014; đã sửa và chạy lại đúng2 ca trên SQLite/PostgreSQL đạt4/4. Sau tối ưu truy vấn chuyên cần và lưu lý do sửa điểm, ca mục tiêu được chạy lại đạt. Ruff `app tests` đạt.
- Frontend: 101/101 Vitest đạt trên15 file; sau chỉnh hiển thị kết quả cá nhân và bắt buộc lý do trên form, chạy lại3 ca liên quan đạt. ESLint và production build đạt sau chỉnh sửa. E2E Chromium cô lập `results.spec.ts` và `admissions.spec.ts` 2/2 đạt, gồm manager → teacher → student → lock, UI mobile và hồi quy tuyến tuyển sinh/thu phí/điểm danh.
- PostgreSQL rehearsal từ `pre0015.dump`: upgrade/check/downgrade/reupgrade0015 đạt;51 bảng cũ cùng count/hash,5 bảng mới rỗng. DB thật chụp lại baseline0014 ngay trước rollout (1 course,2 lớp,1 enrollment,83 buổi; kiểm tra trùng/lệch tenant đều0), pg_dump kiểm tra đọc được; migrate0015 rồi Alembic check và so lại51 bảng cũ đều khớp,5 bảng mới rỗng.
- Image API/web đã build và cập nhật riêng. Health, `/organizations/public` dùng DB, OpenAPI, web, Mailpit HTTP200; OpenAPI có14 path `/results`, không có helper test.82 file nguồn Python API và52 file frontend trong image khớp hash workspace. DB container `18c0b2202fed` và Mailpit `e1376460d909` giữ nguyên, volume `synapselms_postgres_data` không xóa; `compose.yaml`, `.env`, seed thật không sửa. Hai DB restore thử nghiệm đã dọn; backup `.local-backups/pre0015.dump` giữ lại. Không stage/commit hoặc chuyển Jira Done.
- Giới hạn: không tự chạy notification theo giờ, không xuất PDF/Excel, pass/fail, chứng chỉ, AI/streak/theme. Người dùng cần tự nghiệm thu checklist mục7; test tự động không thay thế bước đó.
