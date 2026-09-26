# Danh mục khóa học, ngôn ngữ và cấp độ

Checkpoint 2026-09-24: đã triển khai lát cắt CRS-01/CRS-02, chờ người dùng nghiệm thu. Chưa có đăng ký khóa, xếp lớp, học phí hoặc đánh giá tự động điều kiện đầu vào/hoàn thành. Kế hoạch gốc: [course-catalog-next-step.md](./course-catalog-next-step.md).

## Dữ liệu và quy tắc

- `course_languages` thuộc tenant; `level_frameworks` thuộc một ngôn ngữ trong tenant; `course_levels` thuộc một bộ cấp độ. `courses` tham chiếu cùng tenant/ngôn ngữ/bộ qua khóa ngoại tổng hợp ở DB.
- Mã dài 2–40 ký tự ASCII chữ/số/gạch ngang/gạch dưới, được chuẩn hóa thành chữ hoa. Mã khóa học/ngôn ngữ duy nhất trong tenant; mã bộ duy nhất trong ngôn ngữ; mã và thứ tự cấp độ duy nhất trong bộ. Mã khóa vẫn được giữ sau lưu trữ.
- Thứ tự và quan hệ cha của danh mục không sửa sau tạo. Có thể đổi nhãn; quản lý được sửa mã khi chưa có dữ liệu con hoặc được sử dụng. Không tự quy đổi giữa các bộ/ngôn ngữ. Thứ tự từ 1 đến 10000, đầu vào không cao hơn đầu ra khi chọn cả hai.
- Có API xóa vĩnh viễn mục chưa sử dụng, không xóa dây chuyền, giữ audit. Không có thùng rác/khôi phục trên UI. DB chặn xóa danh mục đang được tham chiếu. Chưa có preset hoặc dữ liệu mẫu tự sinh; quản lý tự cấu hình thang cấp độ của trung tâm.
- Nháp cần mã/tên, có thể thiếu dữ liệu đào tạo. Công bố cần ngôn ngữ, bộ/cấp độ đầu ra và mục tiêu. Đầu vào có thể để không yêu cầu. Mô tả, mục tiêu và điều kiện là plain text, tối đa 5000 ký tự mỗi trường.
- Trạng thái: nháp → công bố hoặc lưu trữ; công bố → nháp hoặc lưu trữ; lưu trữ → nháp. Chỉ sửa nội dung khi nháp. Muốn sửa khóa đã công bố phải đưa về nháp, lúc đó khóa tạm ẩn khỏi catalog học viên.
- Chuyển trạng thái cần xác nhận, lý do và version hiện tại. Khi dữ liệu cũ: trả 409, giữ nội dung đang nhập nhưng khóa lưu; người dùng sao chép nội dung cần giữ rồi làm mới để đối chiếu. Không tự ghi đè.
- Đổi nhãn danh mục cập nhật cách hiển thị của khóa đang dùng, không đổi ID/mã/thứ tự. Khi triển khai lớp/đăng ký phải bổ sung snapshot thông tin đào tạo để giữ lịch sử; chưa tạo snapshot giả ở phiên này.
- Các thao tác tạo/sửa/chuyển trạng thái ghi audit; không sao chép toàn bộ nội dung khóa vào audit. Phạm vi tenant lấy từ phiên/membership hoặc phiên hỗ trợ, không từ body client.

## Quyền hiện hành

| Vai trò | Khóa học | Ngôn ngữ/bộ/cấp độ |
|---|---|---|
| Quản lý | Tạo/sửa nháp, công bố, đưa về nháp, lưu trữ; sửa mã/xóa nháp chưa từng công bố | Tạo/đổi nhãn; sửa mã/xóa mục chưa sử dụng và không có con |
| Giáo vụ | Xem mọi trạng thái, tạo/sửa nháp | Chỉ xem |
| Root | Như quản lý, chỉ trong phiên hỗ trợ còn hiệu lực | Qua phiên hỗ trợ |
| Học viên | Chỉ đọc khóa đã công bố của tenant hiện hành | Chỉ thông tin cần cho catalog |
| Giáo viên | Chưa mở, đợi phân công lớp | Không |

