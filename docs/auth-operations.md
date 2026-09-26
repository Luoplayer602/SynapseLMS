# Vận hành xác thực và phân quyền

Đã triển khai API và UI cho đăng ký, đăng nhập, hồ sơ, refresh/logout, đổi mật khẩu, quản lý trung tâm/thành viên và phiên hỗ trợ Root Admin. Thư viện học liệu chưa triển khai và không là điều kiện hoàn thành giai đoạn này.

## Khởi động Docker

Từ thư mục gốc:

```powershell
docker compose build api web
docker compose up -d db mailpit
docker compose run --rm --no-deps api .venv/bin/alembic upgrade head
docker compose up -d --no-deps api web
```

Migration mới nhất: `20260926_0010` ([chi nhánh/phòng/lớp nháp](./class-foundation.md)), sau 0009 ([hồ sơ/năng lực giáo viên](./teacher-profiles.md)) và 0008 ([trình độ và mục tiêu học viên](./student-proficiencies.md)). Xác minh email, khôi phục mật khẩu, quản lý phiên và cấu hình Mailpit được mô tả trong [vòng đời tài khoản](./account-lifecycle.md); các phần sau tại [mời thành viên qua email](./membership-invitations.md), [hồ sơ học viên](./student-profiles.md) và [danh mục khóa học](./course-catalog.md). Migration không tự xác minh tài khoản cũ hoặc tạo hồ sơ/khóa/cấp độ/chi nhánh/phòng/lớp giả. API/web được rebuild khi sửa mã; database có thể tiếp tục chạy. Không downgrade 0008/0009/0010 trên DB thật đã nhập dữ liệu: thao tác xóa các bảng và dữ liệu tương ứng; cần backup/quy trình phục hồi riêng. Checkpoint triển khai thực tế ghi trong myplan.

Tạo Root Admin bằng email của bạn (thay giá trị ví dụ):

```powershell
docker compose exec api .venv/bin/python -m app.cli bootstrap-root --email admin@example.com
```

CLI hỏi mật khẩu hai lần bằng input ẩn, yêu cầu 12–128 ký tự; không truyền mật khẩu trong command line. Tài khoản đã tồn tại sẽ bị từ chối, không tự nâng thành Root Admin. Không có tài khoản/mật khẩu quản trị mặc định.

Tạo hai trung tâm phát triển, không tạo tài khoản demo:

```powershell
docker compose exec -T api .venv/bin/python -m app.cli seed-centers
```

Seed chỉ cho development/test; chạy lại không nhân bản và không thay đổi trung tâm đã tồn tại. Đăng nhập tại `http://localhost:5173`; Swagger tại `http://localhost:8000/docs`.

## Cách sử dụng

1. Học viên chọn Đăng ký, chọn trung tâm đang công khai hoặc nhập mã mời hợp lệ. Tài khoản được gán student; chưa có đăng ký khóa học ở bước này.
2. Root Admin mở mục Trung tâm: tạo/cập nhật trung tâm, bật công khai và cho phép đăng ký.
3. Để thao tác thành viên, Root Admin nhập lý do và mở phiên hỗ trợ ở trung tâm đó, rồi vào Thành viên. Phiên mặc định 30 phút, tối đa 60 phút và gắn với đúng phiên đăng nhập đã mở nó.
4. Root Admin trong phiên hỗ trợ có thể tạo quản lý trung tâm. Quản lý có thể tạo giáo vụ, giáo viên, học viên và cấp mã mời học viên. Mã mời chỉ trả plaintext một lần, DB chỉ lưu hash; UI tạo mã một lượt dùng, hạn 7 ngày.
5. Quản lý có thể đổi vai trò/khóa membership nhân sự thông thường, không sửa chính mình hoặc quản lý khác, không tự cấp vai trò quản lý/Root. Root có thể khóa/mở tài khoản nghiệp vụ toàn hệ thống, không khóa Root qua endpoint này.
6. Khóa membership thu hồi các phiên hiện có. Người dùng có thể đăng nhập lại để xem hồ sơ cá nhân, nhưng không truy cập tenant. Khóa user toàn hệ thống chặn cả đăng nhập/refresh/me.
7. Đổi mật khẩu yêu cầu mật khẩu hiện tại, thu hồi mọi phiên, rồi đăng nhập lại. Luồng tạo thành viên trực tiếp bằng mật khẩu khởi tạo vẫn có; chưa bắt buộc đổi mật khẩu lần đầu.
8. Với nhân sự mới, dùng **Lời mời thành viên** để người nhận tự đặt mật khẩu qua email. Có danh sách/lọc/phân trang, gửi lại/thu hồi có lý do. Người đã có tài khoản đăng nhập đúng email và xác nhận riêng; tài khoản thuộc trung tâm khác cần luồng chuyển, không tự thêm membership. Xem [hướng dẫn nghiệm thu](./membership-invitations.md).

## API và phạm vi quyền

