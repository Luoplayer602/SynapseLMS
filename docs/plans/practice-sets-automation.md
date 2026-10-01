# Kế hoạch: bộ đề AI theo lịch, Root làm thử mẫu để duyệt chất lượng

Trạng thái 2026-10-01: **chỉ lập kế hoạch, chưa sửa code/migration/deploy/Jira**. Bắt đầu từ checkpoint [hiện tại](../current-state.md) và cụm AI 0017 đã deploy; người dùng chưa nghiệm thu toàn cụm. Working tree hiện có thay đổi của đợt 0017 và `.gitignore` có từ trước, phải giữ nguyên. DB thực tế có 2 câu hỏi cũ, 0 lượt nộp và 0 ngày streak; không coi dữ liệu này là seed hay tự chỉnh sửa. Đợt này thay riêng luồng bài luyện, không mở rộng gợi ý lớp/tóm tắt/tiếng nói.

## 1. Mục tiêu, phạm vi, điểm kết thúc

Thay nút sinh **một câu rồi duyệt từng câu** bằng bộ đề 10–20 câu tạo trong job bền vững theo lịch. Root làm thử một bộ đề mẫu ở giao diện mô phỏng học viên, thấy điểm/đáp án/giải thích và nguồn của từng câu, rồi duyệt **cấu hình sinh** gồm khóa học, ngôn ngữ, prompt version, route/provider, blueprint và phiên bản nguồn. Các job theo lịch dùng đúng cấu hình đã duyệt; bộ đề chỉ tự phát hành nếu toàn bộ câu qua validator và kiểm tra trùng lặp. Đổi prompt, model/route, blueprint hoặc nguồn liên quan làm approval hết hiệu lực; cần Root thử mẫu mới. Không bắt giáo viên/quản lý duyệt từng câu; họ có thể tạm dừng lịch và báo/ẩn bộ đề sai. Root có nút thu hồi approval/đề đã phát hành.

Học viên thấy một bộ đề đúng khóa/lớp và cửa sổ hiệu lực, làm tiếp dở, nộp cả bộ một lần và nhận điểm do server chấm. Không lộ đáp án trước khi nộp. Kết quả bài luyện không ghi vào gradebook. Điểm kết thúc: Root duyệt mẫu một lần; job theo lịch tạo bộ đề 10–20 câu không cần thao tác duyệt hằng ngày, không phát hành nửa bộ hay output sai; học viên nộp idempotent và streak/theme đúng quy tắc được chốt; tắt AI hoặc hết quota không xóa đề đã phát hành.

Ngoài phạm vi: chấm tự luận/phát âm, nhập đề theo file mẫu, OCR/trích nội dung PDF/audio, tự điều chỉnh trình độ cá nhân bằng dữ liệu nhạy cảm, sinh vô hạn khi không có lịch, tự sửa kết quả học tập. Không dùng nội dung file học liệu chưa có pipeline trích xuất và kiểm quyền. Nguồn đã xác minh hiện có là `Course.name`, `Course.objectives`, các mức của khóa; chỉ dùng metadata học liệu đã công bố nếu được xác minh đủ quyền và có ích, không giả vờ đã đọc nội dung PDF.

## 2. Quy tắc nghiệp vụ, quyền, dữ liệu/API

