# Kế hoạch: đăng nhập, đăng ký và màn hình chào Synapse Soft

Ngày2026-09-28. **Đã được duyệt, code/test và deploy web lúc23:23+07:00; chờ người dùng nghiệm thu giao diện.** Người dùng chọn Synapse Soft mặc định, các theme khác là phần thưởng chuỗi ngày làm bài tập AI; giữ màn chào nhanh khi tải và bổ sung mobile từ bản PC.
Đề cử model: GPT gpt-6-astra — high. Giữ lựa chọn đã thống nhất; đợt này cần phối hợp trạng thái xác thực bất đồng bộ, các đường dẫn email, accessibility và hồi quy nhiều vai trò.

## 1. Mục tiêu, phạm vi và đánh giá backend

Mục tiêu: làm mới trọn luồng vào ứng dụng bằng nhận diện Synapse Soft: đăng nhập → tải phiên/hồ sơ → chào ngắn → vào đúng trang/quyền; đăng ký học viên → thông báo thành công → đăng nhập. Desktop/mobile Việt–Anh, light/dark, bàn phím và reduced motion đều sử dụng được.

Đánh giá có giới hạn trước kế hoạch:
- Git còn thay đổi0014 và tài liệu của người dùng; không stage/commit. Manifest source đã test0014 đối chiếu hiện tại không khác. Docker API/web chạy, DB/Mailpit healthy, Alembic20260928_0014(head), health ok. OpenAPI có20 path auth/public-organizations/invitation, không test helpers.
- Đọc trực tiếp auth.register/login/me, router, luồng frontend App/api/Account/Invitations/useEmailLink và test liên quan. API đăng ký luôn tạo student; vai trò Root/membership và tenant_available do server trả; khôi phục phiên/email/lời mời đã có.
- **Chưa tìm thấy backend blocker buộc làm trước việc đổi UI này.** Đây không phải kiểm toán toàn bộ backend hay chứng nhận mọi nghiệp vụ đã đầy đủ. Không chạy test trong phiên lập kế hoạch.
- Đợt0014 đã code/test/deploy, **chưa được người dùng nghiệm thu**; checklist vẫn ở [kế hoạch0014 mục7](./reservation-refund.md). Lỗi tiền/quyền/migration được báo trong nghiệm thu phải ưu tiên sửa trước rollout UI.
- Đợt0013 đã được nghiệm thu; đồng bộ19 story Jira cũ còn riêng, không đổi Jira trong phiên này.

| Nghiệp vụ backend còn thiếu | Đánh giá ưu tiên | Có chặn đợt UI này? |
| --- | --- | --- |
| Bài kiểm tra/đầu điểm/trọng số/nhập điểm/tổng kết | Quan trọng cho LMS dạy và đánh giá thực tế; RES-01..04 là P0 trong backlog, nên là đợt nghiệp vụ tiếp theo sau UI nhỏ này | Không, nếu chưa cần vận hành chấm điểm ngay |
| Bài tập AI, bài làm và xác nhận hoàn thành | Nền bắt buộc trước phần thưởng chuỗi ngày; AI chưa có router triển khai | Không; không giả lập streak/theme unlock trong UI |
| Chuỗi ngày và quyền sở hữu theme | Cần server xác nhận bài làm, quy tắc ngày/múi giờ, chống ghi nhận trùng và lưu phần thưởng | Không; lập kế hoạch riêng cùng nền bài tập |
| Chuyển lớp/học lại/hoàn thành enrollment | Còn thiếu, tách khỏi0014; chỉ trở thành ưu tiên ngay khi trung tâm cần xử lý thật | Không liên quan xác thực |
| Sửa sai quyết toán hoàn đã duyệt; báo cáo công nợ/doanh thu | Quan trọng khi vận hành tài chính mở rộng;0014 đã công bố giới hạn, không được sửa SQL thủ công thay quy trình | Không có yêu cầu/lỗi thực tế đang buộc chặn UI |

