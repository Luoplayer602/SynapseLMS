# Ghi nhận trong quá trình nghiệm thu

Người dùng đã xác nhận “tất cả đều ổn” sau bản bàn giao hồ sơ/theme ngày 2026-09-24. BUG-001, BUG-002 và UX-001 được ghi nhận đã nghiệm thu; các mô tả bên dưới giữ lại lịch sử tái hiện và xử lý.

Cập nhật: người dùng phản hồi “test ok” với luồng vừa bàn giao. Đây là xác nhận tổng quát, không suy diễn rằng mọi ca trong checklist đã được chạy riêng.

## BUG-001 — Nhãn tên trong form Thêm trung tâm

- Trạng thái: đã sửa bằng khóa `centerName` riêng, E2E kiểm tra nhãn Việt/Anh đạt; chờ nghiệm thu.
- Người dùng báo form hiển thị: “Thêm trung tâm” → “Họ và tên” → “Mã trung tâm”.
- Mong đợi: trường tên trung tâm phải có nhãn “Tên trung tâm”, không phải “Họ và tên”.
- Vị trí: `frontend/src/Management.tsx`, component `Centers`, form tạo trung tâm dùng `t('name')`; bản dịch dùng chung trong `frontend/src/i18n.ts`.
- Hướng sửa dự kiến: thêm khóa dịch riêng cho tên trung tâm (Việt/Anh), chỉ đổi nhãn ở form trung tâm; giữ nhãn họ tên ở form tài khoản/thành viên.
- Nghiệm thu sau sửa: form trung tâm hiển thị đúng nhãn ở cả hai ngôn ngữ; form thông tin người dùng vẫn giữ nhãn phù hợp; tạo trung tâm không đổi hành vi.

## UX-001 — Root chưa thấy tính năng Lời mời thành viên

- Trạng thái: đã thêm hướng dẫn mở phiên hỗ trợ trên màn hình Trung tâm; E2E xác nhận Root chưa hỗ trợ không có mục lời mời. Không thay đổi quyền.
- Người dùng đang test bằng tài khoản được cho là Root, chưa thấy tính năng mới.
- Hành vi trong mã nguồn: sidebar chỉ hiện Lời mời thành viên khi là quản lý trung tâm có tenant hoạt động hoặc đã mở phiên hỗ trợ trung tâm. Đăng nhập Root đơn thuần chưa đủ; đây là giới hạn tenant đã thiết kế, không tự kết luận lỗi phân quyền.
- Cách thử: Trung tâm → chọn trung tâm đang hoạt động → nhập lý do → mở phiên hỗ trợ → kiểm tra mục Lời mời thành viên trong sidebar.
- Vị trí: `frontend/src/App.tsx` (điều kiện `manager || support`), `frontend/src/Management.tsx` (mở phiên hỗ trợ).
- Cần kiểm tra thêm nếu đã mở hỗ trợ mà vẫn không thấy: banner trung tâm hỗ trợ, thông báo lỗi và phiên bản giao diện đang tải. Không thay đổi quyền hoặc tự mở phiên thay người dùng trong lúc ghi nhận.
- Đề xuất UX chờ duyệt: giải thích trên màn hình Root rằng tính năng theo trung tâm xuất hiện sau khi mở phiên hỗ trợ; không bỏ yêu cầu phiên hỗ trợ.

## BUG-002 — Nút đổi ngôn ngữ và đăng xuất khó đọc trong chế độ tối

