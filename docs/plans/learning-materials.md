# Đợt đề xuất: học liệu từ thư viện đến lớp học

Trạng thái: **đã code, test và deploy 0016 ngày 2026-10-01; chờ người dùng nghiệm thu thủ công**. Người dùng đã duyệt triển khai sau bản kế hoạch ngày 2026-09-30 trên HEAD `8846d94`. 0015 và 0014 được test sơ pass trước đó nhưng chưa xác nhận nghiệm thu đầy đủ; theo dõi riêng. Luồng nền tại [quản lý giáo trình và tài liệu tham khảo](../workflows/learning-materials.md), vận hành tại [học liệu 0016](../materials-operations.md).

## 1. Mục tiêu và phạm vi

Hoàn thành một luồng học liệu dùng được xuyên vai trò: giáo vụ/quản lý tạo thư viện và giáo trình theo phiên bản; giáo viên đưa tài liệu của mình vào lớp hoặc đề xuất dùng chung; người có quyền phát tài liệu theo lớp/buổi; học viên được cấp quyền xem/đọc/nghe/tải; thu hồi có hiệu lực tại request kế tiếp. Gồm MAT-01–07: tenant policy, lưu file riêng tư, kiểm tra file và quota, duyệt, giáo trình/chương/bài, gắn khóa/lớp/buổi, công bố, thông báo trong ứng dụng, phiên bản/thu hồi và backup/restore.

Không làm DOCX/PPTX/video upload, chuyển đổi nội dung, tìm kiếm bên trong file, theo dõi hoàn thành đọc/nghe, bài tập/đề thi, AI sinh bài, streak/theme, thư viện sách vật lý, DRM hay signed URL. Không sửa điểm, học phí, enrollment hoặc tự tính hoàn thành khóa. File/link cũ không được tạo mặc định.

Điểm kết thúc: một tài liệu được tạo/duyệt, gắn vào một buổi và công bố; đúng học viên đọc được phiên bản đã cấp, người ngoài quyền bị chặn; sửa bản gốc không âm thầm thay bản lớp; thu hồi chặn cả xem/tải và còn lịch sử; restore khôi phục cả metadata lẫn file. UI có luồng tương ứng trên desktop/mobile.

## 2. Quy tắc nghiệp vụ, quyền, dữ liệu và API

- Quản lý/Root trong support session đúng tenant quản trị thư viện, giáo trình, quota và thu hồi. Giáo vụ biên mục, duyệt đề xuất và gắn khóa/lớp. Giáo viên phụ trách lớp tạo/phát tài liệu riêng, đề xuất vào thư viện chung; giáo viên dạy thay chỉ có quyền theo buổi được phân công. Học viên chỉ xem bản đã công bố, đúng enrollment/grant. Mọi API danh sách, tìm kiếm, preview, audio range, download và chi tiết đều kiểm tra quyền server side; không trả object key hoặc đường dẫn file thật.
- Nội dung `DRAFT → PUBLISHED → ARCHIVED/WITHDRAWN`; đề xuất duyệt `PENDING → APPROVED/REJECTED`; file `PENDING_CHECK → READY/REJECTED`. Không công bố file chưa `READY`. Link HTTPS chỉ lưu URL đã kiểm tra cú pháp, không cho server tải về. File chỉ chấp nhận PDF, PNG/JPEG, MP3; giới hạn dung lượng/quota theo cấu hình tenant và giới hạn cứng phía server. Kiểm tra MIME/chữ ký, kích thước, tên tải về an toàn và mã độc; hỏng dịch vụ kiểm tra thì giữ pending và chặn phát hành. Cần chọn cơ chế quét trước khi chốt triển khai file.
- Bản đã công bố là bất biến. Sửa nội dung hoặc upload lại tạo `MaterialVersion` mới; gắn lớp/buổi ghim version, không cập nhật tự động. `ARCHIVED` chặn gắn mới nhưng grant cũ còn hiệu lực; `WITHDRAWN` chặn mọi truy cập thường và ghi lý do/audit. Tài liệu đáp án có audience `teachers`, không dùng bản học viên cộng nút ẩn UI.
- Giáo trình có phiên bản bất biến, chương/bài có thứ tự, liên kết version học liệu. Khóa có giáo trình chính và bổ trợ; khi tạo lớp, chụp phiên bản đang áp dụng; lớp cũ chỉ đổi qua thao tác có lý do. Gắn vào khóa không tự cấp quyền cho người xem catalog công khai.
- Công bố theo giờ server. Grant theo enrollment/version/lớp được ghi rõ khi đến giờ, bảo đảm idempotent khi retry và không cần worker để học viên thấy tài liệu đúng giờ; thông báo trong app dùng outbox/job chống trùng. Bảo lưu: giữ tài liệu đã cấp trước ngày bắt đầu, không cấp nội dung mới trong thời gian bảo lưu; hủy/chờ duyệt không cấp; chuyển tenant không mang file theo. Cần đối chiếu policy thực tế của `EnrollmentPeriod` trước khi code.
- Dữ liệu dự kiến: `materials`, `material_versions`, `material_review_requests`, `curricula`, `curriculum_versions`, `curriculum_units`, `curriculum_materials`, `course_curricula`, `class_curricula`, `material_assignments`, `student_material_grants` và metadata blob/quota nếu cần. Dùng FK ghép `(organization_id, id)`, unique version/idempotency key, audit actor/reason, index theo tenant/status/scope. File ở volume riêng tư, không nằm trong DB hay web public.
- Nhóm API dự kiến dưới `/api/v1/materials`: thư viện/list/detail/version/upload/finalize/review/publish/withdraw, giáo trình/version/units/course-class binding, class/session assignments, `mine`, preview/download. Thiết kế endpoint cụ thể và DTO whitelist khi triển khai; upload có transaction finalize và dọn file mồ côi, không nhân quota/version khi retry. Stream/Range đều xác thực lại.

