# Kế hoạch TCH-01/TCH-02 — Hồ sơ và năng lực giảng dạy

Ngày 2026-09-26. Người dùng đã duyệt triển khai; API/UI đã kiểm chứng và cập nhật Docker, chờ nghiệm thu. Đặc tả thực tế/checklist tại [teacher-profiles.md](./teacher-profiles.md). Nội dung bên dưới giữ làm kế hoạch gốc. Người dùng đã nghiệm thu STU-03. Bước này chuẩn bị dữ liệu giáo viên cho phân công lớp/lịch; không gộp toàn bộ module lịch học.

## Phạm vi và mặc định đề xuất

- TCH-01 (SYNAPSELMS-65): danh sách tìm kiếm/phân trang/lọc trạng thái; tạo, xem, sửa, lưu trữ/khôi phục hồ sơ. Dùng lưu trữ thay xóa cứng để giữ liên kết nghiệp vụ tương lai.
- Hồ sơ gắn tài khoản có membership giáo viên chưa kết thúc trong cùng trung tâm; tạo mới yêu cầu membership đang hoạt động. Mỗi user/tenant tối đa một hồ sơ. Không tự tạo tài khoản, đổi vai trò hay membership. Tài khoản và hồ sơ có vòng đời riêng.
- Thông tin: họ tên, điện thoại, giới thiệu/chuyên môn, ghi chú nội bộ. Email lấy từ tài khoản, chỉ đọc. Chưa thu CCCD, tài khoản ngân hàng, lương hoặc file chứng chỉ. Chưa bổ sung mã giáo viên nghiệp vụ khi chưa có nhu cầu; ID nội bộ đủ cho liên kết.
- TCH-02 (SYNAPSELMS-66): ngôn ngữ, bộ cấp độ và danh sách chính xác các cấp độ có thể dạy. Không suy diễn dạy được mọi cấp thấp hơn hoặc tự quy đổi giữa hai bộ. Có thể ghi chuyên môn ngôn ngữ trước, chưa chọn cấp độ; không coi đó là đủ điều kiện phân công.
- Chứng chỉ là bản ghi văn bản: tên, đơn vị cấp, ngày cấp/hết hạn tùy chọn, ghi chú. Ngày hết hạn không trước ngày cấp; hiển thị cảnh báo hết hạn, chưa tự thu hồi năng lực dạy. Không upload, không gọi API xác minh chứng chỉ.
- Năng lực/chứng chỉ do trung tâm ghi nhận thủ công; không tự suy ra từ tự giới thiệu của giáo viên. Mỗi lần sửa/thu hồi năng lực hoặc chứng chỉ cần lý do và lịch sử; không có xóa cứng lịch sử.

## Phân quyền đề xuất

- Quản lý/giáo vụ: tạo, cập nhật, lưu trữ/khôi phục và quản lý năng lực/chứng chỉ trong tenant. Root cần phiên hỗ trợ còn hiệu lực và audit.
- Giáo viên: xem hồ sơ/năng lực/chứng chỉ của mình, sửa điện thoại và giới thiệu; không tự tạo hồ sơ, sửa năng lực được trung tâm ghi nhận, lưu trữ hoặc đọc ghi chú/lý do nội bộ.
- Học viên: không có quyền danh sách/hồ sơ giáo viên trong lát cắt này. Trang giới thiệu giáo viên công khai là phạm vi khác.
- Hồ sơ lưu trữ chỉ đọc, không khóa tài khoản. Nhân sự vẫn xem hồ sơ khi membership bị đình chỉ/kết thúc; không mở lại quyền giáo viên hoặc đổi chủ sở hữu hồ sơ.
- Không mở quyền xem học viên/nhập điểm cho giáo viên trước khi có phân công lớp; quyền điểm số đã chốt giữ nguyên.

## Thứ tự thực hiện

### 1. Đặc tả và dữ liệu

- Chốt các mặc định trên khi người dùng duyệt. Thiết kế TeacherProfile, TeachingCapability, TeacherCredential và lịch sử thay đổi năng lực/chứng chỉ.
- Unique profile theo user/tenant; cấp độ không trùng trong cùng năng lực. FK tổng hợp bảo vệ tenant/ngôn ngữ/bộ. Không chỉ kiểm tra quan hệ tại frontend.
- Version cho các tài nguyên có thể sửa; snapshot lịch sử giữ mã/nhãn, người/thời điểm. Tách nội dung giáo viên được xem khỏi ghi chú/lý do nội bộ. Audit kỹ thuật không chép nội dung cá nhân tự do.
- Migration chỉ thêm cấu trúc, không sinh hồ sơ/năng lực giả cho tài khoản giáo viên hiện có. GET không tạo dữ liệu nghiệp vụ.

### 2. API và bảo vệ danh mục