API riêng cho học viên không trả status/version quản trị; tùy chọn lọc chỉ gồm ngôn ngữ và cấp độ đầu ra đang được khóa đã công bố sử dụng. Học viên không đọc được khóa nháp/lưu trữ/khác tenant bằng ID trực tiếp. Catalog chưa mở cho khách chưa đăng nhập. Học viên chưa cần có hồ sơ hoặc đăng ký khóa để xem catalog trong tenant.

## API

Tiền tố `/api/v1`; xác thực và header bảo vệ trình duyệt như các API hiện hành. Root gửi `X-Support-Session`. Response đặt `Cache-Control: no-store`.

| Endpoint | Chức năng |
|---|---|
| `GET /course-settings/{kind}` | Danh sách `languages`, `frameworks`, `levels`; limit mặc định 100, tối đa 100, offset |
| `POST /course-settings/languages` | Tạo ngôn ngữ: code, name |
| `POST /course-settings/frameworks` | Tạo bộ: code, name, language_id |
| `POST /course-settings/levels` | Tạo cấp độ: code, name, framework_id, rank |
| `PATCH /course-settings/{kind}/{id}` | Đổi nhãn: name, version |
| `PATCH /course-settings/{kind}/{id}/code` | Sửa mã chưa sử dụng: code mới, reason, version |
| `DELETE /course-settings/{kind}/{id}` | Xóa không dây chuyền: body code hiện tại để xác nhận, reason, version; trả 204 |
| `GET/POST /courses` | Danh sách quản trị / tạo nháp |
| `GET/PATCH /courses/{id}` | Chi tiết / thay nội dung form nháp kèm version |
| `POST /courses/{id}/state` | status, reason, version |
| `PATCH /courses/{id}/code` | Sửa mã nháp chưa từng công bố: code mới, reason, version |
| `DELETE /courses/{id}` | Xóa nháp chưa từng công bố: body code hiện tại, reason, version; trả 204 |
| `GET /course-catalog/options` | Các tùy chọn lọc tối thiểu cho học viên |
| `GET /course-catalog` | Danh sách khóa đã công bố |
| `GET /course-catalog/{id}` | Chi tiết khóa đã công bố |

Danh sách khóa: `q` tìm mã/tên, `language_id`, `exit_level_id`, limit mặc định 20/tối đa 100, offset; quản trị có thêm `status=all|draft|published|archived`. Response danh sách gồm items/total/limit/offset. Ký tự `%` và `_` trong tìm kiếm được xử lý như ký tự thường.

PATCH khóa gửi nguyên phần form (name, description, objectives, entry_requirements, completion_requirements, language_id, framework_id, entry_level_id, exit_level_id) và version; không phải merge-patch. Không gửi code/status/organization_id. Trường nội dung tùy chọn bị bỏ qua sẽ về mặc định rỗng/null.

Lỗi chính: `COURSE_CONFLICT` (409), `COURSE_NOT_FOUND` (404), `COURSE_DRAFT_REQUIRED`, `COURSE_INCOMPLETE`, `COURSE_LEVEL_MISMATCH`, `COURSE_LEVEL_ORDER`, `COURSE_STATE_INVALID`; quyền dùng `FORBIDDEN`/lỗi tenant/support như hiện hành. Xem OpenAPI để lấy schema và validation đầy đủ.

## Sửa mã và xóa an toàn — bổ sung sau BUG-003