## 3. Bản đồ thay đổi đã xác minh

Các đường dẫn ghi **dự kiến tạo** hiện chưa tồn tại tại thời điểm khảo sát. Bảng là bản đồ khởi đầu, không cản mở dependency liên quan sau khi duyệt.

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol hoặc trách nhiệm | Test tương ứng |
|---|---|---|---|---|
| Migration 0016 | `backend/alembic/versions/20261001_0016_learning_materials.py` | Đã tạo | Schema/FK/index, upgrade không backfill, downgrade bảo vệ dữ liệu | `backend/tests/test_materials.py` + migration PostgreSQL |
| Model/registration | `backend/app/models/materials.py`; `backend/app/models/__init__.py` | Dự kiến tạo; sửa | Model mới; đăng ký metadata Alembic | `test_models.py`, `test_materials.py` |
| Quyền, storage, nghiệp vụ | `backend/app/services/materials.py`; `backend/app/core/config.py` | Dự kiến tạo; sửa | Scope/role, phiên bản, grant, quota, file private/finalize | `test_materials.py` |
| API/DTO | `backend/app/api/material_schemas.py`; `backend/app/api/routes/materials.py`; `backend/app/api/router.py` | Dự kiến tạo; dự kiến tạo; sửa | Request/response whitelist và các endpoint học liệu | `test_materials.py` |
| Khóa, lớp, buổi, enrollment | `backend/app/models/course.py`; `backend/app/models/classroom.py`; `backend/app/models/schedule.py`; `backend/app/models/enrollment_lifecycle.py`; `backend/app/services/enrollment_lifecycle.py` | Tái sử dụng, chỉ sửa nếu cần liên kết | `Course`, `LearningClass`, `ClassSession`, `ClassTeacher`, `EnrollmentPeriod`/`active_clause` | `test_courses.py`, `test_classrooms.py`, `test_schedules.py`, `test_admissions.py` |
| Thông báo | `backend/app/models/admissions.py`; `backend/app/api/routes/notifications.py` | Tái sử dụng, sửa nếu cần outbox | `Notification`, `inbox`; chống trùng và thời điểm phát | `test_materials.py`, test thông báo bị ảnh hưởng |
| UI quản trị/lớp/học viên | `frontend/src/Materials.tsx`; `frontend/src/materials.css`; `frontend/src/App.tsx`; `frontend/src/i18n.ts`; `frontend/src/api.ts` | Dự kiến tạo; dự kiến tạo; sửa; sửa; tái sử dụng/sửa nếu cần upload | Thư viện, giáo trình, phát tài liệu, tài liệu của tôi, navigation, VI/EN, client download | `frontend/src/Materials.test.tsx` (dự kiến tạo) |
| E2E | `frontend/e2e/materials.spec.ts` | **Dự kiến tạo** | Giáo vụ/giáo viên → học viên → thu hồi, mobile và quyền | Playwright |
| Hạ tầng và tài liệu | `compose.yaml`; `backend/Dockerfile`; `docs/workflows/learning-materials.md`; `docs/current-state.md`; `docs/README.md` | Sửa chỉ khi triển khai cần; giữ mọi thay đổi hiện có | Volume file riêng/scan service nếu chốt, hướng dẫn backup/restore và checkpoint | restore rehearsal, health/OpenAPI |

## 4. Trình tự triển khai