- Trạng thái: đã tái hiện bằng computed style (chữ nút đen, màu chữ kế thừa trắng), sửa màu nút theo theme; E2E sáng/tối ở 1280px/390px, focus bàn phím và ảnh kiểm tra mobile đạt. Chờ người dùng nghiệm thu; chưa tuyên bố audit khả năng tiếp cận toàn website.
- Hiện tượng: nền trang tối nhưng chữ ở nút đổi ngôn ngữ và đăng xuất vẫn đen, khó nhìn.
- Vị trí cần kiểm tra: `frontend/src/styles.css`, quy tắc `button`, `.topbar button` và `@media (prefers-color-scheme: dark)`; các nút trong `frontend/src/App.tsx`.
- Dấu hiệu trong mã nguồn: root đổi màu chữ theo chế độ tối, nhưng nút chưa khai báo màu chữ theo theme; `.topbar button` dùng nền trong suốt. Cần tái hiện để xác nhận computed style trước khi sửa.
- Hướng sửa dự kiến: định nghĩa màu chữ/nền/viền nút theo theme, giữ màu riêng cho nút primary; kiểm tra normal, hover, focus và disabled. Không chỉ sửa riêng một nhãn.
- Nghiệm thu: cả hai nút đọc rõ trong sáng/tối, Việt/Anh, desktop/mobile; thao tác đổi ngôn ngữ và đăng xuất vẫn đúng; kiểm tra các nút dùng chung để tránh hồi quy.

Ghi chú: các dòng “hướng sửa dự kiến” lưu lại đề xuất ban đầu; trạng thái ở đầu từng mục là trạng thái hiện tại.

## BUG-003 — Tải danh mục khóa học báo lỗi chung do deadlock PostgreSQL

- Ngày ghi nhận: 2026-09-24. Người dùng báo: “Không thể hoàn tất yêu cầu. Vui lòng thử lại.”
- Trạng thái: đã sửa, kiểm thử và cập nhật Docker ngày 2026-09-24; chờ người dùng nghiệm thu. Phiên chẩn đoán ban đầu chỉ đọc log/mã; các bước triển khai được ghi bên dưới.
- Bằng chứng: 08:44:46 UTC (15:44:46 giờ Việt Nam), GET `/api/v1/course-settings/levels?limit=100&offset=0` và `/api/v1/courses?q=&offset=0&status=all` trả HTTP 500, exception `psycopg.errors.DeadlockDetected` bọc trong `sqlalchemy.exc.OperationalError`. Lỗi lặp lại nhiều lần, gồm 08:47:55–56 và 08:57:15/55 UTC.
- Đáng chú ý: POST `/api/v1/course-settings/frameworks` lúc 08:47:54 UTC trả 201 Created, sau đó GET tải lại levels/frameworks trả 500. Vì vậy thông báo không có nghĩa thao tác tạo trước đó chưa được lưu; cần kiểm tra danh sách sau làm mới trước khi tạo lại. Chưa có bằng chứng mất dữ liệu nghiệp vụ.

### Nguồn gốc

1. `frontend/src/Courses.tsx`: effect dùng Promise.all tải đồng thời danh sách/chi tiết khóa và ba danh mục languages/frameworks/levels. Chỉ một request thất bại cũng làm cả lượt tải báo lỗi.
2. `backend/app/api/dependencies.py`, `tenant_access`: Root có phiên hỗ trợ sẽ ghi `support.access` vào `audit_logs` rồi commit trước khi chạy handler. INSERT audit có khóa ngoại tới user và organization, phát sinh khóa kiểm tra tham chiếu.
3. `backend/app/api/routes/courses.py`, `authorize`: kể cả GET cũng lấy `organizations FOR UPDATE`, sau đó gọi `lock_actor` lấy `users FOR UPDATE`.
4. Log PostgreSQL xác nhận một giao dịch đang INSERT audit và chờ khóa tham chiếu `FOR KEY SHARE` trên organizations, trong khi giao dịch kia đang chờ `SELECT ... FROM users ... FOR UPDATE`. Kết hợp mã nguồn cho thấy vòng chờ: luồng kiểm tra quyền giữ organization và chờ user; luồng audit giữ khóa tham chiếu user và chờ organization. Đây là xung đột thứ tự khóa giữa audit và authorize khi các request Root chạy đồng thời, không phải lỗi dữ liệu cấp độ người dùng nhập.
5. Exception xảy ra cả tại `tenant_access` dòng commit, ngoài helper commit của courses; helper cũng chỉ bắt IntegrityError/StaleDataError, không xử lý deadlock OperationalError. Request kết thúc 500.
6. `frontend/src/api.ts`, `result`: lỗi không có JSON `error.code` chuyển thành `REQUEST_FAILED`; lỗi fetch cũng được component đổi sang mã này. `frontend/src/i18n.ts`, `errorMessage`: mã không có bản dịch cụ thể rơi về đúng câu người dùng thấy. Chưa lấy Network của tab người dùng để phân biệt 500 đọc được hay lỗi fetch/CORS do response exception; deadlock/500 backend đã có bằng chứng trực tiếp.

