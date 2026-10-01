# Kế hoạch làm lại UI/UX toàn frontend SynapseLMS

Trạng thái 2026-10-01: **đang triển khai theo từng màn; dashboard đã code/test/deploy web, chờ người dùng nghiệm thu**. Người dùng ưu tiên đợt frontend này; [bộ đề AI tự động](./practice-sets-automation.md) tạm hoãn. Làm lại toàn bộ giao diện và trải nghiệm trên React/Vite hiện có, **giữ nguyên API, quyền và quy tắc nghiệp vụ backend**. `ui-design/` là ref thị giác desktop đã có trong workspace, không nhập nguyên mini project Next.js vào app. HEAD thực tế lúc chốt kế hoạch là `fbd4ab9` (`ai feature`), xuất hiện trong lúc khảo sát; không do phiên này tạo. Giữ thay đổi hiện hữu; không stage/commit, sửa `.env`, seed hoặc xóa volume.

## 1. Mục tiêu, phạm vi, phần chưa làm

Synapse Soft là thiết kế mặc định nhất quán từ đăng nhập tới màn hình nghiệp vụ. Giữ màn hình chào ngắn khi tải hồ sơ, không tạo chờ giả. Các theme Neo Pop/Clay Garden/Liquid Glass là phần thưởng học viên; thay token giao diện nhưng không làm đổi ý nghĩa nút, độ tương phản, trạng thái hay quyền. Dùng ref cho bố cục desktop, bổ sung mobile thật cho Root/quản lý/giáo vụ/giáo viên/học viên. Mọi chức năng hiện có phải tìm thấy và sử dụng được; không bỏ màn hình vì ref không vẽ nó.

Điểm kết thúc: tất cả route frontend hiện có có shell, điều hướng, form, bảng/card, loading/empty/error và responsive cùng hệ thiết kế; luồng tài chính, quyền học viên, điểm danh và AI hiện tại vẫn gọi đúng API. Test UI/E2E và nghiệm thu theo vai trò đạt; không cần migration backend. Ngoài phạm vi: đổi endpoint/DTO, viết lại logic tính tiền/quyền, thêm nghiệp vụ AI bộ đề, chuyển sang Next.js, làm app native hay tự ý thêm tính năng.

## 2. Quy tắc trải nghiệm và dữ liệu

- Giữ `frontend/src/api.ts` làm ranh giới gọi backend; không đưa quyền nghiệp vụ vào CSS/UI. Menu theo role là hỗ trợ điều hướng, server vẫn là nguồn kiểm quyền. Root support session và tenant context phải luôn hiển thị rõ.
- Design token dùng CSS variables cho màu, khoảng cách, typography, radius, focus; Synapse Soft mặc định, theme chỉ override token cho học viên đã mở khóa. Không dùng màu làm tín hiệu duy nhất. `prefers-reduced-motion`, bàn phím/focus, touch target tối thiểu 44 px, tương phản và VI/EN là gate nghiệm thu.
- Dashboard theo vai lấy dữ liệu đã có qua API; số liệu không có endpoint thì hiển thị công việc/lối tắt thật, không tạo KPI giả từ ref. Luồng loading/welcome chỉ tồn tại khi khôi phục session hoặc đọc hồ sơ đang diễn ra; lỗi có Retry/Back rõ.
- Desktop có sidebar/topbar và vùng nội dung nhất quán. Mobile dùng drawer hoặc điều hướng gọn theo vai, form một cột, bảng lớn thành card/scroll có chỉ dẫn; điểm danh giáo viên, thông báo và học liệu/AI học viên phải thuận ngón tay.
- Trạng thái tài chính, hoàn phí, công bố điểm, thu hồi tài liệu và các hành động khó đảo ngược giữ xác nhận và ngôn từ rõ; không gom nhiều bước nghiệp vụ thành nút mơ hồ chỉ để giống ref.

