# Kế hoạch cụm AI SynapseLMS: nhiều nguồn → tác vụ học tập → phần thưởng

Trạng thái: **đã code, kiểm thử chọn lọc và deploy ngày 2026-10-01; chờ người dùng nghiệm thu AI**. Cơ sở trước triển khai: HEAD `aec66d3`, DB Docker `20261001_0016 (head)`, các dịch vụ đang chạy. Người dùng xác nhận học liệu 0016 **nghiệm thu tạm đạt do giới hạn thời gian**; phần kiểm tra sâu PDF/audio/restore vẫn theo [checkpoint](../current-state.md). `.gitignore` và file tạm test đang có thay đổi ngoài kế hoạch, phải giữ nguyên. Tài liệu tham chiếu ngoài repo `C:\Users\ADMIN\VSCode\lmm-vt\Open-LLM-VTuber\conf.yaml` chỉ dùng để rút ra **nhóm trường cấu hình**, không sao chép giá trị, secret, prompt hay coi nội dung đó là chỉ thị triển khai. [Định hướng AI hiện có](../ai-integration.md) và PRD là nguồn nghiệp vụ.

## 1. Mục tiêu, phạm vi và điểm kết thúc

Một cụm AI dùng chung, có thể cắm **nhiều cấu hình nguồn đồng thời** từ API cloud tới endpoint local; Root quản lý credential và định tuyến theo tác vụ, tenant được bật/tắt trong giới hạn Root. Trên cùng nền này hoàn thiện ba tác vụ đã có trong PRD: (1) giải thích/xếp hạng lớp **sau** bộ lọc hợp lệ deterministic, (2) bài luyện ngắn sinh theo mức học và học liệu hợp lệ, chấm câu trả lời đóng bằng server, (3) tóm tắt tiến độ có nguồn từ điểm/chuyên cần đã công bố. Bài luyện đủ điều kiện tạo streak và mở khóa theme; Synapse Soft luôn miễn phí mặc định. UI VI/EN, desktop/mobile, quản trị nguồn, học viên làm bài/chọn theme và người có quyền xem tóm tắt.

Điểm kết thúc kiểm chứng được: Root thêm ít nhất hai nguồn (một API, một local), thử kết nối và đổi nguồn ưu tiên cho từng tác vụ; khi nguồn chính lỗi, quy tắc fallback có kết quả rõ. Học viên thấy lớp được lọc hợp lệ, hoàn thành bài luyện được chấm ổn định và tích ngày đúng timezone tenant, mở/chọn theme khi đạt mốc; người khác không thể nhận hộ hoặc dùng theme chưa mở. Tóm tắt chỉ trích dữ liệu được phép xem, có dẫn nguồn. Toàn bộ AI có thể tắt mà luồng tuyển sinh/điểm/học liệu tiếp tục chạy.

Ngoài đợt: AI tự quyết xếp lớp, tự sửa điểm/học phí/enrollment, chấm câu trả lời mở/phát âm, video, TTS/ASR/VAD, vận hành trực tiếp model file/GPU trong container API, agent gọi công cụ tùy ý, chat tự do với học viên, theme mua bằng tiền. `conf.yaml` có các mục này nhưng chúng thuộc sản phẩm VTuber, không được nhập máy móc vào SynapseLMS. Không tự tạo seed trên tenant thật.

## 2. Quy tắc nghiệp vụ, quyền, dữ liệu và API

### 2.1. Cấu hình nguồn: trường chung

| Trường màn hình Root | Bắt buộc | Ý nghĩa / quy tắc |
|---|---|---|
| Tên hiển thị, mã cấu hình | Có | Nhiều cấu hình cho cùng hãng/model; mã bất biến sau khi dùng. |
| Loại nguồn | Có | OpenAI, Gemini, Claude, API tương thích OpenAI, Ollama, LM Studio hoặc endpoint local tương thích; adapter mở rộng về sau. |
| Model ID | Có | Chuỗi đúng theo nguồn; kiểm tra bằng nút thử kết nối, không hard-code danh sách model có thể đổi. |
| Base URL | Tùy loại | Cloud chính hãng dùng mặc định kiểm soát ở server; custom/local phải nhập endpoint đầy đủ và thử từ **container API**. |
| API key / token | Tùy loại | Chỉ nhập mới/thay thế; UI không đọc lại. Server lưu mã hóa bằng khóa riêng hoặc secret reference, không ghi plaintext vào bảng/log. |
| Bật/tắt, tác vụ cho phép | Có | `class_recommendation`, `practice_generation`, `progress_summary`; một nguồn chỉ tham gia tác vụ đã bật. |
| Timeout, số lần thử lại | Có mặc định | Giới hạn; chỉ retry lỗi tạm thời, không nhân đôi bài/chi phí khi client retry. |
| Giới hạn input/output token, nhiệt độ | Có mặc định | Theo khả năng từng adapter; không hiện tham số không được hỗ trợ. |
| Song song tối đa, ngân sách/ngày | Có mặc định | Chặn quá tải/chi phí theo nguồn; Root thấy usage, không thấy prompt chứa PII. |
| Thứ tự ưu tiên và fallback theo tác vụ | Có sau khi có nguồn | Không có một provider toàn hệ thống; có thể route mỗi tác vụ sang nguồn khác. |

