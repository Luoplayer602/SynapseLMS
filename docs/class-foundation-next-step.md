# Kế hoạch tiếp theo — Chi nhánh, phòng và lớp nháp

Ngày 2026-09-26. Người dùng đã duyệt triển khai chi nhánh/phòng/lớp nháp; tài liệu này giữ lại kế hoạch gốc. TCH-01/TCH-02 đã được người dùng nghiệm thu. Phạm vi triển khai và checklist tại [class-foundation.md](./class-foundation.md). Làm từng lát cắt cho một người phát triển và AI; không gộp toàn bộ lịch/phân công/đăng ký vào một phiên.

## Phạm vi phiên kế tiếp

Chuẩn bị cơ sở vật chất và lớp nháp: chi nhánh, phòng, tạo lớp từ khóa học, sĩ số và khoảng ngày dự kiến. Bao phủ phần nền CLS-01/CLS-02; chưa coi lớp đã mở tuyển sinh hoặc toàn bộ luồng mở lớp hoàn tất. Đã đối chiếu backlog: ORG-02/SYNAPSELMS-54, ORG-03/SYNAPSELMS-55, CLS-01/SYNAPSELMS-72, CLS-02/SYNAPSELMS-73; tái sử dụng story hiện có, không tạo trùng.

### 1. Chi nhánh và phòng học

- Chi nhánh thuộc tenant: mã, tên, địa chỉ tùy chọn, múi giờ IANA (đề xuất mặc định Asia/Ho_Chi_Minh), trạng thái hoạt động/lưu trữ. Không tự tạo chi nhánh giả qua migration/GET.
- Phòng thuộc chi nhánh: mã, tên, sức chứa nguyên dương, ghi chú và trạng thái hoạt động/lưu trữ. Mã chi nhánh duy nhất trong tenant, mã phòng duy nhất trong chi nhánh, kể cả lưu trữ.
- Quản lý trung tâm/Root có hỗ trợ được tạo/sửa/lưu trữ/khôi phục; giáo vụ chỉ xem/chọn theo ma trận quyền hiện có. Giáo viên/học viên chưa có API danh sách cơ sở vật chất toàn trung tâm.
- Không xóa cứng trong lát cắt này. Đề xuất cho sửa mã khi chưa có tham chiếu, cần version/lý do; tên/địa chỉ/ghi chú được sửa theo quyền. Không cascade.

### 2. Lớp nháp từ khóa học

- Chọn khóa đang công bố và chi nhánh đang hoạt động; nhập mã lớp, tên, sĩ số tối đa, ngày bắt đầu/kết thúc dự kiến, hình thức trực tiếp/trực tuyến/kết hợp. Mã lớp duy nhất trong tenant kể cả lưu trữ.
- Chi nhánh là đơn vị quản lý bắt buộc cả với lớp trực tuyến. Phòng mặc định tùy chọn cho trực tiếp/kết hợp; trực tuyến không gắn phòng. Phòng nếu chọn phải hoạt động và thuộc đúng chi nhánh; sĩ số không vượt sức chứa phòng.
- Ngày kết thúc không trước ngày bắt đầu. Đây là khoảng ngày dự kiến, chưa phải lịch học, chưa kiểm tra trùng phòng/giáo viên và chưa đặt giữ phòng.
- Trạng thái chỉ có draft/archived. Quản lý/giáo vụ tạo/sửa và lưu trữ/khôi phục có lý do; Root qua support. Không có active/published/đang tuyển sinh khi chưa có lịch và điều kiện mở lớp.
- Giữ course_id và snapshot mã/tên/ngôn ngữ/bộ/cấp đầu vào/đầu ra tại thời điểm tạo. Khóa đổi nhãn/nội dung sau đó không âm thầm thay lớp. Chưa chụp mẫu đánh giá hay học phí vì các module đó chưa có.
- Không đổi khóa của lớp sau tạo; chọn nhầm thì lưu trữ lớp nháp và tạo lại. Đổi chi nhánh/phòng/hình thức/ngày/sĩ số được khi nháp và phải kiểm tra lại quan hệ. Sửa mã lớp nháp cần lý do; khi có liên kết nghiệp vụ sau này phải bổ sung điều kiện khóa mã.
- Khóa gốc đưa về nháp/lưu trữ không xóa lớp; lớp vẫn xem được và hiện cảnh báo khóa không còn công bố. Chưa có hành động mở lớp nên không tự kích hoạt lớp này.

### 3. Quy tắc tham chiếu và dữ liệu

- Version cho chi nhánh/phòng/lớp, chống ghi đè giữa hai tab. FK tổng hợp bảo vệ tenant và phòng/chi nhánh; dữ liệu tenant lấy từ phiên, không từ body tùy ý.
- Chặn xóa/đổi mã khóa hoặc danh mục được lớp/snapshot tham chiếu, kể cả lớp lưu trữ. Snapshot mã/nhãn đi kèm FK, không dùng JSON để bỏ bảo vệ tham chiếu.
- Không lưu trữ chi nhánh khi còn phòng hoặc lớp chưa lưu trữ; không lưu trữ phòng khi còn lớp nháp dùng làm phòng mặc định. Khôi phục/lưu lớp phải kiểm tra lại chi nhánh/phòng đang hoạt động.
- Giảm sức chứa phòng không được làm lớp nháp đang tham chiếu vượt sức chứa; cần đổi phòng hoặc chỉnh sĩ số trước. Lớp lưu trữ giữ snapshot lịch sử, không bị tự sửa sĩ số.
- Audit thao tác tạo/sửa/đổi mã/lưu trữ/khôi phục, lý do cho hành động nhạy cảm; không chép địa chỉ/ghi chú tự do vào audit. Giữ khóa organization → actor → support và kiểm tra lại quyền sau khóa.
- Migration chỉ thêm cấu trúc, không seed/lấy dữ liệu mẫu làm cơ sở vật chất thật. Chưa có enrollment, số chỗ còn lại, doanh thu hoặc lịch trống suy diễn.