- Chỉ quản lý hoặc Root có phiên hỗ trợ hợp lệ được thực hiện; giáo vụ vẫn chỉ sửa nội dung nháp, không sửa mã/xóa.
- Ngôn ngữ có bộ cấp độ/khóa, bộ có cấp độ/khóa, cấp độ có khóa tham chiếu đều bị chặn xóa và đổi mã. Bao gồm khóa nháp, công bố và lưu trữ. Không xóa dây chuyền; tháo tham chiếu nháp/xử lý các con chưa sử dụng trước nếu cần.
- Khóa phải ở trạng thái nháp và chưa từng công bố mới được sửa mã/xóa. Đã công bố rồi đưa về nháp vẫn giữ mã/lịch sử; kiểm tra lịch sử `course.state` trong audit. Không xóa/prune lịch sử này khi chưa thay bằng dấu mốc bền vững tương đương. Khóa nháp chưa từng công bố có thể sửa/xóa cả khi đã chọn cấp độ; xóa khóa không xóa các cấp độ đó.
- Mã cũ của mục chưa sử dụng đã sửa/xóa có thể được tái sử dụng; audit giữ ID và mã cũ để phân biệt. Khóa chỉ lưu trữ vẫn giữ mã duy nhất như trước.
- Form hiển thị tên/mã đối tượng, cảnh báo xóa vĩnh viễn, yêu cầu gõ lại mã hiện tại và lý do. Backend tự kiểm tra quyền, version, mã xác nhận và tham chiếu; không chỉ dựa vào nút trên UI.
- Audit `catalog.code_change`/`catalog.delete` ghi actor, tenant, target ID, loại, mã cũ/mới và lý do; xóa và audit cùng transaction. Không lưu bản sao toàn bộ nội dung, không coi audit là bản backup có thể phục hồi.
- Lỗi chặn có giải thích Việt/Anh: `CATALOG_HAS_CHILDREN`, `CATALOG_IN_USE`, `COURSE_PREVIOUSLY_PUBLISHED` (409), `CATALOG_CONFIRMATION_MISMATCH` (422). Trùng mã/version cũ dùng `COURSE_CONFLICT` (409).
- STU-03 đã mở rộng `require_unused` cho trình độ hiện hành, mục tiêu và lịch sử: có tham chiếu thì không xóa/đổi mã (`CATALOG_PROFICIENCY_IN_USE`), kể cả sau khi bỏ mục tiêu/thu hồi xác nhận. TCH-01/TCH-02 bổ sung năng lực/lịch sử giáo viên (`CATALOG_TEACHER_IN_USE`); bỏ cấp hoặc thu hồi không giải phóng lịch sử. Nền lớp học thêm `CATALOG_CLASS_IN_USE` cho khóa/ngôn ngữ/bộ/cấp đầu vào–đầu ra được lớp giữ FK, kể cả lớp lưu trữ và cấu hình khóa nguồn đã đổi. Nhãn được sửa nhưng snapshot giữ nguyên. Khi triển khai đăng ký tiếp tục mở rộng guard; FK bảo vệ xóa là lớp cuối, không thay thế kiểm tra sử dụng khi đổi mã. Xem [STU-03](./student-proficiencies.md), [giáo viên](./teacher-profiles.md) và [lớp nháp](./class-foundation.md); checkpoint 0007 phía dưới là lịch sử, migration mới nhất 0010.
- UI phân biệt thao tác đã lưu/xóa thành công nhưng tải lại thất bại: yêu cầu làm mới, không tạo lại. Khi kết quả sửa mã/xóa không xác định do mạng/lỗi 500, UI yêu cầu kiểm tra dữ liệu trước khi gửi lại. Không tự retry mutation.

## Checklist nghiệm thu thủ công

Mở `http://localhost:5173`, tải lại trang. Nếu dùng Root: Trung tâm → nhập lý do → Mở phiên hỗ trợ → Khóa học. Phiên đăng nhập có thể cần đăng nhập lại nếu môi trường development chưa đặt JWT secret cố định.

Dùng dữ liệu thử của bạn; không dùng thông tin cá nhân thật. Có thể dùng hai browser profile/cửa sổ riêng tư để kiểm tra quản lý và học viên cùng lúc.