Phạm vi:
- Đăng nhập, đăng ký và bootstrap/chào chuyển tiếp.
- Vỏ giao diện đồng nhất cho quên mật khẩu, reset/verify email, nhận lời mời vì đây là các nhánh trực tiếp của luồng vào ứng dụng; tái sử dụng logic hiện hữu.
- Mobile320/390/768px và desktop1280/1440px; nền/typography/CTA/focus/trạng thái loading/error được chuẩn hóa trong phạm vi auth.

Chưa làm: đổi toàn sidebar/dashboard/bảng/lịch/tài chính; ứng dụng bốn theme toàn hệ thống; selector theme/phần thưởng/streak/AI; chọn vai trò tự do, SSO, nhớ đăng nhập có thời hạn mới; thay backend/RBAC/cookie/token; tạo dashboard số liệu mới. Không cài/chuyển sang Next.js, Tailwind hoặc bộ dependency của mini project chỉ để lấy diện mạo.

Điểm kết thúc: các luồng auth thật hoạt động trong vỏ mới, không lộ màn hình sai quyền hoặc mất email token; kiểm thử/ảnh desktop-mobile-light-dark đạt; chỉ web được cập nhật nếu triển khai được duyệt. Người dùng nghiệm thu riêng.

## 2. Thiết kế, quy tắc nghiệp vụ, quyền và API

### 2.1 Hình thức và mobile

- Tham chiếu ui-design/app/page.tsx: Brand, LoginScreen, WelcomeScreen; ui-design/app/globals.css: màu Soft, auth-layout/visual-orbit/visual-core. Giữ nhịp bo góc, khoảng trắng, vùng minh họa và form; sửa chữ thương hiệu thành SynapseLMS và biểu tượng S thống nhất.
- Desktop từ1024px: hai vùng, minh họa bên trái khoảng45%, form bên phải; form rộng khoảng420–480px. Brand và đổi ngôn ngữ rõ ràng; đăng ký cao hơn được cuộn tự nhiên, không ép vừa một màn.
- Tablet/mobile dưới1024px: một cột, brand/đổi ngôn ngữ trên cùng, minh họa thu thành dấu hiệu nhận diện nhỏ; ưu tiên form trong vùng nhìn đầu. Padding16–24px, control cao ít nhất44px; không khóa chiều cao/overflow khiến bàn phím che CTA; dùng viewport động có fallback, safe-area và cuộn dọc.
- Soft là diện mạo mặc định của các màn auth. Light/dark theo hệ điều hành hiện có, dùng token CSS có phạm vi .auth-experience; không đổi màu toàn dashboard. Kiểm tra độ tương phản chữ/nút, không dùng chữ trắng nhỏ trên nền teal quá sáng chỉ vì ref dùng vậy.
- Minh họa bằng CSS/SVG cục bộ, không nhúng analytics/font/video ngoài, không autoplay âm thanh. Chuyển động nhẹ, không nhấp nháy; reduced-motion chuyển sang hình tĩnh/fade tối thiểu. Hướng dẫn và lỗi ngắn, phù hợp cả người dùng nhỏ tuổi lẫn nhân sự.
- Theme thưởng sau này chỉ đổi thẩm mỹ; light/dark, tương phản dễ đọc và giảm chuyển động là khả năng sử dụng cơ bản, không khóa bằng thành tích. Chưa định ngưỡng ngày hoặc tạo thông báo “đã mở khóa” trong đợt này.

### 2.2 Đăng nhập và đăng ký

- Một form email/mật khẩu cho mọi vai trò. Không gửi role từ client; sau xác thực đọc Profile qua /auth/me. Root không tự vào tenant và không tự mở support; không có membership/tenant_available=false thì giữ quyền hạn hiện tại, không gán student mặc định cho thông điệp chào.
- Giữ password manager/autocomplete, paste, type=email; bổ sung hiện/ẩn mật khẩu có nhãn và trạng thái rõ. Không lưu mật khẩu/token vào localStorage, URL hoặc log.
- Đăng ký công khai chỉ cho học viên. Họ tên/email/mật khẩu, xác nhận mật khẩu ở client; trung tâm công khai **hoặc** mã mời đăng ký trung tâm. Giữ validation backend (mật khẩu12..128, không áp min12 lên login tài khoản cũ).
- Không nhầm mã mời đăng ký với link email membership-invitation. Vai trò giáo viên/giáo vụ/quản lý được cấp bởi các luồng quản trị/lời mời hiện có.
- Danh sách trung tâm có loading/rỗng/lỗi/retry GET riêng, không coi lỗi tải là “không có trung tâm”. Đổi phương thức chọn trung tâm/mã mời không gửi cả hai.
- Sau201 đăng ký: về đăng nhập và báo đã tạo tài khoản/hướng dẫn kiểm tra email theo hợp đồng hiện có; không tự đăng nhập hoặc báo đã xác minh email.
- Busy chặn double submit và đổi màn khi đang gửi. Lỗi thông tin đăng nhập dùng thông báo chung; không thêm kiểm tra email tồn tại. Đăng ký/email có kết quả chưa rõ do mất mạng không tự gửi POST lại.

