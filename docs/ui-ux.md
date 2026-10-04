# Định hướng UI/UX SynapseLMS

**Phiên bản:** 0.3 — cập nhật 2026-10-03

**Trạng thái:** Synapse Soft mặc định đã code/test/deploy trên shell và các route nghiệp vụ, thêm hub AI học viên dẫn tới tác vụ hiện có. Chưa được người dùng nghiệm thu; còn đối chiếu chi tiết với các board Penpot. Phạm vi, bằng chứng và checklist tại [kế hoạch thực thi](./plans/frontend-penpot-remaining.md).

## Mục tiêu

- Dễ làm quen với người dùng không chuyên công nghệ.
- Desktop-first cho nghiệp vụ quản trị, responsive đầy đủ cho điện thoại.
- Tối ưu đặc biệt luồng điểm danh của giáo viên và bài luyện tập của học viên trên mobile.
- Dashboard và điều hướng thay đổi theo vai trò, không hiển thị mục người dùng không có quyền.
- Phong cách Synapse Soft theo `ui-design/` và thiết kế Penpot: nền mint nhẹ, card trắng, viền mảnh và icon nét đều.

## Khung ứng dụng

### Desktop

- Sidebar bên trái rộng khoảng 240–264 px, có thể thu gọn còn biểu tượng.
- Top bar trong vùng nội dung chứa breadcrumb, tìm kiếm, thông báo, đổi ngôn ngữ và menu tài khoản.
- Nội dung giới hạn chiều rộng hợp lý ở màn hình lớn; bảng dữ liệu có thể dùng toàn chiều rộng.
- Hành động chính nằm ở góc phải tiêu đề trang và giữ vị trí nhất quán.

### Mobile

- Sidebar chuyển thành navigation drawer.
- Các thao tác thường dùng có thể xuất hiện ở bottom action bar theo ngữ cảnh, không tạo một hệ điều hướng thứ hai đầy đủ.
- Bảng phức tạp chuyển thành card/list hoặc cho cuộn ngang có chỉ dẫn.
- Mục tiêu chạm tối thiểu 44 × 44 px.

## Ngôn ngữ thị giác

- Font dùng system stack: `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif.
- Card bo góc 12–16 px; input/button 8–12 px.
- Nền trung tính, phân cấp bằng độ sáng và viền mảnh; không lạm dụng shadow.
- Translucency/blur chỉ dùng ở sidebar, top bar hoặc modal khi trình duyệt hỗ trợ; luôn có màu nền fallback.
- Màu nhấn mặc định teal/mint. Các theme Neo Pop/Clay Garden/Liquid Glass theo phần thưởng bài luyện hiện có; không thay quyền hoặc ý nghĩa thao tác.
- Shell và dashboard Synapse Soft dùng nền sáng thống nhất, không tự chuyển tối theo hệ điều hành. Các trang nghiệp vụ dùng cùng token và khung responsive; bố cục chi tiết vẫn cần đối chiếu với Penpot khi nghiệm thu.
- Chuyển động ngắn 150–250 ms, tôn trọng `prefers-reduced-motion`.

## Trạng thái và phản hồi

- Mọi màn hình có trạng thái loading, empty, error và permission denied.
- Thành công dùng thông báo nhẹ; hành động tài chính hoặc không thể hoàn tác cần hộp thoại xác nhận.
- Validation hiển thị gần trường lỗi và có bản tóm tắt khi form dài.
- Không dùng màu làm tín hiệu duy nhất; trạng thái phải có nhãn hoặc biểu tượng.

## Dashboard theo vai trò

### Root Admin

- Tổng số trung tâm, tenant hoạt động, cảnh báo hệ thống và phiên hỗ trợ gần đây.
- Không hiển thị dữ liệu học tập/tài chính chi tiết cho đến khi mở phiên hỗ trợ có lý do.

### Quản lý trung tâm

- Học viên đang học, lớp đang mở, tỷ lệ lấp đầy, doanh thu/công nợ và cảnh báo vận hành.
- Lối tắt cấu hình trung tâm, nhân sự và báo cáo.

### Giáo vụ/Tư vấn

- Yêu cầu đăng ký chờ duyệt, yêu cầu cần xếp lớp, công nợ, hoàn phí và chuyển trung tâm.
- Hàng đợi công việc là thành phần trung tâm của dashboard.

### Giáo viên

- Buổi dạy hôm nay, lớp phụ trách, điểm danh chưa chốt, bài cần chấm và tiến độ cần chú ý.
- Trên mobile, “Điểm danh buổi tiếp theo” là hành động nổi bật nhất.

### Học viên

- Lịch học tiếp theo, yêu cầu đăng ký, học phí, tiến độ, bài luyện tập và thông báo.
- Trên mobile, “Tiếp tục luyện tập” và lịch học gần nhất là nội dung đầu trang.

## Tiếp cận và quốc tế hóa

- Mục tiêu WCAG 2.2 AA cho tương phản, bàn phím và focus.
- Không hard-code chuỗi giao diện; Việt/Anh dùng cùng khóa dịch.
- Bố cục phải chịu được chuỗi dài hơn khoảng 30% và sẵn sàng cho RTL về mặt cấu trúc dù MVP chưa hỗ trợ RTL.
- Ngày, giờ, số và tiền tệ định dạng theo locale/tenant.