Các endpoint dưới `/api/v1`; mutation auth và các endpoint quản trị/tenant yêu cầu header `X-Synapse-Client: web`. Cookie endpoint kiểm tra Origin nếu có; CORS chỉ cho origin cấu hình. API dùng JWT Bearer cho người dùng đăng nhập; Swagger cần thêm header này khi thử endpoint quản trị.

| Endpoint | Quyền |
|---|---|
| `GET /organizations/public` | Công khai, chỉ trung tâm đang nhận đăng ký |
| `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout` | Luồng auth có rate limit và bảo vệ request trình duyệt |
| `GET /auth/me`, `POST /auth/password` | Tài khoản và phiên còn hiệu lực |
| `GET/POST /admin/organizations`, `PATCH /admin/organizations/{id}` | Root Admin |
| `PATCH /admin/users/{id}` | Root Admin; đổi trạng thái và thu hồi phiên |
| `POST /admin/support-sessions`, `DELETE /admin/support-sessions/{id}` | Root Admin; chỉ kết thúc phiên hỗ trợ thuộc đúng phiên đăng nhập |
| `GET /organization` | Thành viên hoạt động hoặc Root có phiên hỗ trợ |
| `GET/POST /members`, `PATCH /members/{id}` | Quản lý tenant hoặc Root có phiên hỗ trợ |
| `POST /organization/invites`, `DELETE /organization/invites/{id}` | Quản lý tenant hoặc Root có phiên hỗ trợ |

Root truy cập tenant gửi thêm `X-Support-Session`; không lấy tenant từ body hay query. Mọi truy cập qua phiên hỗ trợ và thay đổi quyền/trạng thái, tạo trung tâm/thành viên/mã mời có audit. Đăng nhập thành công, đổi mật khẩu và phát lại token cũng được audit. Danh sách trung tâm/thành viên hiện trả tối đa 100 bản ghi, chưa có UI phân trang/tìm kiếm; riêng lời mời email đã có phân trang 20 bản ghi và lọc trạng thái.

## Token, cấu hình và giới hạn triển khai