### 2.3 Màn hình chào gắn với tải thật

Phân biệt khôi phục phiên khi mở trang, gửi login, tải /auth/me và đã sẵn sàng:
- Bootstrap chờ khoảng120–150ms mới hiện loading có nhận diện để tránh chớp trên máy nhanh. Khách chưa đăng nhập đi thẳng vào form khi nhận401; không giả chào Admin.
- Khi người dùng bấm đăng nhập: hiển thị trạng thái đang xác thực thật, sau login thành công chuyển sang tải hồ sơ. Chỉ hiện tên/vai trò/trung tâm khi server đã trả Profile. Nội dung trung tính trước đó: “Đang chuẩn bị không gian học tập”.
- Khi sẵn sàng, chuyển vào trang hiện có bằng fade khoảng150–250ms; không cố giữ splash1–2giây, không chờ một bộ đếm giả chạy đủ100%. Không phát lại welcome mỗi lần đổi route hoặc refresh access token nền.
- Giữ quỹ đạo/logo mềm từ ref; bỏ chữ kiểu ENCRYPTION VERIFIED/SYNC % nếu không có sự kiện thật. aria-live chỉ thông báo đổi trạng thái, không đọc từng frame chữ xáo trộn.
- Chờ lâu hơn5giây có thông báo kết nối chậm; mốc15giây cho trạng thái có thể phục hồi/thử lại việc đọc phiên rõ ràng thay vì spinner vô hạn. Không timeout rồi tự POST login/register lần nữa. Nếu retry read trong khi request cũ còn về, dùng generation/cancellation guard để response cũ không ghi đè hoặc đưa tài khoản đã logout vào app.
- Khi logout, tài khoản bị thu hồi hoặc nhận synapse-signed-out: hủy timer/transition đang chờ và xóa profile/support qua luồng cũ. StrictMode mount/unmount không tạo timer lặp hoặc thêm mutation.
- Deep link /account/accept-invitation, /account/verify-email, /account/reset-password được nhận diện trước welcome chung. Không thay/unmount thành phần đang giữ email token để chạy animation; useEmailLink tiếp tục đọc rồi xóa fragment khỏi URL, xác nhận nghiệp vụ vẫn phải do người dùng.
- Không thêm điều hướng sau login làm mất đường dẫn hiện tại; giữ BrowserRouter/Route guard và màn đích hiện có.

### 2.4 API/dữ liệu

Tái sử dụng signIn, api, clearSession, Profile/Organization; GET /auth/me, GET /organizations/public, POST /auth/login/register/refresh/logout, các endpoint email/lời mời hiện có. Không thay DTO backend, thời hạn cookie, storage, khóa refresh đa tab, idempotency hay quy tắc support. Không migration hoặc dữ liệu mới. Backend chỉ mở thêm nếu trong triển khai xuất hiện lỗi hợp đồng thật; thay nghiệp vụ đáng kể phải hỏi lại.

## 3. Bản đồ thay đổi đã xác minh