1. Sau khi người dùng duyệt kế hoạch, kiểm tra diff/status/schema/Docker và các file trên có đổi kể từ khảo sát; chốt giải pháp quét, hạn mức và policy truy cập sau bảo lưu. Không khảo sát lại toàn dự án.
2. MAT-01/02: migration + model + private storage + file validation/finalize, tenant/FK/quota/concurrency; rehearsal upgrade/rollback trên bản sao DB và file. File không an toàn không thể phát hành.
3. MAT-03/04: thư viện, duyệt, version và giáo trình gắn khóa/lớp; UI quản trị; khóa snapshot đúng phiên bản.
4. MAT-05/06: phân phối lớp/buổi, phát theo giờ, notification idempotent, grant theo enrollment, UI giáo viên/học viên, preview/stream/range/download.
5. MAT-07: archive/withdraw/audit, dọn orphan an toàn, backup/restore cả DB và volume; E2E xuyên vai trò, hồi quy theo rủi ro; chốt tài liệu. Chỉ deploy sau khi có bằng chứng migration/restore và các ca quyền đạt.

## 5. Migration, deployment, rủi ro dữ liệu

- 0016 chỉ thêm bảng/constraint/index và không seed/backfill dữ liệu thật. Trước triển khai chụp count/hash bảng cũ, kiểm tra duplicate/tenant mismatch, `pg_dump` và backup file volume. Rehearsal trên bản sao gồm upgrade/check/downgrade/reupgrade DB rỗng và DB có dữ liệu; downgrade DB đã có học liệu cần từ chối để không mất dữ liệu.
- `compose.yaml` hiện có volume DB `postgres_data` nhưng **chưa có volume học liệu**. Dự kiến thêm volume private cho API và cơ chế quét phù hợp; không thay đổi hoặc xóa volume DB/Mailpit, không ghi đè chỉnh sửa compose của người dùng. Backup/restore phải ghép DB snapshot với file snapshot cùng mốc; kiểm tra checksum và mở lại version đã cấp.
- Transaction DB không bao trùm filesystem: upload vào vùng tạm, kiểm tra, finalize theo key bất biến, ghi trạng thái và dọn orphan bằng job an toàn. Thử retry, hai upload đồng thời chạm quota, storage/scan lỗi, path traversal, MIME giả và stream bị thu hồi giữa các request. Giới hạn tải ở reverse proxy/API để tránh chiếm tài nguyên.
- Sau deploy kiểm tra revision head, metadata/schema, API/web health/OpenAPI, truy cập DB thật, count/hash baseline và file test cô lập; giữ backup cho rollback. Không tạo học liệu mẫu trong tenant thật. Jira chỉ thay đổi nếu người dùng duyệt phạm vi quản lý Jira riêng.

## 6. Kiểm thử dự kiến

Chạy tại `backend/`: `uv run pytest tests/test_materials.py tests/test_models.py tests/test_courses.py tests/test_classrooms.py tests/test_schedules.py tests/test_admissions.py -q` (chọn ca hồi quy liên quan khi phạm vi sửa thực tế đã rõ); `uv run ruff check app tests`; `uv run alembic check`. Chạy cùng ca quyền/FK/concurrency trên PostgreSQL qua cấu hình fixture hiện có; rehearsal upgrade/downgrade bằng DB restore, không dùng DB thật để thử downgrade.

Chạy tại `frontend/`: `npm test -- src/Materials.test.tsx` (và test navigation/i18n bị ảnh hưởng), `npm run lint`, `npm run build`, `npx playwright test e2e/materials.spec.ts`. Kiểm tra manual mobile/keyboard/VI-EN, PDF/ảnh/audio và Range sau đăng nhập. Không chạy lại toàn suite nếu dependency không đổi.

Đạt khi test được collect thật, 0 lỗi; ca tenant/role/enrollment/withdraw/version/quota/concurrency/scan failure/restore đạt; lint/build/E2E đạt; schema và baseline DB cũ không đổi ngoài migration; API/web chạy với volume file bền vững sau restart. Báo cáo test nêu thời điểm và phạm vi, không tái sử dụng kết quả cũ sau khi code liên quan đổi.

## 7. Checklist nghiệm thu thủ công theo vai trò

