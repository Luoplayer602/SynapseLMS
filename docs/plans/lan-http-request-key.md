# Sửa tạo request key khi truy cập qua HTTP hotspot/LAN

Trạng thái 2026-10-02: **đã code, test chọn lọc và deploy riêng web; chờ người dùng nghiệm thu**. Lỗi đã tái hiện tại `http://192.168.137.1:5173`: Chromium trả `isSecureContext: false`, `crypto.randomUUID: undefined`, `crypto.getRandomValues: function`. Trước bản sửa, `frontend/src/Admissions.tsx` gọi `randomUUID()` trước `api()`, nên form hiển thị “Chưa xác định kết quả...” dù request chưa được gửi. Bản đăng nhập/dashboard mới có sẵn trong workspace cũng đi cùng image web lần này; chưa được người dùng nghiệm thu. Giữ nguyên `compose.yaml` hotspot.

## 1. Mục tiêu, phạm vi và phần chưa làm

- Mọi thao tác frontend đang cần UUID hoạt động qua địa chỉ hotspot HTTP và qua localhost/HTTPS, kể cả khi trình duyệt không cung cấp `crypto.randomUUID`.
- Giữ ý nghĩa `request_key`: khóa UUID v4 ngẫu nhiên, khác giữa hai thao tác độc lập, giữ nguyên khi preview và áp dụng cùng một thao tác nếu luồng hiện tại yêu cầu. Không tự retry mutation sau lỗi mạng chưa rõ kết quả.
- Phạm vi gồm tuyển sinh, học phí/thu tiền, điểm danh, lịch lớp/buổi, bảo lưu/hoàn phí, kết quả, học liệu và nộp bài luyện AI — tất cả chỗ `crypto.randomUUID()` trong `frontend/src` đã xác minh bằng `rg`.
- Ngoài phạm vi: đổi API/schema/backend, thay quy tắc idempotency, sửa BUG-005 tài khoản khóa, cấu hình HTTPS/reverse proxy cho LAN, làm lại các màn nghiệp vụ chưa đến lượt trong kế hoạch UI/UX. HTTP hotspot chỉ phù hợp thử nghiệm trên mạng tin cậy; sửa UUID không mã hóa lưu lượng đăng nhập.

## 2. Quy tắc nghiệp vụ, quyền và dữ liệu/API

- Tạo UUID v4 bằng `crypto.randomUUID()` khi có; fallback dùng `crypto.getRandomValues()` và đặt đúng bit phiên bản/variant. Không dùng `Math.random`, timestamp hoặc thư viện mới chỉ để tạo khóa. Nếu cả hai Web Crypto API không khả dụng, ngăn thao tác trước khi gọi API và hiển thị lỗi cấu hình trình duyệt rõ ràng theo VI/EN.
- Backend hiện nhận `request_key: UUID` tại `backend/app/api/admission_schemas.py`, `schedule_schemas.py`, `material_schemas.py`, `result_schemas.py`, `practice_schemas.py`; upload học liệu cũng nhận UUID từ form tại `backend/app/api/routes/materials.py`. Không sửa các file này. Các quyền/tenant/audit tiếp tục do backend quyết định.
- Tách lỗi tạo khóa **trước khi gửi** khỏi lỗi mạng/5xx **sau khi gửi**. Chỉ trường hợp sau mới giữ cảnh báo “Chưa xác định kết quả” và quy tắc khóa nút/làm mới/đối chiếu dữ liệu hiện có. Không biến 409 hoặc lỗi phiên thành thông báo thành công.
- Luồng chỉnh buổi trong `SessionOperations` đang giữ một key qua preview → apply; cấu hình lịch trong `Scheduling` tạo key theo vòng đời form. Khi thay hàm, không đổi vòng đời khóa hoặc payload.

## 3. Bản đồ thay đổi