### Phạm vi và hướng xử lý khi được duyệt

- Đã xác nhận đường lỗi Root hỗ trợ trong catalog; không kết luận tất cả lỗi có cùng thông báo đều do deadlock. Rà soát các module dùng chung tenant_access/lock_actor để tìm thứ tự khóa tương tự.
- Chuẩn hóa thứ tự khóa và ranh giới transaction giữa audit hỗ trợ và kiểm tra quyền; bảo toàn audit, tenant isolation và kiểm tra phiên bị thu hồi. Không bỏ audit hoặc nới quyền để né lỗi. Chọn giải pháp sau khi có test tái hiện PostgreSQL.
- Nếu thêm retry deadlock, chỉ retry transaction đã rollback hoàn toàn, có giới hạn và kiểm tra tính an toàn/idempotency; không retry mù mọi request tạo dữ liệu.
- Cải thiện lỗi API/UI để phân biệt lưu thất bại và đã lưu nhưng tải lại thất bại; không lộ SQL/thông tin nội bộ.
- Lỗ hổng kiểm thử: E2E hiện dùng SQLite nên không kiểm chứng cơ chế khóa PostgreSQL. Các test concurrency PostgreSQL đã đạt chưa bao phủ đúng tổ hợp nhiều GET Root hỗ trợ tải catalog và audit đồng thời; không dùng kết quả cũ để coi lỗi này đã được kiểm tra.
- Nghiệm thu sau sửa: test PostgreSQL tái hiện đồng thời GET courses/languages/frameworks/levels bằng cùng Root/support; lặp tải/làm mới và tải lại sau tạo không còn 500/deadlock; audit vẫn đủ và không lặp ngoài thiết kế. Kiểm tra đồng thời kết thúc hỗ trợ/khóa tenant/thu hồi phiên vẫn chặn đúng quyền; hồi quy giáo vụ, quản lý và học viên. Chạy E2E catalog trên PostgreSQL hoặc bổ sung integration test tương đương có điều phối cạnh tranh khóa.

### Bản sửa và bằng chứng đối chứng — 2026-09-24

- `tenant_access` lấy khóa organization trước khi INSERT/commit audit hỗ trợ, thống nhất với thứ tự organization → actor → support của courses/students/membership invitations. `start_support`/`end_support` cũng lấy khóa organization trước khi ghi support/audit. Không bỏ audit, không nới quyền, không đổi frontend thành tải tuần tự và không thêm retry mutation.
- Test `test_root_parallel_catalog_audit_lock_order` điều phối hai request qua hook ngay trước khóa actor, quan sát request còn lại thực sự chờ organization bằng `pg_blocking_pids` (observer autocommit để không giữ snapshot cũ). Cùng test trên image cũ trả [200, 500]; source đã sửa trả [200, 200] và có đúng hai audit support.access.
- Bổ sung test PostgreSQL tải song song cả bốn endpoint và thu hồi hỗ trợ/khóa tenant/đăng xuất đồng thời; kiểm tra quyền bị chặn ở yêu cầu kế tiếp, không chỉ kiểm tra hết deadlock. E2E vẫn dùng SQLite, không thay thế các test tranh chấp khóa PostgreSQL này.
- UI có thông báo riêng khi server đã xác nhận lưu/xóa nhưng tải lại thất bại; hướng dẫn làm mới, không tạo lại. Thao tác sửa mã/xóa không xác định được kết quả do mạng/lỗi 500 yêu cầu kiểm tra dữ liệu trước khi gửi lại.
- Luồng bổ sung theo yêu cầu người dùng: sửa mã và xóa có xác nhận cho khóa nháp chưa từng công bố, ngôn ngữ/bộ/cấp độ chưa sử dụng. Chặn con/tham chiếu, giữ audit, kiểm tra version và quyền; không có thùng rác. Quy tắc/API/checklist tại [course-catalog.md](./course-catalog.md).
- Kiểm chứng cuối: 245 backend đạt / 22 skip bản SQLite concurrency (PostgreSQL đạt), 26 UI và 10 E2E đạt; Ruff, ESLint, TypeScript/Vite build đạt. Docker API/web đã rebuild, DB vẫn `20260924_0007`, Alembic check không lệch schema; API/web/Mailpit HTTP 200. Không xóa dữ liệu thật/volume. Jira SYNAPSELMS-70 bình luận 10063, giữ In Progress; chưa commit.