File hiện hữu đã kiểm tra trực tiếp. Mọi symbol trong hàng Tạo là đề xuất, **chưa tồn tại**.

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol hoặc trách nhiệm | Test tương ứng |
| --- | --- | --- | --- | --- |
| Điều phối auth và trạng thái tải/chào | frontend/src/App.tsx | Sửa | App, authenticate, loading/busy/profile/registering/recovering, effects bootstrap và signedOut; giữ route guard | App.test.tsx; auth.spec.ts |
| Vỏ và form đăng nhập/đăng ký/chào | frontend/src/AuthExperience.tsx | **Dự kiến tạo** | AuthLayout, AuthForm, AuthWelcome: component dự kiến; trình bày và callback, không nhân đôi token client | AuthExperience.test.tsx dự kiến; App.test.tsx |
| Token màu/typography/motion/mobile | frontend/src/auth.css | **Dự kiến tạo** | CSS scoped auth-experience, Soft light/dark, reduced-motion, breakpoint/keyboard layout | UI mới; ảnh E2E |
| Tránh CSS cũ ảnh hưởng auth mới | frontend/src/styles.css | Sửa có giới hạn | Quy tắc auth-page/auth-card và selectors chung va chạm; không restyle dashboard | App/Account/Invitations UI; E2E auth/account/invitations |
| Bản dịch | frontend/src/i18n.ts | Sửa | translate/errorMessage, chuỗi loading/chào/chọn trung tâm/mật khẩu Việt–Anh | UI mới và App.test.tsx |
| Luồng quên/reset/verify | frontend/src/Account.tsx | Tái sử dụng; sửa markup nếu cần | EmailRequestForm, AccountAction; chỉ vỏ/nhãn/focus, giữ explicit submit | Account.test.tsx; account.spec.ts |
| Luồng nhận lời mời | frontend/src/Invitations.tsx | Tái sử dụng; sửa markup nếu cần | InvitationAcceptance, AcceptInvitation; giữ wrongAccount/restoring/preview/confirm | Invitations.test.tsx; invitations.spec.ts |
| Token email và auth transport | frontend/src/useEmailLink.ts; frontend/src/api.ts | Tái sử dụng | useEmailLink; api/signIn/signOut/clearSession/Profile, refresh lock và BroadcastChannel | Hồi quy qua App/Account/Invitations và E2E |
| Kiểm thử trạng thái auth | frontend/src/App.test.tsx | Sửa | Bootstrap401/lỗi/chậm, login/me, logout-race, role/deep link/StrictMode | Vitest |
| Kiểm thử trình bày/motion | frontend/src/AuthExperience.test.tsx | **Dự kiến tạo** | Confirmation mismatch, reveal password, loading/empty/error centers, timer cleanup/reduced motion | Vitest |
| Hồi quy nhánh email | frontend/src/Account.test.tsx; frontend/src/Invitations.test.tsx | Sửa khi markup/props đổi | Giữ token/explicit confirm/sai tài khoản sau đổi layout | Vitest |
| E2E chính | frontend/e2e/auth.spec.ts | Sửa | Luồng register/login/reload/password/logout hiện có; thêm chào/tải lỗi/role/mobile/light-dark/keyboard | Playwright |
| E2E email/lời mời | frontend/e2e/account.spec.ts; frontend/e2e/invitations.spec.ts | Tái sử dụng; sửa locator nếu cần | Khôi phục/verify/sessions và nhận lời mời, không thêm seed thật | Playwright |
| Môi trường và API thật | frontend/playwright.config.ts; backend/tests/e2e_server.py; backend/app/api/routes/auth.py; backend/app/api/routes/account.py; backend/app/api/routes/membership_invitations.py | Tái sử dụng | E2E8011/5180, endpoint/auth contract; không đổi theo thiết kế này | Bộ E2E kể trên |
| Ref thẩm mỹ | ui-design/app/page.tsx; ui-design/app/globals.css | Tham chiếu | Brand/LoginScreen/WelcomeScreen và CSS Soft, không sửa mini project | So hình desktop/mobile |
| Bàn giao | docs/plans/auth-soft-experience.md; docs/current-state.md; docs/auth-operations.md; myplan.txt | Sửa tài liệu | Kế hoạch/kết quả, checklist, quyết định; không nhân bản handoff | diff/link review |

Không dự kiến sửa package.json/lock, main.tsx hoặc Playwright config. Nếu cần import CSS, đặt trong component mới hoặc App; không cài thư viện animation cho chuyển động CSS đơn giản.

