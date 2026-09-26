# Chi nhánh, phòng học và lớp nháp

Ngày triển khai: 2026-09-26. ORG-02/ORG-03 và phần nền CLS-01/CLS-02; chờ người dùng nghiệm thu. Kế hoạch đã duyệt: [class-foundation-next-step.md](./class-foundation-next-step.md).

## Phạm vi và quyền

- Sidebar **Chi nhánh & phòng**: quản lý trung tâm được tạo/sửa/lưu trữ/khôi phục; giáo vụ chỉ xem. Root phải mở phiên hỗ trợ trung tâm trước.
- Sidebar **Lớp học**: quản lý/giáo vụ và Root đang hỗ trợ được tạo/sửa/lưu trữ/khôi phục lớp nháp. Giáo viên và học viên chưa được truy cập hai module này, kể cả gọi trực tiếp API.
- Mỗi bản ghi thuộc tenant lấy từ phiên xác thực, không nhận tenant tùy ý từ body. Root hết hạn/thu hồi hỗ trợ hoặc tài khoản mất quyền sẽ bị chặn ở request kế tiếp.
- Chưa có phân quyền nhân sự theo từng chi nhánh. Người có quyền hiện làm việc trong toàn trung tâm của mình; không coi đây là hoàn tất IAM-05 theo chi nhánh.

## Dữ liệu và quy tắc

Migration `20260926_0010` thêm `branches`, `rooms`, `learning_classes` và unique index `(id, organization_id)` trên courses phục vụ FK. Không seed/backfill, không tạo dữ liệu qua GET. Giữ dữ liệu các module cũ; không downgrade migration này trên DB thật đã có lớp/phòng.

Chi nhánh có mã/tên, địa chỉ tùy chọn, múi giờ IANA (mặc định `Asia/Ho_Chi_Minh`), trạng thái hoạt động/lưu trữ. Phòng có mã/tên, chi nhánh cố định sau tạo, sức chứa 1–10000 và ghi chú. Mã được trim/viết hoa, dài 2–40, chữ/số/gạch ngang/gạch dưới. Mã chi nhánh/lớp duy nhất trong tenant, mã phòng duy nhất trong chi nhánh, kể cả đã lưu trữ.

Lớp mới phải chọn khóa **đã công bố** và chi nhánh hoạt động. Chi nhánh bắt buộc cả khi học online. Phòng mặc định tùy chọn với offline/hybrid; online không gắn phòng. Phòng phải cùng chi nhánh, hoạt động và đủ sức chứa lớp. Ngày kết thúc không trước ngày bắt đầu. Ngày dự kiến chưa giữ phòng, sinh buổi học hay kiểm tra trùng lịch.

Khóa của lớp không đổi sau tạo. Lớp lưu bản chụp mã/tên/mô tả/mục tiêu/yêu cầu/ngôn ngữ/bộ/cấp đầu vào–đầu ra và thời điểm tạo. Các FK gốc bảo vệ danh mục kể cả khi khóa nguồn đổi cấu hình. Đổi nhãn/cấu hình khóa không viết lại bản chụp. Khóa nguồn ngừng công bố vẫn giữ lớp cũ và hiển thị cảnh báo; không tạo lớp mới từ khóa đó. Chi nhánh, phòng và múi giờ là thông tin hiện hành, không phải snapshot lịch học.

Trạng thái lớp chỉ `draft`/`archived`, chưa mở tuyển sinh. Được sửa mã lớp nháp có lý do/version. Trước khi triển khai đăng ký/buổi học phải mở rộng guard sửa mã và thay đổi lớp theo tham chiếu mới.

Không xóa cứng. Lưu trữ giữ lịch sử/mã và chặn sửa. Chi nhánh không lưu trữ nếu còn phòng hoạt động hoặc lớp nháp; phòng không lưu trữ nếu còn lớp nháp dùng phòng. Giảm sức chứa phòng không được làm lớp nháp hiện tại vượt sức chứa. Lớp đã lưu trữ không chặn giảm sức chứa, nhưng khôi phục sẽ kiểm tra lại: cần khôi phục cơ sở vật chất/tăng sức chứa trước. Lớp đã lưu trữ chưa được sửa trực tiếp để tránh vượt quy trình khôi phục.