## Giao diện

- Quản lý/Root có mục **Chi nhánh & phòng**; giáo vụ xem chỉ đọc và dùng bộ chọn trong form lớp.
- Nhân sự có **Lớp học**: tìm mã/tên, lọc khóa/chi nhánh/trạng thái, phân trang, tạo nháp, chi tiết, sửa/lưu trữ/khôi phục. Có cảnh báo rõ “chưa có lịch/chưa mở tuyển sinh”.
- Hiện thông tin khóa theo snapshot, phân biệt ngày dự kiến với buổi học thực tế. Không hiển thị nút đăng ký/điểm danh hoặc lịch giả.
- Việt/Anh, desktop/mobile, trạng thái rỗng/loading/lỗi/version cũ và xác nhận thao tác. BUG-004 select dark mode tiếp tục hoãn.

## Trình tự triển khai

1. Chốt các mặc định trên khi người dùng duyệt; ghi đặc tả quyền/trạng thái/tham chiếu.
2. Model/migration chi nhánh, phòng, lớp/snapshot; kiểm thử nâng/hạ/nâng trên DB tạm.
3. API CRUD có giới hạn, phân trang/tìm kiếm và catalog guard; test SQLite/PostgreSQL, cùng tenant, version, membership/support và cạnh tranh đổi sức chứa/lưu lớp/lưu trữ.
4. UI theo vai trò và E2E tạo chi nhánh → phòng → lớp nháp; test online/offline/hybrid và dữ liệu lỗi.
5. Hồi quy auth/STU/TCH/catalog, lint/build/schema check. Sau khi đạt mới cập nhật Docker và bàn giao checklist. Không tự commit, không xóa volume hoặc cần tắt database trước; API/web có thể gián đoạn ngắn khi cập nhật.

## Tiêu chí nghiệm thu

1. Quản lý tạo chi nhánh/phòng; giáo vụ xem nhưng không sửa được cấu hình, kể cả gọi API trực tiếp.
2. Tạo lớp từ khóa công bố, ngày/sĩ số hợp lệ; tải lại không mất dữ liệu. Khóa nháp hoặc tenant khác không chọn được.
3. Phòng khác chi nhánh, phòng lưu trữ, sĩ số vượt sức chứa và ngày đảo ngược bị từ chối, không để lại bản ghi dở.
4. Lớp trực tuyến không cần phòng; lớp trực tiếp/kết hợp có thể chưa chọn phòng khi còn nháp; không tuyên bố đã giữ phòng hay không trùng lịch.
5. Khóa đổi nhãn/nội dung không thay snapshot lớp; danh mục đã tham chiếu không xóa/đổi mã được.
6. Chặn lưu trữ cơ sở vật chất hoặc giảm sức chứa làm sai lớp nháp đang dùng. Khôi phục lớp không bỏ qua trạng thái cơ sở vật chất.
7. Hai tab/ghi đồng thời không ghi đè hoặc vượt quy tắc; thu hồi quyền/support chặn request sau đó, không lỗi 500.
8. Không có học viên/hóa đơn/lịch/buổi học tự phát sinh từ tạo lớp nháp.

## Những lát cắt tiếp sau — chưa triển khai cùng phiên

- **Phân công và lịch cơ bản:** CLS-03, SCH-01/02/03, TCH-03/04/05 — nhiều giáo viên, thời gian có thể dạy, lịch tuần, sinh buổi và chống trùng. Chốt riêng quy tắc năng lực giáo viên, múi giờ/DST, lịch thiếu giáo viên/phòng, sửa mẫu lịch và tính nguyên tử/idempotency khi sinh buổi.
- **Vận hành lịch:** SCH-04/05/06/07 — đổi/hủy buổi, lịch tuần/tháng, dạy thay và liên kết học trực tuyến. Quyền giáo viên xem lớp/học viên phải dựa trên phân công thực tế, không chỉ năng lực.
- **Sau nền lớp/lịch:** tài chính/thông báo rồi đăng ký khóa → duyệt tạo hóa đơn → xếp lớp tự động/thủ công theo quy tắc đã chốt. Không mở luồng duyệt nửa chừng khi chưa có hóa đơn nguyên tử.
- AI, điểm/điểm danh, thư viện học liệu, giải trí và payroll không nằm trong phiên nền lớp.

Giữ đề cử phiên triển khai: **GPT gpt-6-astra high**. Kế hoạch đã được duyệt và triển khai; trạng thái nghiệm thu/checkpoint xem [class-foundation.md](./class-foundation.md) và mục 26 `myplan.txt`.