## 4. Thứ tự và dependency

1. Khi được duyệt: git status và đối chiếu baseline mục10; đọc diff file thay đổi, kiểm tra phản hồi nghiệm thu0014. Không khảo sát lại toàn repo.
2. Tạo AuthLayout/Form/Welcome và CSS Soft có phạm vi riêng, chốt bố cục desktop/mobile, light/dark trước khi nối state.
3. Nối App với state tải thật và giữ login/register/API cũ; thêm guard timer/request/logout và màn trung tâm loading/error.
4. Áp vỏ auth cho Account/Invitation; bảo vệ deep links/token trong bộ nhớ. Bổ sung dịch/nhãn/focus.
5. Chạy UI mục tiêu trong lúc code; sau ổn định chạy hồi quy frontend + ba E2E auth/account/invitations. Xem ảnh mobile/desktop và thử keyboard/reduced-motion.
6. Chỉ khi được duyệt triển khai: build/update riêng web, health và đối chiếu source; chốt tài liệu/test/giới hạn. Người dùng nghiệm thu; không tự Done Jira.

## 5. Migration/deployment, rủi ro và bảo vệ dữ liệu

Không migration/API deployment theo phạm vi này. Khi triển khai được duyệt, chạy từ gốc:
~~~powershell
docker compose build web
docker compose up -d --no-deps web
~~~
Giữ API/DB/Mailpit/volume/compose/.env và thay đổi người dùng. Không seed DB thật, stage/commit hoặc subagent. Ghi image web trước/sau để có đường quay lại giao diện cũ, không rollback DB0014.

Rủi ro chính: splash che lỗi/chặn deep link, callback cũ khôi phục tài khoản đã logout, form gửi trùng, mất fragment token sau unmount, CSS global ảnh hưởng nghiệp vụ, dark select khó đọc, bàn phím mobile che thao tác. Test tương ứng ở mục6. BUG-004 vẫn hoãn toàn hệ thống; riêng select chọn trung tâm trong auth phải đọc được sáng/tối và bàn phím, không tuyên bố sửa mọi native popup.

## 6. Kiểm thử dự kiến và tiêu chí thành công

Tại frontend, trong lúc code:
~~~powershell
npm.cmd exec -- vitest run src/App.test.tsx src/AuthExperience.test.tsx src/Account.test.tsx src/Invitations.test.tsx
~~~
AuthExperience.test.tsx là file dự kiến tạo. Trước bàn giao:
~~~powershell
npm.cmd run test -- --reporter=json --outputFile=../backend/test-results/auth-soft-ui.json
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e -- e2e/auth.spec.ts e2e/account.spec.ts e2e/invitations.spec.ts
~~~
Dùng thư mục báo cáo backend/test-results đã gitignore, không tạo thêm file report vào index. Từ gốc: git -c core.safecrlf=false diff --check. Không chạy full backend nếu backend/dependency/config không đổi; nếu sửa auth API ngoài dự kiến thì test file backend bị ảnh hưởng và PostgreSQL khi động tới quyền/transaction/concurrency.

Ma trận:
- Login thành công cho student/teacher/staff/manager/Root; quyền lấy từ /auth/me, không tự chọn role/tenant. Membership thiếu/tenant unavailable không có CTA vượt quyền.
- Sai mật khẩu/401,429,lỗi mạng; login thành công nhưng me lỗi; bootstrap phiên hết hạn; phản hồi chậm/đảo thứ tự; double click và logout khi welcome đang chờ.
- Register public/invite-code, center loading/rỗng/lỗi/đóng nhận sau khi form mở, mật khẩu không khớp, email trùng,201 quay lại login; không tự retry POST.
- Link reset/verify/invitation còn fragment và sau scrub, link khác mở cùng tab, token hết hạn/sai account, chỉ mở link không tự xác nhận.
- Timer bằng fake timers + deferred promises; reduced-motion, StrictMode cleanup; không có khoảng chờ giả kéo dài sau khi dữ liệu sẵn sàng.
- E2E giữ refresh cookie HttpOnly, không lưu token/password; reload/logout đa tab và support workflow không đổi. Giả lập chậm/lỗi qua Playwright route trên môi trường test, không sửa server thật.
- 320/390/768/1280/1440px, Việt/Anh, light/dark, focus visible/Tab/Enter, show-password, zoom200%, không tràn ngang hoặc mất CTA; kiểm tra trạng thái bàn phím mobile thủ công nếu browser emulation không mô phỏng đầy đủ. Ảnh screenshot không đủ chứng nhận popup native.
- Các màn đã đăng nhập/thu tiền/hoàn phí không đổi layout do CSS; kiểm tra hồi quy UI toàn frontend. Nếu CSS chung thực sự ảnh hưởng chúng, bổ sung E2E admissions; không mở full E2E theo thói quen.