- **Blueprint và lịch:** quản lý chọn khóa đã `published`, lớp hoặc toàn khóa, ngôn ngữ, 10–20 câu (mặc định 10), chủ đề/mục tiêu từ khóa, giờ mở đề hằng ngày, hạn làm và timezone tenant. Cấu hình lịch có version, trạng thái bật/tắt, `next_run_at`, giới hạn một job/bộ cho mỗi ngày; chỉ sinh khi AI tenant/practice và route/provider còn bật, prompt tương ứng đã publish và approval Root còn hợp lệ. Worker tạo trước kho dự phòng tối đa ba ngày theo cùng blueprint đã duyệt, mỗi ngày chỉ mở một bộ đúng lịch; không gọi model vào lúc học viên mở đề. Không gửi PII học viên cho model.
- **Root QA:** job thử mẫu dùng cùng pipeline/provider như production nhưng đánh dấu `sample`, có chi phí và quota riêng; Root làm toàn bộ đề ở chế độ preview, xem giải thích/nguồn sau nộp, đánh dấu câu yếu và lý do. Preview không tạo `PracticeAttempt`, streak, theme hay quyền học viên. Root chỉ duyệt blueprint sau khi hoàn thành preview và xác nhận. Approval gắn fingerprint của khóa/blueprint/locale/prompt/route/model/nguồn; không suy diễn một lần duyệt bảo đảm vĩnh viễn khi đầu vào đổi. Audit mọi duyệt/thu hồi.
- **Sinh bộ:** worker nhận job qua DB, lease/heartbeat/retry có giới hạn. Vì 20 câu có thể vượt output token một lời gọi, sinh theo nhiều lô nhỏ (ví dụ 4–5 câu) rồi ghép, loại câu trùng, validate 10–20 câu trong một transaction; vượt quota, timeout, provider lỗi, dữ liệu nguồn thiếu hoặc số câu hợp lệ không đủ thì job `failed`, không phát hành phần còn lại. Retry idempotent, có số lượt/token/chi phí ước tính nếu đã cấu hình giá, không gọi vô hạn. Job có thể mất phút; UI hiện queued/running/completed/failed và lý do an toàn, không giữ request HTTP mở. Một khóa/kỳ/language không nhân đôi đề khi scheduler/worker chạy song song.
- **Validator ngoài prompt:** JSON schema bất biến, đúng số câu, 2–4 lựa chọn, đúng một đáp án, giải thích phù hợp đáp án, độ dài/độ tuổi/ngôn ngữ, tham chiếu mục tiêu được cấp, không lặp stem/đáp án hoặc tương đồng cao với các bộ gần đây. Theo dõi độ phủ mục tiêu; nếu mục tiêu khóa học quá ít để sinh đề mới hằng ngày, dừng lịch và báo thiếu nguồn thay vì lặp/bịa. Không thể chứng minh hoàn toàn tính đúng bằng validator: Root duyệt mẫu, kiểm tra hậu phát hành và nút ẩn/thu hồi vẫn cần. Câu nghi vấn hoặc thiếu nguồn làm **cả bộ** không phát hành. Học viên không thấy đáp án của đề khác qua API.
- **Đề và nộp:** bộ đề có version/snapshot 10–20 câu bất biến, nguồn/prompt/model/AI run và cửa sổ hiệu lực. Học viên enrollment period đang hiệu lực mới mở/nộp; bảo lưu/hủy/thu hồi quyền được kiểm tra lại khi mở và khi nộp. Nếu học nhiều khóa, server chọn **một bộ trong ngày cho mỗi học viên** theo vòng luân phiên ổn định giữa các khóa đủ quyền, tránh bắt làm nhiều bộ để giữ streak; câu/đáp án có thể hoán vị ổn định theo học viên mà server vẫn chấm đúng. Lưu tiến độ nháp riêng, nộp cả bộ bằng idempotency key, transaction và row lock/unique để tránh chấm hai lần. Chấm điểm trên server, hiện giải thích sau nộp. Một học viên chỉ có một kết quả chính thức cho một bộ; lịch sử vẫn đọc được sau khi đề ẩn theo quyền.
- **Streak/theme:** một bộ đề mới mở mỗi ngày; chỉ nộp **trọn bộ** trong ngày địa phương của trung tâm mới tính một ngày streak, không đặt ngưỡng điểm. Làm nhiều bộ/retry không cộng ngày thứ hai. Giữ ngày, timezone và grant cũ, không tính lại lịch sử. Kho dự phòng giúp không mất ngày khi provider tạm lỗi; nếu hết đề thì báo rõ vận hành, không cấp streak giả. Bài cũ 0017 tiếp tục đọc/nộp theo luồng cũ trong giai đoạn chuyển tiếp hoặc được ẩn có kiểm soát; không tự xóa 2 câu hiện có.
- **Quyền:** Root cấu hình/QA/duyệt/thu hồi và xem usage toàn hệ thống; quản lý tenant đặt lịch trong giới hạn Root, xem job/bộ của tenant và tạm dừng; giáo viên phụ trách xem đề lớp, báo lỗi/ẩn khẩn cấp; học viên chỉ thấy/nộp đề của enrollment hợp lệ. Mọi endpoint kiểm tenant/server-side; không cho Root QA giả làm học viên thật.