### 2.2. Trường riêng theo nguồn

| Nguồn cấu hình | Trường Root cần điền | Trường tùy chọn / lưu ý |
|---|---|---|
| OpenAI API | Tên, Model ID, API key | Organization ID / Project ID nếu tài khoản cần; endpoint chính hãng mặc định. |
| Gemini API | Tên, Model ID, API key | Endpoint mặc định; không đưa key ra frontend. |
| Claude API | Tên, Model ID, API key | Workspace ID nếu credential yêu cầu; adapter xử lý phiên bản API. |
| API cloud tương thích OpenAI | Tên, Base URL HTTPS, Model ID, API key/token | Organization/Project ID nếu nguồn hỗ trợ. Đây là cấu hình cho DeepSeek, Groq, Mistral, Zhipu hoặc proxy **chỉ khi endpoint cụ thể tương thích**; thử khả năng structured output trước khi gán tác vụ. |
| Ollama local | Tên, Base URL nội bộ, Model ID | Token nếu qua gateway; `keep_alive` tùy chọn nếu dùng API native. Không nhầm `localhost` của máy người dùng với container API. |
| LM Studio local | Tên, Base URL `/v1`, Model ID | Token nếu server/gateway bật xác thực; phải bật server và tải model ở máy vận hành. |
| Local khác (ví dụ llama.cpp server) | Tên, Base URL, Model ID/alias, kiểu tương thích, token nếu có | SynapseLMS gọi endpoint đang chạy; không nhận `model_path` để tự chạy file model. |
| Hugging Face inference | **Adapter giai đoạn sau trong cùng cụm**, cần endpoint/provider ID, model và token | Chốt giao thức endpoint trước khi mở form; không hiển thị một form chung gây hiểu nhầm mọi endpoint đều tương thích. |

