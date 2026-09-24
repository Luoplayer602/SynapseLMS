# Ghi nhận trong quá trình nghiệm thu

Ban đầu chỉ ghi nhận; người dùng đã cho phép triển khai kế hoạch. Các mục dưới đây đã sửa và qua kiểm thử tự động, chờ người dùng nghiệm thu lại.

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