API dự kiến: `POST/GET /api/v1/practice/blueprints`, `POST /api/v1/practice/blueprints/{id}/sample`, `GET /api/v1/practice/jobs/{id}`, `POST /api/v1/ai/practice-approvals/{sample_id}`, `POST /api/v1/ai/practice-approvals/{id}/revoke`, `GET /api/v1/practice/sets/mine`, `GET /api/v1/practice/sets/{id}`, `PUT /api/v1/practice/sets/{id}/draft`, `POST /api/v1/practice/sets/{id}/submit`. Tên DTO/URL cuối cùng rà soát khi triển khai. API câu đơn cũ được giữ để không phá dữ liệu và client đang dùng cho đến khi chuyển UI hoàn tất.

### System prompt đề xuất cho bản mẫu Root thử

Phần dưới là **nội dung Root có thể sửa và version trong Prompt Studio**; policy bắt buộc về quyền, đầu vào được phép, schema và validator vẫn ở server. Server truyền `locale`, mục tiêu/level đã lọc, số câu của lô, danh sách stem cần tránh và source ID hợp lệ qua payload; không ghép dữ liệu cá nhân vào prompt.

```text
Bạn là người biên soạn bài luyện ngắn cho học viên SynapseLMS. Hãy tạo đúng số câu hỏi trắc nghiệm của lô được yêu cầu, dùng ngôn ngữ {locale} và chỉ dựa trên mục tiêu, trình độ, chủ đề và source ID đã được cung cấp. Mỗi câu kiểm tra một ý rõ ràng; phân bố mức độ từ nhận biết đến vận dụng vừa sức, không hỏi kiến thức ngoài nguồn. Viết câu hỏi ngắn, tự nhiên, phù hợp học viên nhỏ tuổi. Tạo 2–4 lựa chọn khác nhau, chỉ một đáp án đúng; các đáp án nhiễu phải hợp lý nhưng không đánh đố. Phần giải thích nêu vì sao đáp án đúng dựa trên nguồn, không tiết lộ dữ liệu riêng tư hoặc đưa lời khuyên ngoài phạm vi học tập. Tránh lặp câu hỏi, đáp án và dạng diễn đạt với danh sách đã dùng. Nếu nguồn không đủ để tạo câu đúng, báo thiếu dữ liệu thay vì bịa. Chỉ trả JSON theo schema do server cung cấp, không thêm văn bản ngoài JSON.
```

Prompt không tự cho phép model quyết định `correct_index` hợp lệ bằng lời văn; server bắt buộc kiểm schema/ngữ nghĩa và Root thử đề mẫu. Nếu model không đáp ứng format qua nhiều lô, không được auto-publish.