Đạt khi không lỗi bộ đã chọn, không bỏ qua ca auth quan trọng; animation không là điều kiện xác thực, không có mutation mới lúc mount; các trạng thái lỗi đều có đường xử lý rõ. Lưu thời điểm/report/source hash và phân biệt đã test/đã deploy/người dùng đã nghiệm thu.

## 7. Checklist nghiệm thu thủ công theo vai trò

- Khách/học viên: đăng ký bằng trung tâm công khai hoặc mã mời; lỗi rõ và thành công quay về login. Đăng nhập không chọn vai; chào nhanh đúng tên sau khi xác thực; lịch/học phí vẫn của mình.
- Giáo viên/giáo vụ/quản lý: đăng nhập cùng form, menu/quyền cũ đúng; chưa có phần thưởng/theme selector giả.
- Root: vào tài khoản hệ thống, không tự mở hỗ trợ trung tâm; mở/kết thúc support như trước.
- Người nhận email: reset/verify/nhận lời mời giữ nguyên xác nhận, sai tài khoản phải xử lý đúng; welcome không nuốt link hoặc hiện token.
- Mọi vai trò: Việt/Anh, light/dark, desktop/mobile; bàn phím và password manager; mạng chậm/mất mạng; refresh/logout/tab khác; reduced-motion không có hiệu ứng gây xao nhãng.
- Riêng0014: vẫn nghiệm thu tiền/bảo lưu theo kế hoạch0014; kết quả UI auth không thay xác nhận nghiệp vụ đó.

## 8. Quyết định và phần còn cần trả lời

Đã chốt: Synapse Soft mặc định; theme khác thưởng chuỗi ngày AI; giữ chào nhanh trong lúc load; thiết kế mobile từ PC; một form login và role do server quyết định.

Không có câu hỏi phạm vi bắt buộc để hoàn thiện kế hoạch này. Các ngưỡng ngày, mất/giữ streak, múi giờ, cách tính bài đạt, theme nào ở mốc nào và quyền giữ phần thưởng khi đổi trung tâm sẽ chốt trong đợt bài tập AI, không hỏi hoặc tự quyết trước trong đợt auth.

Người dùng đã duyệt triển khai và báo test nhanh nghiệp vụ0014 chưa có vấn đề. Đây là xác nhận test nhanh, chưa thay cho nghiệm thu đầy đủ checklist0014.

## 9. Trạng thái thực thi

- [x] Đọc current-state, git status, Docker/revision/health và nguồn auth/ref liên quan.
- [x] Đánh giá backend có giới hạn, tách các nghiệp vụ thiếu khỏi blocker.
- [x] Lưu kế hoạch đủ bản đồ/test/mobile/checklist.
- [x] Người dùng duyệt triển khai.
- [x] Code/test đợt auth.
- [x] Deploy web và bàn giao.
- [ ] Người dùng nghiệm thu.

### Kết quả triển khai2026-09-28