## BUG-004 — Ô chọn/danh sách tùy chọn chữ trắng nền trắng trong dark mode

- Ngày ghi nhận: 2026-09-25. Người dùng báo `<input type:'select'>` chưa tối ưu chế độ tối: chữ trắng trên nền trắng. Thành phần tương ứng trong ứng dụng là `<select>`/`<option>`.
- Trạng thái: HOÃN theo yêu cầu người dùng ngày 2026-09-25 vì chưa nghiêm trọng; CHƯA SỬA, không chặn kế hoạch nghiệp vụ tiếp theo. Người dùng xác nhận dùng Chrome; chưa có phiên bản, màn hình cụ thể hoặc xác nhận lỗi ở ô đóng/danh sách mở. Chưa tái hiện trực tiếp. Không suy diễn người dùng đã nghiệm thu toàn bộ BUG-003 hoặc luồng xóa.
- Dấu hiệu từ mã: `frontend/src/styles.css` đặt `input, select` nền transparent, chữ inherit; root đổi chữ sáng và color-scheme sang dark. Chưa có quy tắc màu riêng cho option/optgroup. Đây là điểm cần kiểm tra, chưa đủ kết luận nguyên nhân vì popup native còn phụ thuộc trình duyệt/hệ điều hành. Color-scheme dark đã tồn tại, không đề xuất thêm trùng như thể đang thiếu.
- Phạm vi rà soát: các select trong Courses (lọc, ngôn ngữ, bộ, cấp độ, loại danh mục), đăng ký/chọn trung tâm, quản lý thành viên/lời mời/hồ sơ và các form dùng CSS chung.
- Mong đợi: chữ/nền dễ phân biệt ở ô đóng và danh sách mở, mục được chọn, focus/hover, mục chưa chọn/disabled; hoạt động trong cả sáng/tối, Việt/Anh, desktop/mobile và điều hướng bàn phím.
- Kế hoạch: tái hiện với danh sách đang mở, ghi ảnh và kiểm tra style; định nghĩa màu control/popup theo theme trên đúng phần tử cần thiết, giữ native select trước khi cân nhắc component tùy biến. Không đổi dữ liệu/quyền hoặc gộp tính năng nghiệp vụ vào bản sửa.
- Kiểm thử: bổ sung regression theme cho select/option; không chỉ dùng selectOption() hoặc ảnh select đang đóng để khẳng định popup đạt. Cần kiểm tra trực quan popup thực trên trình duyệt mục tiêu, nêu rõ giới hạn nếu công cụ không chụp popup native. Chạy lại lint/build/UI/E2E liên quan, rồi rebuild web và bàn giao checklist.
- Nghiệm thu: mở từng dropdown sáng/tối, chọn bằng chuột và Tab/mũi tên/Enter, thử mục disabled, đổi Việt/Anh; không còn trắng-trên-trắng và giá trị lưu đúng. Không mất khả năng nhận diện focus hoặc làm hỏng form khác.