## 3. Bản đồ thay đổi (file đã xác minh)

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol/trách nhiệm | Test |
|---|---|---|---|---|
| Schema bộ đề, job, approval | `backend/alembic/versions/20261001_0018_practice_sets.py`; `backend/app/models/practice.py`; `backend/app/models/ai.py`; `backend/app/models/__init__.py` | Migration dự kiến tạo; còn lại sửa | Bảng blueprint/job/set/set-attempt/QA approval, FK tenant/unique kỳ, `set_id` nullable trên câu cũ; giữ dữ liệu 0017 | `backend/tests/test_practice_sets.py` dự kiến tạo; migration rehearsal |
| Sinh lô và lịch bền vững | `backend/app/services/practice_sets.py`; `backend/app/practice_worker.py`; `backend/app/services/ai/providers.py`; `backend/app/services/ai/routing.py`; `backend/app/services/ai/prompts.py`; `compose.yaml` | Hai file dự kiến tạo; còn lại sửa | Scheduler/worker lease, chia lô, quota, validator và fingerprint approval; worker có key secret như API | `backend/tests/test_practice_sets.py`, `test_ai_config.py` |
| API, quyền và nộp | `backend/app/api/routes/practice.py`; `backend/app/api/routes/ai.py`; `backend/app/api/practice_schemas.py`; `backend/app/services/practice.py` | Sửa/tái sử dụng | Root QA, quản lý lịch, học viên mở/lưu nháp/nộp bộ, chấm và streak, giữ endpoint cũ | `backend/tests/test_practice.py`, `test_practice_sets.py` |
| UI theo vai | `frontend/src/AIPractice.tsx`; `frontend/src/AIPrompts.tsx`; `frontend/src/AISettings.tsx`; `frontend/src/ai.css`; `frontend/src/App.tsx` | Sửa/tái sử dụng | Root preview làm đề/duyệt mẫu, quản lý lịch/job, học viên làm cả bộ/resume/kết quả, teacher báo/ẩn | `frontend/src/AIPractice.test.tsx`, `AIPrompts.test.tsx` |
| E2E và tài liệu | `frontend/e2e/practice-sets.spec.ts`; `docs/ai-integration.md`; `docs/plans/ai-cluster.md`; `docs/current-state.md`; `myplan.txt` | E2E dự kiến tạo; còn lại sửa | Xuyên vai trò và checkpoint, ghi rõ thay thế luồng câu đơn | Playwright + checklist mục 7 |

## 4. Thứ tự triển khai và dependency

1. Thiết kế lịch một bộ/ngày, schema 0018 và dữ liệu 2 câu cũ; contract bộ đề/QA fingerprint/nguồn đủ để tạo câu.
2. System prompt có version và Root QA sample bằng **cùng pipeline** với worker; validator/chia lô trước khi bật auto-publish.
3. Job scheduler/worker bền vững, khóa kỳ, giới hạn quota/retry và publish nguyên bộ; quản lý xem tiến độ/lịch.
4. Học viên làm/resume/nộp bộ, chấm và streak; chuyển UI, giữ đường cũ trong giai đoạn tương thích.
5. Test lỗi/đồng thời, E2E Root → lịch → học viên, backup/restore rehearsal, deploy với lịch tắt mặc định; chỉ bật sau Root QA.

## 5. Migration, deployment, rủi ro dữ liệu

Migration 0018 additive, `set_id` nullable; không sửa/xóa 2 câu cũ hoặc ngày thưởng. Chụp baseline count/hash và `pg_dump -Fc`, restore scratch, upgrade/check/downgrade guard, rồi rollout API + worker + web. Giữ DB/Mailpit/material volume và mọi thay đổi Compose có sẵn; không sửa `.env` hay seed tenant thật. Worker phải có Compose secret riêng đúng mount và mạng tương tự API; dừng worker/lịch trước khi rollback. Nếu provider lỗi, hết quota hoặc nguồn/prompt thay đổi, giữ bộ đã phát hành và báo thiếu bộ mới, không trộn lô cũ với phiên bản mới. Preview Root và job production có giới hạn tiền/lượt riêng để thử thật không gây chi phí bất ngờ. Chạy rollout với lịch mặc định tắt, Root duyệt sample rồi quản lý mới bật lịch.

## 6. Kiểm thử dự kiến

Từ `backend/`: `.venv\\Scripts\\python.exe -m pytest tests/test_practice_sets.py tests/test_practice.py tests/test_ai_config.py tests/test_ai_prompts.py -q` trên SQLite và PostgreSQL test schema riêng; chọn lọc hồi quy `tests/test_admissions.py tests/test_results.py tests/test_materials.py`. `.venv\\Scripts\\python.exe -m ruff check app tests/test_practice_sets.py tests/test_practice.py`; Alembic upgrade/check và restore rehearsal. Cần ca: 10/20 câu hợp lệ, lô thiếu 1 câu/sai schema/trùng thì không publish; QA chưa làm/đổi fingerprint bị chặn; hai worker cùng kỳ chỉ một bộ; crash/retry không nhân đôi gọi/đề/attempt; tenant/RBAC/enrollment bị thu hồi; nháp/resume/submit song song; streak qua timezone và bộ cũ; quota/chi phí/nguồn lỗi.