| Ca | Thao tác | Kết quả mong đợi / dấu hiệu lỗi |
|---|---|---|
| 1. Danh mục | Khóa học → Ngôn ngữ và cấp độ; tạo EN/Tiếng Anh, bộ LOCAL, cấp L1 thứ tự 1 và L2 thứ tự 2 | Tạo được đúng cha; trùng mã hoặc trùng thứ tự trong bộ bị từ chối. Đây là thang demo tự chọn, không phải chuẩn có sẵn |
| 2. Nháp | Về danh sách → tạo khóa DEMO-01 chỉ có tên/mã → Lưu | Lưu nháp được và hiển thị phần thiếu; học viên chưa thấy khóa |
| 3. Thiếu dữ liệu | Bấm Công bố, nhập lý do và xác nhận | Bị từ chối, không đổi trạng thái. Nếu công bố thành công là lỗi |
| 4. Công bố | Điền ngôn ngữ/bộ/đầu ra/mục tiêu, tùy chọn đầu vào và điều kiện; Lưu rồi công bố | Chuyển sang Đã công bố, không sửa trực tiếp nội dung; học viên cùng tenant thấy khóa và nội dung; không có nút đăng ký hoạt động |
| 5. Quyền | Giáo vụ mở khóa; học viên mở catalog; Root kết thúc hỗ trợ | Giáo vụ không công bố/lưu trữ/cấu hình; học viên không thấy quản trị; Root không còn đọc dữ liệu khóa tenant. API vẫn phải chặn nếu sửa URL/request |
| 6. Nhãn | Quản lý đổi nhãn L1 và xem lại khóa đang dùng | Nhãn mới hiển thị; mã L1 và thứ tự không đổi. Thử xóa/sửa mã cấp độ đang dùng phải bị chặn; không có sửa thứ tự |
| 7. Ghi đè | Đưa khóa về nháp; mở cùng khóa ở hai tab; lưu tab A rồi lưu tab B | Tab B báo xung đột, không ghi đè A; giữ nội dung đang nhập để sao chép, làm mới trước khi tiếp tục |
| 8. Lưu trữ | Công bố lại, mở chi tiết bằng học viên; quản lý lưu trữ có lý do; học viên làm mới | Khóa biến mất khỏi danh sách; chi tiết cũ báo không tìm thấy và không còn nội dung cũ. Quản lý vẫn xem được và đưa về nháp |
| 9. Tìm/lọc | Tìm DEMO-01, lọc ngôn ngữ/đầu ra/trạng thái; với hơn 20 khóa thử trang sau | Tổng số và phân trang đúng; không thấy dữ liệu trung tâm khác |
| 10. Giao diện | Đổi Việt/Anh, theme hệ điều hành sáng/tối, thu màn hình 390px và dùng Tab | Chữ/nút đọc rõ, label tương ứng ngôn ngữ, không tràn ngang; focus nhận biết được |
| 11. BUG-003 | Root hỗ trợ → mở Khóa học, làm mới vài lần, tạo một danh mục và chờ tải lại | Không có lỗi chung/500; mục vừa tạo hiện ra. Nếu báo đã lưu nhưng tải lại lỗi, làm mới kiểm tra, không tạo lại |
| 12. Sửa mã | Tạo một ngôn ngữ thử chưa có bộ/khóa; Sửa mã → mã mới + lý do → xác nhận | Mã đổi, tên giữ nguyên. Mã trùng bị chặn. Lặp lại với bộ trống, cấp độ chưa dùng và khóa nháp mới |
| 13. Xóa | Xóa mục này → thử mã sai, rồi Hủy; mở lại, nhập mã đúng/lý do → xác nhận | Mã sai không xác nhận được; Hủy giữ dữ liệu; xác nhận đúng xóa mục, báo không khôi phục từ UI, giữ audit |
| 14. Chặn sử dụng | Xóa/sửa mã ngôn ngữ có bộ, bộ có cấp độ, cấp độ dùng bởi khóa; khóa từng công bố đưa về nháp | Tất cả bị chặn kèm lý do; không mất dữ liệu con. Giáo vụ không thấy nút và API vẫn trả 403 |