Các file ghi “sửa” và “tái sử dụng” đã xác minh tồn tại ngày 2026-10-02. File mới được ghi rõ “dự kiến tạo”.

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol hoặc trách nhiệm thay đổi | Test tương ứng |
|---|---|---|---|---|
| Tạo khóa UUID an toàn trên HTTP LAN | `frontend/src/requestKey.ts` | **Dự kiến tạo** | Hàm chung tạo UUID v4 từ Web Crypto; báo lỗi riêng khi không có nguồn ngẫu nhiên | `frontend/src/requestKey.test.ts` (**dự kiến tạo**) |
| Lỗi trước khi gửi và bản dịch | `frontend/src/i18n.ts`; `frontend/src/Admissions.tsx` | Sửa | Thông báo VI/EN khi không tạo được khóa; `BusinessForm` phân biệt lỗi trước API với kết quả mutation chưa rõ | `frontend/src/Admissions.test.tsx` |
| Tuyển sinh, tiền, điểm danh và lịch | `frontend/src/Admissions.tsx`; `frontend/src/SessionOperations.tsx`; `frontend/src/Scheduling.tsx` | Sửa | Thay lời gọi UUID trực tiếp; giữ lifecycle preview/apply và khóa theo thao tác | `frontend/src/Admissions.test.tsx`; `SessionOperations.test.tsx`; `Scheduling.test.tsx` |
| Bảo lưu/hoàn phí và kết quả | `frontend/src/EnrollmentLifecycle.tsx`; `frontend/src/Results.tsx`; `frontend/src/GradingSchemes.tsx` | Sửa | Thay lời gọi UUID trực tiếp trong preview/mutation, không đổi tính tiền hoặc công bố điểm | `frontend/src/EnrollmentLifecycle.test.tsx`; `frontend/src/Results.test.tsx`; `frontend/src/GradingSchemes.test.tsx` |
| Học liệu và bài luyện AI | `frontend/src/Materials.tsx`; `frontend/src/AIPractice.tsx` | Sửa | Thay khóa JSON/FormData và nộp đáp án, không đổi quyền truy cập/chấm/streak | `frontend/src/Materials.test.tsx`; `AIPractice.test.tsx` |
| Kiểm tra xuyên luồng | `frontend/e2e/admissions.spec.ts`; `frontend/e2e/ai-cluster.spec.ts`; `frontend/e2e/materials.spec.ts`; `frontend/e2e/results.spec.ts` | Tái sử dụng, sửa test nếu cần | Chạy một ca thực khi `randomUUID` bị vô hiệu hóa trong trang để mô phỏng capability trên HTTP LAN; giữ DB E2E tạm | Chọn spec theo rủi ro, không chạy full E2E nếu không cần |
| Bàn giao | `docs/current-state.md`; `docs/plans/frontend-uiux-rebuild.md`; `docs/test-feedback.md` | Sửa khi triển khai | Ghi kết quả, trạng thái deploy và checklist; không chép lại kế hoạch vào nhiều nơi | So thực tế và diff cuối |

## 4. Thứ tự triển khai và dependency

1. Kiểm tra diff các file trong bảng so với thời điểm lập kế hoạch và xác nhận URL hotspot còn đúng. Chạy một test hồi quy thể hiện lỗi hiện tại, đặc biệt `BusinessForm` chưa gọi API khi `randomUUID` thiếu.
2. Viết helper UUID v4 và test secure/insecure capability, đúng format/bit version/variant, tính độc lập các khóa và đường lỗi khi thiếu cả hai API.
3. Đổi toàn bộ lời gọi trực tiếp trong `frontend/src`, giữ nguyên thời điểm tạo/tái sử dụng từng key. Chỉnh hiển thị lỗi tiền gửi của `BusinessForm` và các màn liên quan khi nguồn ngẫu nhiên thật sự không có.
4. Chạy test component bị ảnh hưởng rồi E2E chọn lọc. Đo trong browser ở URL hotspot thật: `isSecureContext=false`, `randomUUID=undefined`, thao tác hợp lệ vẫn gửi đúng một mutation và hiển thị kết quả. Kiểm tra riêng lỗi mạng sau khi gửi vẫn yêu cầu đối chiếu dữ liệu.
5. Lint/build và cập nhật checkpoint. Nếu rollout, chỉ build/recreate dịch vụ `web`, đối chiếu health UI/API và để người dùng nghiệm thu trên thiết bị kết nối hotspot.

## 5. Migration/deployment, rủi ro và bảo vệ dữ liệu

- Không có migration. Không đổi `compose.yaml`, `.env`, API, DB, Mailpit hay volume. Trước khi deploy cần kiểm tra Docker thực tế; chỉ cập nhật image/container web, giữ bản web cũ làm điểm quay lại.
- Rủi ro lớn nhất là tái tạo key giữa preview/apply hoặc retry sau lỗi mạng làm nhân đôi thao tác tài chính, xếp lớp hay lịch. Test phải xác nhận key ổn định đúng vòng đời và không có retry tự động. Rủi ro khác là UUID tạo sai variant bị backend từ chối 422, hoặc sửa lỗi chung khiến lỗi mạng bị diễn giải là lỗi chưa gửi.
- HTTP qua hotspot vẫn truyền lưu lượng không mã hóa. Sửa này chỉ khắc phục khả năng tạo UUID cho môi trường thử hiện tại; HTTPS là đợt hạ tầng riêng trước khi dùng trên mạng không tin cậy.

## 6. Kiểm thử dự kiến, thư mục chạy và tiêu chí thành công