Từ `frontend/`: `npm.cmd test -- --run src/AIPractice.test.tsx src/AIPrompts.test.tsx`, `npm.cmd run lint`, `npm.cmd run build`, `npx.cmd playwright test e2e/practice-sets.spec.ts`. E2E dùng fake provider, không gọi API tính phí: Root làm sample và duyệt → quản lý bật lịch → worker tạo bộ → học viên làm/nộp → theme, teacher ẩn; mobile 390 px và reduced motion. Tiêu chí 0 lỗi, không full suite sau mỗi chỉnh sửa nhỏ; trước deploy kiểm baseline, schema, health/OpenAPI, worker và dữ liệu cũ.

## 7. Checklist nghiệm thu thủ công

- Root: chọn cấu hình, làm thử 10–20 câu ở preview; thấy điểm/giải thích/nguồn, duyệt hoặc từ chối; đổi prompt/model/khóa học làm approval hết hiệu lực, thu hồi dừng job mới; không tạo streak/attempt thật khi preview.
- Quản lý: bật lịch sau approval; thấy lịch kế tiếp, job đang chạy/lỗi/hoàn tất, số câu và hạn; không phải duyệt từng câu, có thể tạm dừng lịch; tenant khác không thấy đề.
- Giáo viên: xem bộ lớp phụ trách và báo/ẩn khẩn cấp; lớp khác bị chặn.
- Học viên: chỉ thấy bộ còn hiệu lực của lớp đang học; làm dở rồi trở lại, không thấy đáp án sớm; nộp một lần nhận đúng điểm/giải thích; retry không thêm kết quả/streak; mobile dùng được.
- Vận hành: thử model chậm, crash worker, thiếu quota, output sai, trùng câu, thay prompt/nguồn, restart, restore DB + key, giữ nguyên volume và dữ liệu 0017; không có bộ nửa vời hay chi phí retry vô hạn.

## 8. Quyết định đã chốt và còn cần trả lời

- **Đã chốt:** 10–20 câu/bộ; Root làm thử và duyệt **mẫu một lần cho từng cấu hình**, các bộ sau qua validator sẽ tự phát hành; sinh theo **lịch cố định**. Bản nháp/bài thủ công cũ được giữ, không còn là đường bắt buộc của bộ đề mới.
- **Đã chốt:** mỗi ngày mở một bộ; học viên phải hoàn thành trọn bộ trong ngày địa phương của trung tâm để tính một ngày streak, không yêu cầu điểm tối thiểu. Mặc định 10 câu để tránh gánh nặng hằng ngày, có thể cấu hình tối đa 20 câu. Đề có thể xem lại sau hạn, nhưng nộp quá hạn không cộng streak cho ngày đã qua.
- **Mặc định đề xuất nếu chưa có quyết định khác:** Root approval gắn với khóa học + ngôn ngữ + prompt + provider/route + blueprint/source version; thay đổi một trong các yếu tố này cần sample mới. Không tự duyệt mọi khóa chỉ vì một prompt mẫu toàn hệ thống đạt.

## 9. Đề cử model và trạng thái

Đề cử model: GPT gpt-6-astra — high, vì thay đổi giao dịch nộp bài/streak, scheduler/worker và auto-publish nội dung cho học viên nhỏ tuổi cần thiết kế đồng thời về chất lượng, quyền và dữ liệu.

- [x] Kiểm tra checkpoint, file thực tế và số bản ghi bài luyện trước khi lập kế hoạch.
- [x] Chốt Root duyệt mẫu một lần và lịch cố định; lưu system prompt đề xuất.
- [x] Chốt nhịp lịch/streak mục 8: một đề mỗi ngày, hoàn thành trọn bộ mới tính ngày.
- [ ] Người dùng duyệt triển khai kế hoạch; **chưa code, deploy hoặc đổi Jira**.