Đầu vào cao hơn đầu ra hoặc cấp độ không đúng bộ/ngôn ngữ phải bị từ chối, kể cả gọi API trực tiếp. Tạo thêm trung tâm để xác nhận cùng mã được dùng độc lập nhưng không đọc/sửa chéo tenant.

## Kiểm chứng và vận hành

Checkpoint bổ sung BUG-003/sửa mã/xóa ngày 2026-09-24:

- 245 backend đạt / 22 skip bản SQLite concurrency (PostgreSQL đạt), 26 UI và 10 E2E đạt. Test điều phối deadlock thất bại trên image cũ, đạt trên source mới; thêm bốn GET Root song song với thu hồi hỗ trợ/tenant/phiên, xóa đối đầu sửa mã và gán cấp độ, audit và rollback khi trùng mã.
- Ruff, ESLint, TypeScript/Vite build đạt; đã xem ảnh xác nhận xóa dark mobile 390px, không tràn ngang. E2E sửa mã/xóa tự tạo dữ liệu riêng, không phụ thuộc bài catalog chạy trước.
- API/web Docker đã rebuild; không cần migration mới, DB vẫn `20260924_0007 (head)`, Alembic check không lệch schema. Health API/web/Mailpit HTTP 200, OpenAPI có DELETE/PATCH code và không có helper test. Không xóa dữ liệu thật hoặc volume.
- Sửa thứ tự khóa trong audit hỗ trợ/mở/kết thúc hỗ trợ để đồng nhất với handler; không bỏ audit hoặc retry mutation. Chi tiết ở [BUG-003](./test-feedback.md#bug-003--tải-danh-mục-khóa-học-báo-lỗi-chung-do-deadlock-postgresql).

Checkpoint catalog ban đầu (lịch sử, chưa bao phủ BUG-003):

- 222 test backend đạt, 15 skip là bản SQLite của các test concurrency; bản PostgreSQL đạt. Bao gồm constraint tenant, phân quyền, chống ghi đè, tạo/cập nhật/công bố đồng thời, migration nâng/hạ/nâng và so model/schema.
- 22 test UI và 9 E2E Chromium đạt; luồng mới kiểm tra cấu hình → nháp thiếu trường → công bố → học viên đọc → lưu trữ. Đã xem ảnh catalog dark/mobile 390px và light/desktop 1280px, không tràn ngang. Đây không phải audit accessibility toàn site.
- Ruff, ESLint, TypeScript/Vite build đạt. Cảnh báo TestClient/reflection SQLite hiện có không làm test thất bại.
- Migration `20260924_0007` chỉ thêm 4 bảng; không tạo khóa/cấp độ mẫu hoặc thay đổi tài khoản/hồ sơ cũ. Docker API/web đã rebuild, DB ở head và `alembic check` không lệch schema. API/web/Mailpit HTTP 200; module UI và API mới có mặt, không lộ endpoint test helper.
- PostgreSQL/Mailpit tiếp tục chạy, không xóa volume. Dữ liệu tự động kiểm thử nằm trong DB/schema tạm, không tạo dữ liệu học viên/khóa vào DB thật.

Chạy lại test theo [auth-operations.md](./auth-operations.md). Mỗi lần đổi code phải rebuild service tương ứng vì Compose không mount mã nguồn để hot reload.

Giới hạn còn lại: chưa preset, công khai catalog, rich text/upload, snapshot đăng ký, bài đánh giá năng lực, học phí hoặc thư viện học liệu. Snapshot lớp đã có trong module lớp nháp; tự khai/xác nhận trình độ đã có ở STU-03. UI tải hết danh mục cấu hình qua API phân trang; tối ưu tìm danh mục theo nhu cầu khi dữ liệu lớn là việc sau. Mọi truy cập khóa hiện khóa hàng tenant để đồng bộ với thay đổi quyền/trạng thái trung tâm; cần đo và tối ưu khi tăng tải. Không coi phiên này là hoàn tất toàn bộ quy trình đào tạo.