- Quản lý/Root hỗ trợ đúng tenant: cấu hình giới hạn, duyệt/từ chối đề xuất, xuất bản phiên bản giáo trình, thu hồi có lý do; Root thiếu support đúng tenant bị chặn.
- Giáo vụ: tạo giáo trình/chương/bài, gắn khóa/lớp, duyệt đề xuất; phiên bản lớp đang học giữ nguyên khi giáo trình phát hành bản mới; không truy cập tenant khác.
- Giáo viên phụ trách: tạo tài liệu lớp, phát cho buổi hoặc hẹn giờ, nghe/xem bản giáo viên; giáo viên dạy thay chỉ trong buổi được phân công; không sửa tài liệu của giáo viên khác.
- Học viên: trước giờ công bố không thấy; sau giờ đọc PDF/ảnh, nghe MP3, mở link, tải đúng file và đúng version; không thấy đáp án; bảo lưu giữ bản đã cấp nhưng không nhận tài liệu mới; hủy/chưa duyệt/khác lớp/tenant bị chặn.
- Vận hành: thử file sai loại/quá hạn mức/MIME giả/scan lỗi, retry upload, hai tab, thu hồi rồi refresh/Range; restart API/web và khôi phục bản sao DB+volume, file vẫn đúng checksum; DB/Mailpit và dữ liệu cũ nguyên vẹn.

## 8. Quyết định cần người dùng trả lời

Trước khi triển khai file upload cần chốt **dịch vụ quét mã độc** sẽ vận hành trong Docker hay chỉ phát hành pha đầu với HTTPS link/metadata; nếu chưa có scanner, file luôn `PENDING_CHECK` và không được công bố. Đề xuất dùng scanner nội bộ và giữ nguyên nguyên tắc fail closed. Hạn mức đề xuất ban đầu: PDF/ảnh 25 MB, MP3 50 MB, 2 GB/tenant; quota quản lý có thể hạ, không vượt trần server. Đề xuất giữ quyền đọc bản đã cấp khi bảo lưu, nhưng thu hồi bản nguồn luôn chặn. Nếu người dùng muốn chính sách khác, cần chốt trước lúc code vì ảnh hưởng schema, storage và test. Không cần quyết định này để duyệt **kế hoạch**.

## 9. Trạng thái

- [x] Đọc checkpoint, đối chiếu git status và Docker hiện tại; chỉ khảo sát tài liệu/code liên quan.
- [x] Xác minh đường dẫn hiện hữu, ghi rõ đường dẫn dự kiến tạo.
- [x] Lưu kế hoạch; không code, deploy, đổi Jira hoặc coi 0015 đã nghiệm thu.
- [x] Người dùng duyệt phạm vi/điều kiện triển khai; dùng ClamAV nội bộ, file fail closed.
- [x] Code, kiểm thử tự động và deploy 0016; xem bằng chứng bên dưới.
- [ ] Người dùng nghiệm thu thủ công theo mục 7.

## 10. Bàn giao triển khai 2026-10-01

- Code: 12 bảng mới, không backfill/seed; file trong volume riêng tư, ClamAV, quota/scan fail closed, version/grant/thu hồi/audit; API và UI theo MAT-01–07. `material-gc` chạy mỗi ngày, chỉ xóa file mồ côi quá 24 giờ. Không thay đổi `.env`, stage/commit hoặc Jira.
- Test: `tests/test_materials.py` đạt **13 pass, 1 skip** trên SQLite + PostgreSQL; skip là ca khóa dòng quota chỉ áp dụng PostgreSQL, nơi ca đó đã đạt với hai upload đồng thời. Có ca quyền khi giáo viên bị gỡ phân công. Hồi quy `test_materials.py test_classrooms.py test_admissions.py` trên SQLite đạt **55 pass, 15 skip** trước hai ca mới; các ca mới đạt trong vòng 13 pass. UI **104/104**, lint/build đạt sau thay đổi dropdown giáo trình; E2E Playwright 1 test xuyên vai trò (kể cả viewport mobile) đạt trước thay đổi dropdown này. Migration đã diễn tập trên bản DB restore: nâng/hạ/nâng, Alembic check, 56 bảng cũ cùng hash và guard từ chối downgrade khi có dữ liệu học liệu.
- Deploy: `.local-backups/pre0016-final.dump` và baseline `.local-backups/pre0016-live-check.json` trước nâng; DB thật lên `20261001_0016`, Alembic check sạch, **56 bảng cũ không lệch count/hash**, 12 bảng mới rỗng. API/web và `material-gc` đã cập nhật; DB/Mailpit giữ container/volume cũ. API public, OpenAPI (26 đường dẫn học liệu), web, Mailpit HTTP 200; ClamAV healthy và INSTREAM trả `ready` cho file tạm sạch. Không tạo học liệu trong tenant thật.
- Giới hạn: người dùng chưa nghiệm thu mục 7. Thử restore end-to-end file thật trên volume test và thao tác PDF/MP3 trên thiết bị thật nằm trong checklist thủ công; rehearsal DB đã thực hiện. 0014/0015 vẫn chưa được xác nhận nghiệm thu đầy đủ.

Đề cử model: GPT gpt-6-astra — high, vì đợt này liên quan tenant/RBAC, file private, version bất biến, concurrency và phục hồi dữ liệu.