- Trước code,22 SHA256 mục10 khớp. Bổ sung `frontend/src/AuthExperience.tsx`, `auth.css`, `AuthExperience.test.tsx`; sửa App/App.test/i18n và E2E auth. E2E courses thêm xác nhận mật khẩu vì dùng chung đăng ký. CSS giới hạn trong auth; không sửa styles.css, Account/Invitations/useEmailLink/api hoặc dependency. App chỉ bọc các nhánh email trong AuthLayout, giữ logic/token hiện hữu.
- Synapse Soft có desktop hai cột/mobile một cột, Việt–Anh, light/dark theo hệ thống, focus và reduced motion. Đăng ký có xác nhận mật khẩu, tải/lỗi/rỗng trung tâm và thử lại; mã mời là nhánh riêng. Login chung, vai trò lấy từ hồ sơ backend.
- Welcome bám tải phiên thật, trễ140ms chống nhấp nháy, báo chậm sau5s và cho thử lại đọc hồ sơ sau15s; không tự gửi lại login/register. Chặn submit trùng, bỏ response cũ khi logout/đọc lại, giữ trang yêu cầu và đường dẫn email. Tên/vai trò chỉ hiện sau khi có hồ sơ server.
- Full UI **97 đạt,0 lỗi,0 pending**, báo cáo `backend/test-results/auth-soft-ui.json` lúc23:20:59+07. Lint và build đạt. Test mới bao gồm response đến muộn, StrictMode, logout khi đang login, retry GET, link reset/language, bảy trạng thái vai trò/tenant và timers/reduced motion.
- **10 E2E riêng biệt đạt** (auth4/account2/invitations2/courses2),43.3s. Chạy lại auth4 đạt15.8s sau sửa assertion chờ welcome hết trễ trước chụp ảnh; không cộng thành14. Lệnh từ `frontend`: `npm.cmd run test:e2e -- e2e/auth.spec.ts e2e/account.spec.ts e2e/invitations.spec.ts e2e/courses.spec.ts`. E2E dùng API8011/web5180 và SQLite tách biệt.
- Đã xem ảnh login desktop1440 light/mobile390 dark, register mobile dark và welcome tại `frontend/test-results/`. Test layout320/390/768/1280/1440, hai chế độ màu, bàn phím và reduced motion. Chưa kiểm tra bàn phím mềm trên điện thoại thật hoặc zoom trình duyệt200% thực; viewport640 chỉ mô phỏng không gian layout thu hẹp. Native select Chrome vẫn thuộc BUG-004 chưa chốt toàn hệ thống.
- Không thay backend/config/dependency nên không chạy lại backend suite;225 đạt/26skip của0014 vẫn là kết quả lịch sử trong phạm vi đó. Không dùng test auth để chứng nhận lại tài chính/migration.

### Deployment và bàn giao

- `docker compose build web` và `docker compose up -d --no-deps web` đạt. Web mới lúc23:23:01+07, image `sha256:80139cd403644f6ec57a0e21db72572aaf56422bdc49d245037daeee15b40260`; image trước `sha256:0e0703090a8bb2204c6d3f0f8a9735624673b21fa4f232f58d63e2eb05c02bf5`.
- Web5173, module AuthExperience/auth.css, API health8000 và Mailpit8025 đều HTTP200; Alembic vẫn `20260928_0014 (head)`. API/DB/Mailpit giữ nguyên container ID/StartedAt; không chạy migration hoặc sửa dữ liệu. Giữ compose/.env/volume.
- SHA256 nguồn web trong image đối chiếu workspace qua `backend/test-results/auth-soft-deployed-web.json`; manifest nguồn UI/test hiện tại `backend/test-results/auth-soft-source-manifest.json`. Hash chuẩn hóa CRLF về LF. Báo cáo và ảnh bị gitignore, không chứa seed dữ liệu thật.
- Kiểm tra lại ngày2026-09-30 sau Docker Desktop restart: DB container giữ nguyên ID/image/volume nhưng bị mất endpoint network compose, khiến health nông200 còn endpoint dùng DB500. Đã nối lại chính container vào `synapselms_default` với alias `db`, không recreate hoặc sửa compose. DNS, `organizations/public` HTTP200 và Alembic0014(head) đã xác minh lại; xem chi tiết vận hành tại `docs/current-state.md`.
- Không stage/commit hoặc đổi Jira. Trong phiên người dùng đã commit phần trước: HEAD hiện tại `7d1df97b81c8b7e116528032d1afa37d65aab007`; các thay đổi auth vẫn ở working tree. Không can thiệp index của người dùng.
- Tiếp theo: người dùng mở http://localhost:5173, đăng xuất hoặc dùng cửa sổ riêng để nghiệm thu mục7; ưu tiên thiết bị mobile thật, mạng chậm, nhánh email và từng vai trò. Chưa có xác nhận nghiệm thu UI. Theme thưởng/streak/AI và đổi dashboard vẫn ngoài phạm vi.