- Argon2id qua pwdlib; JWT HS256 xác minh issuer/audience/exp/iat/sub/session/type. Cách tích hợp dựa trên [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) và [PyJWT usage](https://pyjwt.readthedocs.io/en/latest/usage.html).
- Access token 15 phút mặc định; phiên refresh tối đa 7 ngày. Cookie `synapse_refresh` là HttpOnly, SameSite=Lax, path `/api/v1/auth`; Secure bắt buộc ngoài development/test. Không lưu token trong localStorage.
- Rotation giữ các digest đã tiêu thụ, khóa user/session trên PostgreSQL và đọc lại token sau khi có khóa. Phát lại thu hồi phiên rồi commit trước khi trả lỗi. Frontend gộp refresh trong tab và dùng Web Locks giữa các tab nếu trình duyệt hỗ trợ; trình duyệt thiếu Web Locks có thể phải đăng nhập lại khi các tab cùng refresh.
- Mỗi API bảo vệ đọc lại user/session. Tenant API kiểm tra membership/trung tâm hoạt động. Đổi quyền thu hồi mọi phiên của user; dữ liệu token không phải nguồn quyết định quyền tenant.
- Rate limit dùng PostgreSQL/SQLite, dùng chung giữa worker: login 10/phút, register 5/phút, refresh/logout 30/phút, password 10/phút theo địa chỉ client. IP chia sẻ NAT cùng hạn mức; proxy phải cấu hình địa chỉ tin cậy đúng trước khi vận hành công khai.
- `SYNAPSE_JWT_SECRET`: ít nhất 48 ký tự ngẫu nhiên. Nếu trống trong development/test, sinh khóa tạm mỗi process, restart sẽ đăng xuất người dùng. Chỉ chạy một worker khi dùng khóa tạm. Để giữ phiên qua restart/multi-worker, đặt cùng secret cố định trong `.env`; Compose chuyển secret vào API.
- Production từ chối thiếu/khóa yếu, debug=true, cookie không Secure hoặc CORS không HTTPS. Compose hiện là cấu hình phát triển, chưa là bộ triển khai production. Cookie Lax giả định frontend/API cùng site; triển khai khác site cần thiết kế lại cookie/CSRF trước.
- SQLite chỉ dùng phát triển/test. Hai request đồng thời được kiểm tra trên PostgreSQL; không tuyên bố SQLite cung cấp cùng khóa hàng.
- Đã có xác minh email, quên/đặt lại mật khẩu và quản lý phiên; xem [vòng đời tài khoản](./account-lifecycle.md). Chưa có MFA/OAuth hoặc hàng đợi email bền vững; Compose vẫn dành cho phát triển.
- Quyền lớp/buổi, chi nhánh, học phí/điểm danh/điểm số sẽ được triển khai và kiểm thử cùng module tương ứng. Khung hiện tại không phải bằng chứng các module chưa tồn tại đã được phân quyền.

## Kiểm thử

Checkpoint nền lớp học 2026-09-26: 320 backend đạt / 39 skip bản SQLite concurrency (PostgreSQL đạt), 49 UI, 13 E2E Chromium; Ruff/ESLint/build đạt. Migration 0010 roundtrip và schema/model đạt trên DB tạm; Docker API/web mới, DB 0010 head và alembic check sạch, API/web/Mailpit/module UI HTTP 200. Checklist tại [chi nhánh/phòng/lớp nháp](./class-foundation.md), chi tiết Jira/Docker tại mục 26 `myplan.txt`. Các checkpoint dưới đây là lịch sử.

Checkpoint TCH-01/TCH-02 2026-09-26: 289 backend đạt / 32 skip bản SQLite concurrency (PostgreSQL đạt), 40 UI, 12 E2E Chromium; Ruff/ESLint/build đạt. Migration 0009 nâng/hạ/nâng và schema/model trên DB tạm đạt; gồm quyền/riêng tư/version/FK, năng lực/chứng chỉ/lịch sử, bảo vệ catalog, cạnh tranh ghi và thu hồi hỗ trợ. Checklist tại [giáo viên](./teacher-profiles.md), kết quả Docker/Jira cuối tại mục 24 của `myplan.txt`.

Checkpoint STU-03 2026-09-25: 266 backend đạt / 27 skip bản SQLite concurrency (PostgreSQL đạt), 32 UI, 11 E2E Chromium; Ruff/ESLint/build đạt. Migration nâng/hạ/nâng và schema check trên DB tạm đạt; thêm quyền/riêng tư/lịch sử, FK/catalog tham chiếu và Root đọc trình độ đồng thời với thu hồi hỗ trợ. Đặc tả/checklist tại [STU-03](./student-proficiencies.md); kết quả Docker cuối tại mục 22 của `myplan.txt`. Các checkpoint bên dưới giữ làm lịch sử.

Checkpoint BUG-003/bảo trì catalog 2026-09-24: 245 backend đạt / 22 skip bản SQLite concurrency (PostgreSQL đạt); 26 UI, 10 E2E; Ruff/ESLint/build đạt. Có test điều phối deadlock và Root tải catalog đồng thời với thu hồi support/tenant/session. Docker đã cập nhật, không migration mới, vẫn head `0007`; xem [feedback](./test-feedback.md) và [catalog](./course-catalog.md).

Checkpoint catalog 2026-09-24: 222 backend đạt / 15 skip SQLite concurrency (các bản PostgreSQL đạt); 22 UI, 9 E2E đạt; Ruff, ESLint và build đạt. Migration `0007`, Alembic schema check và Docker smoke đạt. Chi tiết tại [danh mục khóa học](./course-catalog.md). Các checkpoint bên dưới giữ làm lịch sử.

Checkpoint hồ sơ học viên mới nhất: 199 backend đạt / 12 skip SQLite concurrency; 17 UI, 8 E2E đạt. Chi tiết tại [hồ sơ học viên](./student-profiles.md). Các checkpoint auth/lời mời dưới đây giữ làm lịch sử.

Kết quả mới nhất 2026-09-23: 169 backend đạt / 10 skip SQLite concurrency (các bản PostgreSQL đạt); 12 UI, 6 E2E đạt; Ruff lint, ESLint và TypeScript/Vite build đạt. Format check luồng mời đạt; toàn backend còn 14 file định dạng cũ chưa chỉnh ngoài phạm vi. Phạm vi mới xem [mời thành viên qua email](./membership-invitations.md). Các số liệu dưới đây là checkpoint trước khi bổ sung email/recovery/quản lý phiên.

Kết quả xác nhận 2026-09-21: 42 test cục bộ đạt, 2 concurrency skip trên SQLite; Docker chạy cả SQLite/PostgreSQL: 81 đạt, 2 skip chỉ trên SQLite. Ba test frontend và hai E2E Chromium đạt; Ruff, ESLint, production build đạt. Còn cảnh báo deprecation TestClient và hạn chế reflection expression index SQLite đã ghi ở AUTH-01.

```powershell
Set-Location backend
uv run ruff check .
uv run pytest
Set-Location ..
docker compose run --rm --no-deps -e SYNAPSE_TEST_POSTGRES=1 -v "${PWD}/backend/tests:/app/tests:ro" api uv run --locked --group dev pytest
Set-Location frontend
npm.cmd run lint
npm.cmd run test
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

PostgreSQL dùng schema test riêng rồi dọn sạch. E2E tự khởi động API loopback cổng 8011 với SQLite tạm và Vite cổng 5180; không sử dụng DB Docker. Tài khoản Root cố định trong `tests/e2e_server.py` chỉ tồn tại ở database tạm đó. Test kiểm tra học viên đăng ký/đăng nhập/reload/đổi mật khẩu/logout, Root hỗ trợ/tạo giáo viên/khóa membership và phiên giáo viên cũ bị từ chối.