Sửa mã chi nhánh/phòng chỉ khi chưa có **bất kỳ** tham chiếu nào, kể cả đã lưu trữ. Đổi tên vẫn được phép khi hoạt động. Catalog guard chặn xóa/sửa mã khóa/ngôn ngữ/bộ/cấp độ được lớp tham chiếu, bao gồm lớp lưu trữ; không xóa dây chuyền.

## API

Tất cả dưới `/api/v1`; `kind` là `branches` hoặc `rooms`.

| Đường dẫn | Thao tác |
| --- | --- |
| `/facilities/{kind}` | GET danh sách; POST tạo tại `/facilities/branches` hoặc `/facilities/rooms` |
| `/facilities/{kind}/{id}` | GET chi tiết, PATCH thông tin |
| `/facilities/{kind}/{id}/state` | POST `{version, archived, reason}` |
| `/facilities/{kind}/{id}/code` | PATCH `{version, code, reason}` |
| `/classes` | GET danh sách, POST lớp nháp |
| `/classes/{id}` | GET chi tiết, PATCH thông tin lớp nháp |
| `/classes/{id}/state` | POST `{version, status, reason}` |
| `/classes/{id}/code` | PATCH `{version, code, reason}` |

Danh sách trả `{items,total,limit,offset}`, mặc định 20/tối đa 100. `q` tìm mã/tên, `status` là active/archived/all cho cơ sở vật chất hoặc draft/archived/all cho lớp; phòng/lớp lọc `branch_id`, lớp thêm `course_id`.

PATCH thông tin gửi đầy đủ trường editable và `version`, không nhận mã/trường chủ sở hữu/snapshot ngoài endpoint riêng. Lý do cho thao tác mã/trạng thái dài 3–500 ký tự. Audit ghi actor/tenant/target/trường thay đổi/lý do; không chép địa chỉ hay ghi chú vào log. Phần xem audit UI chưa thuộc phiên này.

Mã lỗi chính: `CLASS_RESOURCE_CONFLICT` (trùng mã hoặc phiên bản cũ), `FACILITY_IN_USE`, `ROOM_CAPACITY_IN_USE`, `CLASS_CAPACITY_EXCEEDED`, `CLASS_ROOM_MISMATCH`, `FACILITY_ARCHIVED`, `CLASS_DRAFT_REQUIRED`, `CLASS_PUBLISHED_COURSE_REQUIRED`, `CATALOG_CLASS_IN_USE`. UI không tự retry mutation; khi version xung đột giữ phần nhập để sao chép rồi làm mới. Khi mất mạng phải kiểm tra danh sách trước khi gửi lại vì thao tác có thể đã được lưu.

FK tổng hợp bảo vệ tenant/chi nhánh/phòng/ngôn ngữ/bộ/cấp độ; SQL checks bảo vệ ngày/sĩ số/trạng thái/hình thức. API serialize thao tác trên hàng tenant, rồi actor/hỗ trợ, dùng cùng thứ tự khóa với catalog để chống race tạo lớp–lưu trữ–giảm sức chứa. SQLite không có row lock PostgreSQL; kiểm thử race chạy PostgreSQL, SQLite dành cho hành vi/constraint/migration. Các selector UI hiện tải toàn bộ lựa chọn qua API phân trang; tìm từ xa khi dữ liệu lớn là tối ưu sau.

## Checklist nghiệm thu trên Chrome

Chuẩn bị: tải lại `http://localhost:5173`, dùng quản lý hoặc Root → Trung tâm → bắt đầu hỗ trợ. Cần một khóa đã công bố; khóa nháp không xuất hiện trong lựa chọn tạo lớp. Không cần tắt database/container để test.