## 3. Bản đồ thay đổi theo file đã xác minh

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol/trách nhiệm và test |
|---|---|---|---|
| Design system và shell | `frontend/src/ui/` (dự kiến tạo); `frontend/src/styles.css`; `frontend/src/App.tsx`; `frontend/src/i18n.ts` | Tạo UI primitives/tokens; sửa shell/i18n | Button/Input/Card/Dialog/Feedback, sidebar/topbar/drawer, role dashboard, state và theme; `App.test.tsx` và test component mới |
| Auth và chào | `frontend/src/AuthExperience.tsx`; `frontend/src/auth.css`; `frontend/src/Account.tsx`; `frontend/src/AuthExperience.test.tsx` | Sửa/tái sử dụng | Đồng bộ token, login/đăng ký/quên mật khẩu/phiên, màn chào ngắn có reduced motion; test auth, E2E `frontend/e2e/auth.spec.ts` |
| Danh mục và vận hành lớp | `frontend/src/Management.tsx`; `frontend/src/Students.tsx`; `frontend/src/Teachers.tsx`; `frontend/src/Courses.tsx`; `frontend/src/Classrooms.tsx`; `frontend/src/Scheduling.tsx`; `frontend/src/SessionOperations.tsx`; `frontend/src/Invitations.tsx` | Sửa | List/detail/form, bảng/card mobile, trạng thái dữ liệu; test `.test.tsx` tương ứng và E2E hiện hữu |
| Tuyển sinh, học phí, bảo lưu, kết quả | `frontend/src/Admissions.tsx`; `frontend/src/admissions.css`; `frontend/src/EnrollmentLifecycle.tsx`; `frontend/src/Results.tsx`; `frontend/src/results.css`; `frontend/src/GradingSchemes.tsx`; `frontend/src/Proficiencies.tsx` | Sửa | Quy trình nhiều bước, tiền/trạng thái/confirm, điểm danh/gradebook, lỗi form; test `.test.tsx` và E2E liên quan |
| Học liệu và AI hiện hành | `frontend/src/Materials.tsx`; `frontend/src/materials.css`; `frontend/src/AISettings.tsx`; `frontend/src/AIPrompts.tsx`; `frontend/src/AIPractice.tsx`; `frontend/src/AIInsights.tsx`; `frontend/src/ai.css` | Sửa | Thư viện, preview/download, provider/prompt, bài luyện câu đơn hiện hành, tiến độ/theme; test `.test.tsx`, E2E materials/ai |
| Ref, kiểm tra và bàn giao | `ui-design/app/page.tsx`; `ui-design/app/globals.css`; `frontend/e2e/` ; `docs/current-state.md`; `docs/ui-ux.md`; `myplan.txt` | Ref chỉ đọc; E2E sửa/tạo khi cần; docs sửa | Đối chiếu ref, responsive/role visual QA và checkpoint. Không biến `ui-design` thành source production. |

## 4. Thứ tự triển khai và dependency

1. Chụp baseline màn hình/route và kiểm tra test đang có; định nghĩa token Synapse Soft, thành phần dùng chung, shell và nav theo vai. Không sửa hành vi API ở bước này.
2. Đồng bộ auth/welcome/dashboard Root–quản lý–giáo vụ–giáo viên–học viên; mobile shell trước khi chuyển từng page.
3. Chuyển các nhóm màn hình theo luồng liên kết: danh mục/lớp/lịch → tuyển sinh/tài chính/điểm danh → kết quả/học liệu → AI hiện hành. Mỗi nhóm hoàn tất cả desktop/mobile/VI-EN/state/test trước khi sang nhóm khác, tránh nửa trang cũ nửa trang mới quá lâu.
4. Áp theme thưởng lên token, kiểm tra focus/contrast/reduced motion; so ref PC và bản mobile tự thiết kế. Chạy E2E xuyên vai và kiểm tra thủ công ở viewport phổ biến.
5. Build/deploy riêng web sau khi các route và smoke API đạt; không deploy backend/migration. Cập nhật checkpoint và checklist nghiệm thu.

## 5. Deployment, rủi ro và bảo vệ dữ liệu

Không cần DB migration hoặc seed. Build web image, giữ API/DB/Mailpit/volume. Khả năng rollback là dùng web image cũ; trạng thái server không đổi. Rủi ro chính là đứt route, sai role/tenant context, mất hành động hiếm, hiển thị sai tiền/ngày/điểm, mobile tràn ngang, theme giảm tương phản. Dùng bản đồ route và test hành vi hiện có làm gate; không coi screenshot đẹp là đủ. `.gitignore` đã bổ sung quy tắc ignore thư mục tạm backend nhưng 48 file `.test-tmp` từng được Git theo dõi nên trạng thái `D` cần xử lý index riêng; lệnh ignore không tự xóa tracking. Không đụng các file đó hoặc stage khi làm UI.