Các nhóm `llm_configs` trong file tham chiếu có `base_url`, `llm_api_key`, `organization_id`, `project_id`, `model`, `temperature`, cùng `keep_alive`/`model_path` cho local. Ta chỉ giữ trường phù hợp ứng dụng web. Tách “nguồn” khỏi “model” và “route tác vụ”: một nguồn có thể có nhiều model; Root có thể chuyển route mà không thay secret. Theo tài liệu chính thức, [OpenAI dùng API key và có org/project tùy ngữ cảnh](https://platform.openai.com/docs/api-reference/backward-compatibility?lang=ruby), [Gemini yêu cầu API key](https://ai.google.dev/gemini-api/docs/api-key), [Claude có key và phiên bản API](https://platform.claude.com/docs/en/manage-claude/authentication), [Ollama có endpoint local và compatibility](https://docs.ollama.com/api/openai-compatibility), [LM Studio công bố endpoint tương thích](https://lmstudio.ai/docs/developer/openai-compat). Không chốt model ID hoặc giá ở kế hoạch vì chúng thay đổi.

### 2.3. System prompt dễ chỉnh mà vẫn kiểm soát được

- Root có **Prompt Studio** trong setting: ba template riêng cho tư vấn lớp, sinh bài luyện và tóm tắt tiến độ; phiên bản VI/EN hoặc biến `locale` được kiểm tra. Mỗi template có `draft → tested → published → retired`; sửa tạo phiên bản mới bất biến, không thay trực tiếp bản đang dùng. Root xem diff/lịch sử, thử bằng bộ dữ liệu giả đã kiểm soát, xem output đã validate, publish một bản active theo tác vụ/ngôn ngữ và rollback bằng cách kích hoạt lại bản cũ. Không cần build/deploy để đổi lời văn.
- Phần Root chỉnh được: system instruction về vai trò, giọng điệu, mức giải thích, độ dài và các biến **trong allowlist**. UI hiển thị biến hợp lệ và báo lỗi biến thiếu/lạ. Không cho template tự chọn trường DB, mở rộng quyền, cấp công cụ mạng hoặc đổi schema đầu ra. Server luôn ghép phần policy bất biến về quyền/riêng tư, tập dữ liệu đã lọc và JSON schema/semantic validator **ngoài** template; prompt không là cơ chế bảo mật.
- Mỗi AI run ghi `prompt_version_id`, task, provider/model, schema version, input digest, source refs, trạng thái/usage. Không log full prompt hay dữ liệu cá nhân theo mặc định. Đổi prompt chỉ ảnh hưởng run mới; kết quả cũ giữ version để giải thích và so sánh. Bản nháp/test không ảnh hưởng production. Nếu chưa có bản active, tác vụ dùng fallback deterministic/chưa sẵn sàng, không gửi yêu cầu thiếu hướng dẫn tới provider.
- Trước publish chạy evaluation cố định với ca bình thường, thiếu dữ liệu, cảnh báo, prompt injection trong học liệu, output ngoài schema và hai ngôn ngữ. Root thấy so sánh với bản active và phải ghi lý do publish/rollback. Adapter local nào không giữ được chỉ thị hệ thống hoặc output schema cần báo không đạt capability, không được dùng cho tác vụ đó. Thiết kế template + biến và đánh giá phiên bản phù hợp [hướng dẫn prompt template của Claude](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompt-templates-and-variables); [Gemini nhấn mạnh vẫn phải kiểm tra ý nghĩa sau structured output](https://ai.google.dev/gemini-api/docs/structured-output).

### 2.4. Gợi ý lớp học

- Điểm vào đầu tiên là yêu cầu tuyển sinh trạng thái `waiting`: giáo vụ/quản lý xem các lớp từ `app.services.admissions.candidates()`. Hàm hiện đã lọc cứng cùng khóa, chi nhánh/hình thức, lịch/giáo viên/phòng, chỗ trống và xung đột; giữ nguyên hàm này làm nguồn sự thật. `ADMISSION_LEVEL_REVIEW` và `ADMISSION_AVAILABILITY_REVIEW` là **cảnh báo cần người xử lý**, không được AI biến thành “đủ điều kiện chắc chắn”. Học viên chỉ xem gợi ý cho yêu cầu của chính mình nếu UI cung cấp; không được xếp lớp từ gợi ý.
- Trước gọi AI, server tạo danh sách candidate ID + tên/mã lớp, số chỗ, lịch đã rút gọn, cảnh báo, tiêu chí đã có trên `AdmissionRequest` (`course_id`, branch, format, availability) và trình độ đã xác minh nếu có. Không gửi tên, email, số điện thoại, học phí hoặc toàn hồ sơ học viên. Mục tiêu/ngân sách chưa là trường của `AdmissionRequest`; không giả định có dữ liệu này hoặc tự thêm vào form trong đợt AI. Không có candidate: trả danh sách rỗng cùng lý do nghiệp vụ; một candidate: có thể giải thích bằng quy tắc mà không tốn lời gọi AI.
- AI chỉ trả **thứ tự candidate ID** và giải thích ngắn dựa trên các thuộc tính được cung cấp. Server từ chối ID ngoài tập, số liệu/khẳng định không có nguồn hoặc output sai schema; vẫn hiển thị cảnh báo gốc. Khi timeout/provider tắt, fallback sắp xếp quy tắc theo số cảnh báo, phù hợp lịch, chỗ và ngày bắt đầu, với nhãn rõ “gợi ý theo quy tắc”. Lưu as-of/source digest/prompt version để phát hiện gợi ý cũ.
- Nút xếp lớp thủ công hiện tại tiếp tục gọi `candidates()` **lại tại thời điểm quyết định** và kiểm tra version/chỗ; gợi ý AI không giữ ghế, không duyệt warning và không ghi enrollment. Gợi ý hết hạn phải tính lại; audit ai xem/chọn lớp và lý do xếp của giáo vụ, không quy trách nhiệm cho model.

### 2.5. Tóm tắt tiến độ

- Học viên xem bản thân; giáo viên phụ trách xem học viên/lớp trong phân công hiện hành, mất phân công thì request kế tiếp bị chặn. Chưa mở màn hình phân tích liên trung tâm hay thay đổi quyền sổ điểm. Nguồn chỉ gồm kết quả từ gradebook `publish_at <= now()` theo logic `/results/mine`, điểm danh buổi `finalized` theo `/attendance/mine` hoặc service tổng hợp đã có, và attempt bài luyện hợp lệ. Chưa chốt sổ/điểm thiếu là “chưa đủ dữ liệu”, **không xem như 0**. Không trộn tài chính, dữ liệu nội bộ chưa công bố hoặc nhận xét giáo viên chưa cho học viên xem.
- Server dựng facts có nguồn (class/item/session/attempt ID, mốc công bố, số liệu được phép), rồi yêu cầu AI viết ngắn gọn: điều đã làm tốt, phần nên luyện tiếp và gợi ý hành động. Output buộc citation tới fact ID trong payload; ID lạ hoặc khẳng định trái số liệu bị từ chối. Hiển thị nhãn “AI hỗ trợ”, số liệu nền và đường mở màn hình nguồn. Không dự báo đạt/rớt, chẩn đoán năng lực, sửa điểm hoặc tự chuyển enrollment.
- Tạo theo yêu cầu, cache theo người xem/phạm vi, locale, source digest, prompt version và route model; không gọi provider mỗi lần mở trang. Khi điểm được sửa/công bố lại, điểm danh chốt lại, attempt thay đổi hoặc quyền truy cập bị thu hồi, cache cũ không còn hợp lệ. Cần hạn mức và idempotency để hai tab không sinh hai bản; provider lỗi/AI tắt thì hiển thị bảng tiến độ deterministic thay vì bản văn cũ hoặc dữ liệu của người khác.
- Tóm tắt lớp của giáo viên là tổng hợp trong lớp được phân công, không lộ student ngoài roster; tóm tắt cá nhân của học viên chỉ dùng nguồn bản thân. Test xuyên tenant, giáo viên bị gỡ phân công, thay đổi nguồn sau cache, thiếu điểm, enrollment bảo lưu/hủy, prompt mới và cả output bịa citation.

Root duy nhất tạo/sửa/test/disable nguồn và secret; phải có audit actor/thời gian. Quản lý tenant chỉ bật tác vụ trong danh sách Root cho phép và xem quota/usage tenant, không xem key hoặc URL nội bộ nhạy cảm. Giáo viên xem bản nháp bài luyện của lớp phụ trách, có thể ẩn/đánh dấu sai; học viên chỉ thấy bài của mình/lớp đủ quyền. Root hỗ trợ tenant cần support session đúng tenant. Mọi endpoint danh sách/chi tiết dùng DTO whitelist và kiểm tra quyền server side.

Chỉ gửi payload được whitelist: lớp hợp lệ và thuộc tính học tập cần thiết cho tư vấn; mục tiêu/mức học/chủ đề hoặc trích đoạn học liệu **đã được phép** cho bài luyện; số liệu điểm/chuyên cần **đã công bố** cho tóm tắt. Không gửi email, điện thoại, địa chỉ, tài chính, prompt thô chứa PII. URL local/custom phải được quản trị allowlist, chống SSRF/chuyển hướng/DNS rebinding; chỉ API container được gọi. Secret cần khóa mã hóa triển khai riêng, rotation/revoke và masking; nếu thiếu khóa thì nguồn cloud không bật, AI core vẫn chạy. Test kết nối trả trạng thái/khả năng, không trả raw provider error hoặc secret.

AI output không phải quyết định nghiệp vụ. Tư vấn lớp giữ lọc cứng từ tuyển sinh, AI chỉ sắp hạng/giải thích và fallback giải thích quy tắc. Bài luyện có schema phiên bản bất biến, đáp án đóng và validator kiểm tra cấu trúc, độ dài, an toàn/độ tuổi, nguồn học liệu; sai schema không phát hành. Bài nộp có idempotency key, chấm deterministic trên server, không ghi vào `student_scores`/gradebook 0015. Tóm tắt có source IDs/đường dẫn đọc đúng quyền và nhãn “AI hỗ trợ”, không suy ra đạt/rớt hoặc chẩn đoán học viên. Usage chỉ lưu metadata, token/độ trễ/trạng thái/cost estimate, không lưu prompt đầy đủ mặc định.

Streak đã chốt tính **một ngày** khi học viên hoàn tất ít nhất một bài luyện hợp lệ trong timezone tenant; retry/mở lại/đổi đáp án không cộng thêm. Một ngày không có bài hoặc provider lỗi cần fallback bài đã được xác thực để học viên không mất cơ hội. Mốc đã chốt 3/7/14 ngày mở Neo Pop/Clay Garden/Liquid Glass; Synapse Soft luôn có. Grant theme là server-authoritative, per học viên/tenant và bền vững; lựa chọn theme không chuyển sang tenant khác, mất streak không khóa lại theme đã nhận. Hỗ trợ reduced motion, contrast và giao diện mobile theo ref.

Dữ liệu dự kiến: cấu hình nguồn/model/secret reference, route tác vụ và quota tenant; prompt template/version/active pointer/audit, run/usage log kèm prompt version và source digest; snapshot gợi ý lớp và cache tóm tắt có phạm vi quyền; bài luyện version/câu/đáp án, assignment hoặc daily availability, attempt/result; daily activity/streak, reward grant và selected theme. Root config là dữ liệu hệ thống; mọi bài/attempt/reward và kết quả AI gắn người học là tenant-scoped với FK ghép `(organization_id, id)`, unique idempotency và index đọc chính. API dự kiến `/api/v1/ai/*` cho Root config/prompt/test/route/usage và task read; `/api/v1/practice/*` cho bài/nộp/lịch sử/streak/theme. Tên endpoint chi tiết chốt lúc thiết kế DTO, không tái sử dụng URL học liệu để cấp quyền AI.

## 3. Bản đồ thay đổi đã xác minh

“Dự kiến tạo” nghĩa là đường dẫn chưa tồn tại khi khảo sát. Tên symbol mới bên dưới chỉ là **trách nhiệm dự kiến**, không khẳng định đã có. `backend/app/api/routes/admissions.py`, `results.py`, `materials.py` được đọc/tái sử dụng quyền và dữ liệu, chỉ sửa nếu luồng mới thực sự cần.

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol hoặc trách nhiệm thay đổi | Test tương ứng |
|---|---|---|---|---|
| Schema 0017 | `backend/alembic/versions/20261001_0017_ai_cluster.py`; `backend/app/models/ai.py`; `backend/app/models/practice.py`; `backend/app/models/__init__.py` | Dự kiến tạo; dự kiến tạo; dự kiến tạo; sửa | Config/route/run, bài/attempt/streak/reward, FK/unique/guard downgrade | `backend/tests/test_ai_config.py`, `test_practice.py`, migration rehearsal |
| Provider & an toàn | `backend/app/services/ai/providers.py`; `backend/app/services/ai/routing.py`; `backend/app/services/ai/privacy.py`; `backend/app/core/config.py`; `backend/pyproject.toml` | Dự kiến tạo ×3; sửa ×2 | Adapter cloud/local, route/fallback/circuit breaker, whitelist, secret/runtime config | `backend/tests/test_ai_config.py`, `test_ai_tasks.py` |
| Prompt Studio | `backend/app/services/ai/prompts.py`; `backend/app/api/routes/ai.py`; `frontend/src/AIPrompts.tsx` | Dự kiến tạo ×2; dùng route mới nêu dưới | Version, allowlist biến, đánh giá dữ liệu giả, publish/rollback nguyên tử, audit; UI Root xem diff và thử bản nháp | `backend/tests/test_ai_prompts.py`, `frontend/src/AIPrompts.test.tsx` (đều dự kiến tạo) |
| Gợi ý lớp và tiến độ | `backend/app/services/ai/recommendations.py`; `backend/app/services/ai/progress.py`; `backend/app/services/admissions.py`; `backend/app/api/routes/attendance.py`; `backend/app/api/routes/results.py` | Dự kiến tạo ×2; tái sử dụng ×3 | Chỉ xếp hạng candidate hợp lệ; trích facts đã công bố/finalized, kiểm tra citation, cache theo quyền và nguồn | `backend/tests/test_ai_recommendations.py`, `backend/tests/test_ai_progress.py` (dự kiến tạo) |
| Tác vụ AI | `backend/app/services/ai/tasks.py`; `backend/app/services/practice.py`; `backend/app/api/ai_schemas.py`; `backend/app/api/routes/ai.py`; `backend/app/api/routes/practice.py`; `backend/app/api/router.py` | Dự kiến tạo ×5; sửa router | Lọc rồi xếp hạng lớp, sinh/kiểm tra bài, tóm tắt có nguồn, chấm, streak/reward và API | `backend/tests/test_ai_tasks.py`, `test_practice.py` |
| Dữ liệu nghiệp vụ nền | `backend/app/api/routes/admissions.py`; `backend/app/api/routes/results.py`; `backend/app/api/routes/materials.py`; `backend/app/models/enrollment_lifecycle.py`; `backend/app/api/routes/notifications.py` | Tái sử dụng; sửa có điều kiện | Lọc lớp, dữ liệu đã công bố, material grant, enrollment period, thông báo bài mới/reward | `test_admissions.py`, `test_results.py`, `test_materials.py` và test AI |
| UI quản trị & học viên | `frontend/src/AISettings.tsx`; `frontend/src/AIPractice.tsx`; `frontend/src/AIInsights.tsx`; `frontend/src/ThemeRewards.tsx`; `frontend/src/ai.css`; `frontend/src/App.tsx`; `frontend/src/api.ts`; `frontend/src/i18n.ts`; `frontend/src/styles.css` | Dự kiến tạo ×5; sửa ×4 | Form nguồn/route, bài luyện, tư vấn/tóm tắt, reward/theme, nav, VI/EN/mobile | `frontend/src/AISettings.test.tsx`, `AIPractice.test.tsx`, `App.test.tsx` |
| E2E & tài liệu | `frontend/e2e/ai-cluster.spec.ts`; `docs/ai-integration.md`; `docs/current-state.md`; `docs/README.md`; `myplan.txt` | Dự kiến tạo; sửa ×4 | Root cấu hình nguồn → learner dùng → fallback/reward; checkpoint và vận hành | Playwright, checklist theo vai trò |

## 4. Thứ tự triển khai và phụ thuộc

1. **AI-01 Cấu hình nguồn và Prompt Studio trước:** migration, Root UI, secret handling, adapter/test connection, capability matrix, route mỗi tác vụ, quota/circuit breaker; template có phiên bản, đánh giá, publish/rollback. Fake provider cho CI; không cần key thật để test. Chốt cấu trúc nguồn/model/route, prompt và đường dẫn local từ API container trước khi mở tác vụ người dùng.
2. **AI-02 Tư vấn lớp:** dùng bộ lọc deterministic hiện có; AI xếp hạng/giải thích từ tập hợp hợp lệ, fallback quy tắc. Không cho AI thao tác placement.
3. **AI-03 Bài luyện:** nguồn học liệu/quyền/enrollment → sinh câu hỏi đóng theo schema → validate → học viên làm/nộp → server chấm; lịch sử và phản hồi giáo viên. Đây là dependency của streak, không buộc triển khai TTS/ASR.
4. **AI-04 Tóm tắt tiến độ:** chỉ đọc điểm/chuyên cần công bố và các attempt trong quyền; lưu bản nháp/citation, không sửa kết quả nguồn. Fallback số liệu thuần khi AI tắt/lỗi.
5. **AI-05 Streak/theme:** tính ngày từ attempt đủ điều kiện, grant và chọn theme, UX desktop/mobile, an toàn khi tắt AI. Sau đó E2E toàn cụm, backup/restore rehearsal, deploy theo gate và cập nhật vận hành.

Mỗi mốc có thể review riêng nhưng đợt chỉ kết thúc sau AI-05 và test xuyên suốt. Nếu provider chưa được cấu hình, Root vẫn thấy setting và hệ thống hiện trạng chạy bình thường; không phát hành UI bài AI trống hoặc gọi API thật từ test.

## 5. Migration/deployment và bảo vệ dữ liệu

Migration 0017 chỉ **thêm** bảng/index/constraint, không backfill grant/theme hoặc sửa bảng điểm/học phí. Chụp count/hash DB trước rollout, `pg_dump -Fc`, restore và nâng trên DB scratch, `alembic check`, thử downgrade DB trống và guard từ chối khi đã có attempt/config quan trọng. Kiểm tra tenant mismatch, unique submission/reward, transaction/concurrency và timezone. Không xóa volume DB/Mailpit/học liệu; không sửa `.env` trong phiên lập kế hoạch.

Secret mã hóa cần khóa triển khai riêng/secret manager đã chốt trước khi nhập key thật; backup DB phải đi cùng khả năng khôi phục khóa, nếu không credential sẽ không đọc được. Không đưa key vào migration, file test, log, OpenAPI hoặc browser. Local endpoint phải truy cập được từ API container, có allowlist mạng; không mặc định mở cổng local model ra Internet. Build API/web sau test; rollout từng bước với AI tắt mặc định cho đến khi health, schema, baseline, adapter fake/local và quota đạt. Tắt AI/rollback route không được ảnh hưởng nghiệp vụ cũ; không tự ghi dữ liệu thử vào tenant thật.

## 6. Kiểm thử dự kiến

Từ `backend/`: `.venv\Scripts\python.exe -m pytest tests/test_ai_config.py tests/test_ai_prompts.py tests/test_ai_recommendations.py tests/test_ai_progress.py tests/test_practice.py -q` trên SQLite; cùng ca trên PostgreSQL bằng fixture `SYNAPSE_TEST_POSTGRES=1` và URL DB test lấy từ Compose nhưng chạy trong schema cô lập. Hồi quy chọn lọc `tests/test_admissions.py tests/test_results.py tests/test_materials.py tests/test_auth_identity.py`; `.venv\Scripts\python.exe -m ruff check app tests`; Alembic upgrade/check và restore rehearsal. Cần ca secret masking/rotation, SSRF/redirect, tenant/RBAC, timeout/fallback, quota/parallel request, idempotency attempt, output sai schema, timezone/DST và reward không nhận hai lần.

Từ `frontend/`: `npm.cmd test -- --run src/AISettings.test.tsx src/AIPrompts.test.tsx src/AIPractice.test.tsx src/App.test.tsx`, `npm.cmd run lint`, `npm.cmd run build`, `npx.cmd playwright test e2e/ai-cluster.spec.ts` trên backend fixture cô lập. E2E thử Root cấu hình hai nguồn fake/cloud giả lập + local giả lập, switch route, học viên làm bài/nhận theme, giáo viên/manager đọc đúng quyền, responsive 390 px và reduced motion. Không gọi API có tính phí trong CI. Đạt khi 0 lỗi, số ca collect thật rõ; PostgreSQL/migration và lỗi bảo mật đều có bằng chứng, health/OpenAPI/baseline sau deploy khớp.

## 7. Checklist nghiệm thu thủ công theo vai trò

Kiểm chứng riêng Prompt Studio: Root sửa bản nháp, thử dữ liệu giả và xem diff trước khi publish; người học vẫn nhận bản đang hoạt động. Publish/rollback phải đổi đúng phiên bản cho run mới, không làm thay đổi kết quả đã lưu. Giáo vụ kiểm tra gợi ý chỉ chứa candidate của yêu cầu đang chờ, warning vẫn hiển thị và xếp lớp sẽ kiểm tra lại chỗ/lịch. Học viên mở tóm tắt có dẫn nguồn điểm đã công bố, chuyên cần đã chốt và bài luyện; giáo viên chỉ xem lớp đang phụ trách. Đổi điểm/quyền sau khi có cache phải làm bản cũ hết hiệu lực.

- Root: thêm hai nguồn, nhập/thay key không đọc lại được, test nguồn từ container API, gán ưu tiên/fallback theo tác vụ, bật/tắt và xem usage/cost estimate; URL nội bộ không bị lộ cho vai khác.
- Quản lý trung tâm: chỉ bật tác vụ được Root cho phép, xem hạn mức tenant; không thấy secret của hệ thống hoặc dữ liệu tenant khác. Thử AI tắt hoàn toàn, tuyển sinh/điểm/học liệu vẫn dùng được.
- Giáo viên: xem bài luyện của lớp phụ trách, báo/ẩn câu sai; không truy cập lớp khác. Tóm tắt có nguồn và không ghi đè điểm.
- Học viên: lớp được gợi ý đều đủ điều kiện; làm lại/retry không nhận điểm/streak hai lần; trước/sau mốc ngày theo timezone; đạt mốc mở và chọn theme, đổi tenant không mang phần thưởng; Synapse Soft luôn có, mobile và reduced motion dùng được.
- Vận hành: thử nguồn cloud/local lỗi, timeout, output sai schema, vượt quota, đổi khóa, restart/restore DB+khóa, logging không chứa PII/key; so baseline DB và container/volume cũ.

## 8. Quyết định cần người dùng trả lời trước khi triển khai

1. **Đã chốt ranh giới:** người dùng xác nhận ASR/TTS/VAD sang đợt tiếng nói riêng, hiện ưu tiên thấp. Cụm này chỉ dùng LLM cho ba tác vụ PRD và theme thưởng; không kéo hạ tầng âm thanh từ `conf.yaml` vào.
2. **Đã chốt credential:** Root nhập/thay API key trong UI, DB lưu bản mã bằng mã hóa có xác thực; khóa chủ độc lập với JWT/DB, cấp cho riêng API qua Docker Compose secret file nằm ngoài repo và sao lưu tách biệt. Chỉ Root có quyền ghi/test; không có API đọc lại key. Hỗ trợ quay vòng khóa bằng key version và kế hoạch re-encrypt; tắt nguồn nếu thiếu khóa, không làm gián đoạn nghiệp vụ cũ. Local không cần key khi endpoint chỉ ở mạng tin cậy, nhưng gateway có auth thì phải nhập token. Không cần key thật để test bằng fake provider. Cách này phù hợp vận hành Docker hiện tại; nếu sau này có vault/KMS thì thay tầng lưu secret mà không đổi API quản trị.
3. **Đã chốt streak/theme:** hoàn thành **toàn bộ** một bài luyện hợp lệ/ngày là đủ, không đặt ngưỡng điểm để khuyến khích nỗ lực; mỗi học viên/tenant/ngày chỉ tính một lần theo timezone tenant ghi tại thời điểm nộp. Bài cũ nộp lại, retry và đổi đáp án không cộng ngày. Bỏ lỡ một ngày sẽ ngắt chuỗi; lần hoàn thành kế tiếp bắt đầu lại ở 1, còn best streak và theme đã mở được giữ; chưa có “streak freeze”. Mốc 3/7/14 mở Neo Pop/Clay Garden/Liquid Glass, Soft luôn có. Khi provider lỗi, chỉ bài fallback đã qua validator/được duyệt mới tính, không tạo grant từ phản hồi AI lỗi.

## 9. Đề cử model và trạng thái

Đề cử model: GPT gpt-6-astra — high, vì cụm liên quan secret, mạng local, tenant/RBAC, dữ liệu học viên nhỏ tuổi, giao dịch/idempotency, provider failover và UI thưởng xuyên suốt.

- [x] Kiểm tra checkpoint, HEAD/working tree, Docker và revision thật; không dựa hoàn toàn vào checkpoint cũ.
- [x] Đọc chỉ cấu trúc nhóm LLM trong `conf.yaml`, không in/copy giá trị secret; xác minh file hiện hữu/mới của bản đồ.
- [x] Lưu kế hoạch toàn cụm; chưa code, deploy hoặc đổi Jira.
- [x] Người dùng duyệt triển khai toàn kế hoạch; các quyết định mục 8 đã chốt.
- [x] Code backend/UI, migration 0017, tài liệu vận hành và test tự động chọn lọc; deploy API/web sau backup và restore rehearsal.
- [ ] Người dùng nghiệm thu cụm AI theo mục 7; chưa cấu hình credential/provider trên tenant thật.

## 10. Bàn giao triển khai 2026-10-01

- **Đã code:** migration `20261001_0017` thêm 12 bảng; adapter OpenAI/Gemini/Claude/OpenAI-compatible/Ollama/LM Studio, mã hóa key và quay khóa, route theo tác vụ, opt-in/quota tenant, Prompt Studio có phiên bản, gợi ý lớp có lọc cứng, bài luyện duyệt/chấm/idempotency, tóm tắt theo nguồn, streak/theme và UI VI/EN responsive. Xem [vận hành AI](../ai-integration.md). Không cấu hình model/key hoặc seed tenant thật.
- **File thực tế khác bản đồ dự kiến:** tác vụ tách thành `backend/app/services/ai/recommendations.py`, `progress.py`, `routing.py`, `providers.py`, `prompts.py` và `backend/app/services/practice.py`; Prompt Studio ở `frontend/src/AIPrompts.tsx`, phần thưởng/theme ở `frontend/src/AIPractice.tsx` và `App.tsx`. Không tạo `tasks.py`, `ThemeRewards.tsx` hay `test_ai_tasks.py` vì trách nhiệm đã nằm trong các file trên.
- **Đã test:** SQLite AI cùng hồi quy tuyển sinh/kết quả/học liệu chọn lọc đạt (12 skip do ca chỉ chạy PostgreSQL). Nhóm AI trên SQLite + PostgreSQL schema cô lập đạt (ca khóa dòng skip trên SQLite). UI 107/107, lint/build và ruff đạt; E2E Root tạo/test cấu trúc/publish prompt 1/1 đạt. Migration restore → upgrade/check → downgrade/upgrade trên DB scratch đạt. Không chạy full backend, không gọi API tính phí.
- **Đã deploy:** `pg_dump -Fc` trước migration ở `.local-backups/pre0017-ai.dump`; live DB `20261001_0017 (head)`, Alembic check sạch, 68 bảng cũ giữ nguyên count/hash so với `.local-backups/pre0017-ai-baseline.json`, 12 bảng mới rỗng. API/web/health/OpenAPI/Mailpit HTTP 200; DB/Mailpit/ClamAV/GC container và volume giữ nguyên. Khóa chủ độc lập ngoài repo tại `C:\Users\ADMIN\SynapseLMS-secrets\ai-master-key`; cần backup riêng. DB scratch diễn tập có thể dọn sau bàn giao.
- **Giới hạn cần biết:** Prompt Studio “Thử cấu trúc” chỉ kiểm tra template/policy, chưa chạy bộ đánh giá chất lượng đầu ra trên fake provider. E2E tự động mới bao phủ Root Prompt Studio; đường đi quản lý/giáo viên/học viên, cloud/local thật, mobile/reduced motion và restore DB+khóa cần nghiệm thu thủ công mục 7. Chưa có ước tính tiền theo giá provider, cấu hình retry/song song hay Hugging Face native adapter; usage hiện có lượt/token. Đây là phần còn thiếu so với kế hoạch, chưa coi là hoàn tất hoặc đã nghiệm thu.