1. **Tạo cơ sở vật chất:** thêm chi nhánh `CN-TEST`, tên/địa chỉ, múi giờ mặc định. Thêm phòng `P-TEST` thuộc chi nhánh, sức chứa 20. Tải lại danh sách: dữ liệu còn, tìm mã/tên và lọc đúng. Múi giờ không tồn tại/mã trùng phải bị từ chối; không tạo bản ghi thừa.
2. **Tạo lớp:** chọn khóa công bố, chi nhánh/phòng vừa tạo, sức chứa 15, ngày kết thúc sau bắt đầu. Lưu thành công, hiển thị Nháp và bản chụp thông tin khóa. Thử sĩ số 21: báo vượt sức chứa; sửa 15 rồi lưu được. Ngày ngược thứ tự không được lưu.
3. **Sửa và bảo vệ tham chiếu:** đổi tên lớp, sửa mã có lý do. Thử giảm sức chứa phòng xuống 10 hoặc lưu trữ phòng đang dùng: bị chặn, dữ liệu cũ không bị thay đổi. Đổi mã chi nhánh/phòng đã dùng bị chặn; tên vẫn sửa được.
4. **Online và quyền:** chuyển lớp sang Trực tuyến: phòng tự bỏ chọn, chi nhánh vẫn bắt buộc. Giáo vụ thấy chi nhánh/phòng nhưng không có nút ghi; vẫn tạo/sửa lớp nháp được. Giáo viên/học viên không thấy hai mục. Root kết thúc hỗ trợ thì không còn truy cập được.
5. **Lưu trữ/khôi phục:** lưu trữ lớp có lý do; lớp chỉ thấy khi lọc lưu trữ/tất cả, form chỉ đọc. Khôi phục hợp lệ quay về Nháp. Với lớp gắn phòng, thử lưu trữ lớp → giảm sức chứa phòng dưới sĩ số lớp → khôi phục lớp: phải bị chặn; tăng sức chứa rồi khôi phục được.
6. **Snapshot và xung đột:** sửa tên/mục tiêu khóa nguồn sau khi đưa về nháp; lớp giữ nội dung cũ và cảnh báo khóa không còn công bố. Mở cùng lớp ở hai tab, lưu tab đầu rồi lưu tab cũ: phải báo xung đột, không ghi đè. Làm mới để xem bản mới.
7. **Hiển thị:** chuyển Việt/Anh, thử màn hình nhỏ và sáng/tối; điều hướng qua lại Chi nhánh & phòng ↔ Lớp học phải hiển thị đúng module, không giữ form/lựa chọn của loại dữ liệu trước.

Dấu hiệu thất bại cần gửi lại: thông báo lỗi chung thay vì lý do nghiệp vụ, bản ghi trùng sau một lần lưu, hiển thị dữ liệu tenant khác, giáo vụ sửa được phòng, lớp online còn phòng, lớp vượt sức chứa vẫn lưu được, snapshot bị thay theo khóa nguồn, hoặc tab cũ ghi đè bản mới. BUG-004 popup native select Chrome màu chữ/nền vẫn **hoãn**, không tính là đã sửa trong phiên này.

## Giới hạn và bước sau

Bổ sung sau checkpoint nền lớp: đã có [phân công và lịch cơ bản](./scheduling.md). Phòng mặc định/ngày dự kiến của lớp vẫn không tự giữ chỗ; chỉ xác nhận lịch mới tạo buổi và giữ tài nguyên. Khi đã có buổi, khóa cấu trúc/mã lớp và múi giờ chi nhánh; chặn lưu trữ tài nguyên/lớp còn buổi tương lai hoặc giảm sức chứa phòng dưới sĩ số buổi (kể cả phòng không phải mặc định). Tên lớp vẫn sửa được. Các quy tắc nháp phía trên áp dụng trước xác nhận.

Chưa lịch rảnh/dạy thay/đổi-hủy buổi, đăng ký/xếp lớp, học phí, điểm danh/điểm, AI hoặc thư viện học liệu. Không đánh dấu hoàn tất toàn bộ CLS-01 chỉ vì đã tạo được lớp nháp hoặc xác nhận lịch.

Kết quả kiểm thử/deploy/Jira cuối cùng được ghi tại mục 26 `myplan.txt`.