- API quản trị tenant và API `/me` riêng cho giáo viên; body không được chọn tenant/chủ sở hữu tùy ý khi sửa. Danh sách/hồ sơ/lịch sử có phân trang và lỗi cụ thể.
- Metadata tối thiểu cho module giáo viên, không mở API quản trị catalog cho giáo viên. Có thể tái sử dụng logic nhưng không đổi quyền endpoint STU-03.
- Mở rộng `require_unused` cho năng lực hiện tại và lịch sử trước khi mở module: ngôn ngữ/bộ/cấp độ đã dùng không xóa/đổi mã được. Sửa nhãn không viết lại snapshot cũ. Thu hồi năng lực vẫn giữ tham chiếu lịch sử.
- Kiểm tra lại quyền/tenant/support sau khóa, giữ thứ tự khóa đã sửa BUG-003. Test cạnh tranh cập nhật năng lực với xóa/đổi mã và thu hồi quyền.

### 3. Giao diện

- Nhân sự có mục sidebar **Giáo viên**: tìm tài khoản giáo viên để tạo hồ sơ, danh sách tìm kiếm/lọc/phân trang, chi tiết và lưu trữ/khôi phục có lý do.
- Giáo viên có **Hồ sơ giáo viên của tôi**: trạng thái chưa được tạo rõ ràng, thông tin được sửa và năng lực/chứng chỉ chỉ đọc.
- Chi tiết phân phần thông tin liên hệ, năng lực, chứng chỉ và lịch sử. Hiển thị nguồn trung tâm, trạng thái thu hồi/hết hạn; xác nhận trước thao tác thay đổi trạng thái.
- Việt/Anh, desktop/mobile; loading/rỗng/lỗi/version cũ/quyền thu hồi. Lỗi mạng không tự retry mutation. BUG-004 select dark mode vẫn hoãn, không tuyên bố đã sửa.

### 4. Kiểm thử và bàn giao

- Backend SQLite/PostgreSQL: quyền/tenant, membership, tạo trùng, FK sai bộ, version cũ, archived, dữ liệu nội bộ, snapshot và catalog guard. PostgreSQL kiểm thử ghi đồng thời/thu hồi support, không chỉ các request tuần tự.
- UI/E2E: nhân sự tạo hồ sơ/năng lực/chứng chỉ → giáo viên xem và sửa liên hệ → nhân sự thu hồi năng lực/lưu trữ → giáo viên chỉ đọc. Test ngày chứng chỉ, sửa nhãn không thay lịch sử, Việt/Anh/mobile.
- Hồi quy auth, hồ sơ học viên, STU-03 và catalog. Migration nâng/hạ/nâng/schema check trên DB tạm; không downgrade DB thật đã nhập dữ liệu.
- Chỉ sau khi đạt mới rebuild API/web và upgrade migration. Không cần tắt database hay xóa volume; API/web có thể gián đoạn ngắn khi thay container. Cập nhật tài liệu/myplan/Jira đúng phạm vi, bàn giao checklist, không tự commit.

## Tiêu chí nghiệm thu

1. Nhân sự chỉ tạo hồ sơ từ tài khoản giáo viên hợp lệ trong tenant; không tạo trùng hoặc lấy nhầm tài khoản trung tâm khác.
2. Giáo viên sửa liên hệ/giới thiệu của mình được nhưng không sửa năng lực/chứng chỉ hay nhận nội dung nội bộ qua API.
3. Chọn nhiều ngôn ngữ/bộ/cấp độ không lẫn quan hệ; chứng chỉ có ngày không hợp lệ bị từ chối; hết hạn hiển thị rõ.
4. Cập nhật/thu hồi có lý do và lịch sử giữ nguyên nhãn cũ; danh mục đã tham chiếu không xóa/đổi mã được.
5. Hai tab không ghi đè phiên bản mới; hồ sơ lưu trữ chỉ đọc; thu hồi quyền/support chặn request sau đó, không lỗi 500.
6. Không tự phát sinh lớp/lịch/lương hoặc quyền xem học viên từ việc thêm năng lực.

## Để sau

TCH-03 (SYNAPSELMS-67) thời gian có thể dạy; TCH-04 (68) lớp/lịch được phân công; TCH-05 (69) trùng lịch: triển khai cùng lát cắt chi nhánh/phòng/lớp/lịch, không đưa lịch giả vào phiên hồ sơ. Sau đó mới tài chính/thông báo và đăng ký/duyệt/xếp lớp. Thư viện học liệu, AI, payroll, upload/xác minh chứng chỉ, import và chuyển giáo viên liên trung tâm chưa triển khai.

Đề cử khi duyệt triển khai: **GPT gpt-6-astra high**. Trạng thái thực hiện ghi tại tài liệu module và myplan, không dùng câu chờ duyệt trong kế hoạch gốc để suy ra trạng thái hiện tại.