- Từ `frontend/`: `npx.cmd vitest run src/requestKey.test.ts src/Admissions.test.tsx src/SessionOperations.test.tsx src/Scheduling.test.tsx src/EnrollmentLifecycle.test.tsx src/Results.test.tsx src/GradingSchemes.test.tsx src/Materials.test.tsx src/AIPractice.test.tsx --maxWorkers=1`. Chỉ thêm module test khi dependency mới chạm tới.
- Từ `frontend/`: `npm.cmd run lint` và `npm.cmd run build` sau thay đổi. E2E dùng `SYNAPSE_E2E_PYTHON` trỏ `.venv` để không phụ thuộc cache uv; chọn `admissions.spec.ts` và một luồng học liệu/AI. Runner auth trước đó treo lúc teardown Windows, nên báo riêng kết quả ca test và exit code.
- Unit: UUID hợp lệ theo parser backend, đúng v4/variant, hai lần gọi khác nhau; fallback chạy khi `randomUUID` thiếu; thiếu cả hai API không gọi mutation. UI: lỗi trước khi gửi không còn báo “Chưa xác định kết quả”; lỗi mạng sau khi gửi vẫn chặn gửi lặp. E2E/browser: request được phát đúng một lần và không nhận 422 UUID tại HTTP hotspot, form lịch không vỡ lúc render. Không gọi provider AI tính phí.

## 7. Checklist nghiệm thu thủ công theo vai trò

- Học viên: qua thiết bị kết nối hotspot, đăng ký khóa và nộp một bài luyện đã phát hành; sau làm mới thấy kết quả, không có thao tác lặp.
- Giáo vụ/quản lý: tạo/duyệt/xếp lớp, ghi nhận khoản thu bằng dữ liệu thử được cấp riêng; kiểm tra số tiền và số bản ghi trước/sau. Thử một thao tác khi mạng ngắt sau gửi để chắc cảnh báo kết quả chưa rõ vẫn giữ nguyên.
- Giáo viên: mở chỉnh buổi, preview rồi apply với cùng dữ liệu, điểm danh/chấm điểm; khi `randomUUID` bị thiếu không vỡ trang.
- Root/quản lý học liệu: upload/gắn một tài liệu thử và đối chiếu không có bản ghi trùng. Kiểm tra `http://localhost:5173` trên máy chủ và `http://192.168.137.1:5173` trên máy khách; địa chỉ thực có thể thay đổi theo hotspot.

## 8. Quyết định còn cần người dùng trả lời

Không có quyết định chặn triển khai: đã xác định phạm vi là sửa tương thích frontend cho HTTP hotspot hiện tại, giữ API/nghiệp vụ. Việc đưa HTTPS vào môi trường dùng thật sẽ lập kế hoạch riêng khi cần.

## 9. Đề cử model và trạng thái

Đề cử model: GPT gpt-6-astra — high, vì thay khóa idempotency dùng xuyên các luồng tiền, lịch, học liệu và AI đòi kiểm tra kỹ vòng đời khóa và lỗi mạng.

- [x] Xác minh code, URL hotspot, capability browser và schema UUID backend.
- [x] Đã tạo helper UUID v4, thay mọi lời gọi trực tiếp trong `frontend/src`, phân biệt lỗi trước khi gửi với lỗi mạng chưa rõ kết quả. `SessionOperations` vẫn giữ cùng key từ preview đến apply; `Scheduling` giữ key theo vòng đời form. Không đổi backend/API/schema.
- [x] Test 2026-10-02: Vitest chọn lọc **40/40 đạt** (9 file); sau sửa bản dịch lỗi AI chạy lại `AIPractice.test.tsx` **1/1 đạt**, lint và build đạt. Một lượt AI timeout trên máy đang tải nặng, chạy lại với ngưỡng 20 giây đạt. Build vẫn cảnh báo chunk JS trên 500 kB. E2E tuyển sinh chạy trên DB SQLite tạm: đã qua gửi yêu cầu khi `randomUUID` bị vô hiệu hóa, duyệt/xếp lớp và thu tiền; chưa ghi đạt toàn ca vì locator trùng shortcut dashboard ở bước điểm danh. Locator đã sửa, lần chạy tiếp theo treo lúc khởi động runner trên Windows và được ngắt. Không chạy full backend/E2E.
- [x] Image web trước rollout được giữ tại `synapselms-web:pre-request-key-20261002`; chỉ `docker compose build web` và `up -d --no-deps --force-recreate web`. Container web cuối `b73709784fcb`; API `f55a4db43545`, DB `18c0b2202fed`, Mailpit `e1376460d909`, ClamAV `18530b2f8bda`, GC `7edf1a1b5791` giữ nguyên. UI hotspot, API health và OpenAPI đều HTTP 200. Chromium tại URL hotspot sau deploy xác nhận `secure=false`, `randomUUID=undefined`, `getRandomValues=function`, helper tạo UUID v4 `bcc3ada6-e8f3-4761-a2b5-37a856fb1187`.
- [ ] Người dùng nghiệm thu thao tác hợp lệ trên thiết bị qua hotspot: gửi yêu cầu tuyển sinh/thu tiền đúng một lần, thấy kết quả; thử lỗi mạng sau gửi vẫn yêu cầu làm mới và đối chiếu dữ liệu. Xem checklist mục 7. Không seed dữ liệu thật trong lần triển khai này.