## 10. Baseline file trước triển khai

SHA256 raw bytes, ngày2026-09-28; kiểm tra lại trước code. File dự kiến tạo chưa có hash. Manifest0014 tại backend/test-results/reservation-source-manifest.json đã đối chiếu không khác (manifest đó chuẩn hóa LF, không so trực tiếp digest raw dưới đây).

| File | SHA256 |
| --- | --- |
| frontend/src/App.tsx | ab99d609d3247ccce29a735955ab5c999f317b1c094bac6a0fce92df4394efdc |
| frontend/src/App.test.tsx | 31a483064a0d714a399e9f5988ea0d6ed190b8935778566f5f39eed84b56a7f9 |
| frontend/src/styles.css | 6387f18d0fbf47b2f824229e469d222aaa3a7b22f6cb2bb0b53e219ac5701770 |
| frontend/src/i18n.ts | ece4090e6f0450b4493e9b2e4d7034cdb125f68016f8fbc54ebd8044d5e17d18 |
| frontend/src/api.ts | 7c14d5055fe399819e1cbc4b9b8cbb61b3f2e27463fc68a2c50aa3f0b7bb3b78 |
| frontend/src/Account.tsx | 4b81515dc95b1d9826a2c5e9956f107e4095bb08744755b1f7a881c43b2daf2a |
| frontend/src/Account.test.tsx | 3e1f4375550a076da0825cf87e4c15638999ec6c3c9de5393f753c676337a108 |
| frontend/src/Invitations.tsx | 5051e7d8157174523431b92762423f77a99df844e9bc5a2e07df261a7ded4a3d |
| frontend/src/Invitations.test.tsx | 6bab18e6cb8e81b579ea53834c6144caed63c5b847185fe2988d64e607aa4db4 |
| frontend/src/useEmailLink.ts | a35d8f26bfd6e672b2de84c19284c5ceeff2d76cc91958df167b425b281c5869 |
| frontend/e2e/auth.spec.ts | 9032c0d72d995bf4825a1bc0c216d4ed59d29f8915bf58f8cd81f672493f20df |
| frontend/e2e/account.spec.ts | 9fb004018c9cff4efea4202fdb2fa6fd48afb94ec5c0fae7c05ac500b133d315 |
| frontend/e2e/invitations.spec.ts | fd6e4c844b9483a2acbfc09aa46bde089cdfc9cd9d0b4268181438f218d5fac9 |
| frontend/playwright.config.ts | beee5a9a6a8b6da58e37b94af67c2c51098a6dd4e93dc8f75b2d1166d2ff2fda |
| frontend/package.json | db626cf53278ed9cb7d307dbea370422300a2a37977aa14116ed0deb931d7926 |
| frontend/package-lock.json | 9fe1ae0b9e2167d7ab0cabdc3f13805c4e26947d302bc03e88512c4dbb37f357 |
| backend/app/api/routes/auth.py | 2bbf08cb7a3b205341ea20f69a4956f0a896370148cb9bc4740d37a17f70ae51 |
| backend/app/api/routes/account.py | 1a6a3ff3ae2079d760d6b3beb677cdba0919a149d42db0557a1f45200fd8db87 |
| backend/app/api/routes/membership_invitations.py | 8cf161ecf3f110c8a1a77d6261ec61d63451684adae70d85e82d03b099dc20ce |
| backend/tests/e2e_server.py | 0f86e9779b86067cef48bb4422e87b2a1fbaa44dae00a5785c64d810e25f61a5 |
| ui-design/app/page.tsx | 641c320ec3057ade8951e88cc7569bb65dec9cb3e8600e9c02bb751560092d09 |
| ui-design/app/globals.css | 36d66e7c08e96e7416de82eee758d39886d576e1390edb0524986ac456e25c5d |