## 6. Kiểm thử dự kiến

Từ `frontend/`: `npm.cmd test -- --run` cho component/flow đang sửa theo từng nhóm; trước bàn giao `npm.cmd run lint`, `npm.cmd run build`, rồi `npx.cmd playwright test` chọn các spec auth, role, admissions/finance, attendance/results, materials và AI. So desktop rộng 1440 px, tablet 768 px, mobile 390/320 px, keyboard-only và reduced motion. Chỉ chạy full UI suite một lần trước bàn giao nếu dependency chung đổi; không chạy full backend vì API không đổi. Kiểm tra thủ công network không xuất hiện endpoint mới, payload nghiệp vụ không thay, health web/API và smoke role sau deploy. Thành công khi 0 lỗi và tất cả route có đúng loading/empty/error/permission state.

## 7. Checklist nghiệm thu theo vai

- Root: đăng nhập/chào nhanh, chọn trung tâm, phiên hỗ trợ rõ tenant, AI settings/prompt và lối quay lại; không nhìn dữ liệu tenant khi chưa vào support.
- Quản lý/giáo vụ: tìm danh mục/lớp/lịch, tuyển sinh, thu tiền/hoàn phí, học liệu và báo cáo đúng role; xác nhận thao tác tiền rõ trên desktop/mobile.
- Giáo viên: lịch dạy, điểm danh, gradebook, học liệu và bài luyện đang có; thao tác điểm danh trên điện thoại không tràn/khó chạm.
- Học viên: đăng ký, lịch, học phí, kết quả, học liệu, thông báo và bài luyện; Synapse Soft mặc định, theme mở khóa đúng, mobile và reduced motion dùng được.
- Chung: VI/EN, tab/focus, trạng thái chờ/rỗng/lỗi, lỗi mạng/401, nhiều kích thước viewport và không mất hành động nghiệp vụ.

## 8. Quyết định đã chốt/còn mở

- **Đã chốt:** ưu tiên toàn frontend; dùng `ui-design` làm ref, Synapse Soft mặc định và theme thưởng như trước; giữ API/quy tắc nghiệp vụ, không triển khai bộ đề AI lúc này. Mobile thiết kế dựa trên PC. Không xóa hoặc stage thay đổi người dùng.
- Không còn quyết định ảnh hưởng phạm vi trước khi bắt đầu; lựa chọn chi tiết UI giải quyết trong hệ token và kiểm tra theo vai. Nếu ref mâu thuẫn với khả năng API/role hiện có, giữ nghiệp vụ và báo khác biệt khi bàn giao.

## 9. Đề cử model và trạng thái

Đề cử model: GPT gpt-6-astra — high, vì thay toàn bộ UI qua nhiều vai và luồng tài chính/quyền trong khi giữ tương thích API đòi kiểm soát hồi quy xuyên màn hình.

- [x] Kiểm tra checkpoint/git status, ref và file frontend hiện hữu; chốt UI/UX toàn bộ, giữ API/backend.
- [x] Bổ sung ignore cho thư mục test tạm mới, giữ thay đổi `.gitignore` của người dùng; chưa xử lý file tạm đã tracked.
- [x] Thiết kế Figma dashboard desktop/mobile và bộ trạng thái nút; người dùng đã yêu cầu đưa dashboard vào app.
- [x] Code dashboard trang chủ theo vai trò, mobile drawer, lối tắt và số liệu trung tâm từ API hiện hữu; không tạo KPI giả. Test App + Dashboard 20/20, lint/build đạt. Kiểm tra Chromium 1440/390 px không tràn ngang; drawer mobile mở được. Một ca E2E auth đạt phần test nhưng Playwright lỗi teardown web server trên Windows; chưa tính là cả spec đạt.
- [x] Deploy riêng web bằng `docker compose up -d --no-deps --build web`: web `b30bbdda0e07`, HTTP web/API 200; API `0fc19d0ab0fe`, DB `18c0b2202fed`, Mailpit `e1376460d909` giữ ID. Image web cũ `sha256:b03ed2d67463799923d52fe5c1f59087967a3e0bb56017b91cd5c7b4b0d94f0b` là điểm rollback.
- [ ] Người dùng nghiệm thu dashboard trên app. Màn đăng nhập mới chỉ là Figma, chưa code. Tiếp tục các nhóm UI còn lại theo mục 4.
