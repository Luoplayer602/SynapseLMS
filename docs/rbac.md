# Ma trận phân quyền SynapseLMS

**Phiên bản:** 0.1  
**Nguyên tắc:** từ chối mặc định; mọi truy vấn nghiệp vụ phải nằm trong tenant hiện tại.

Mỗi tài khoản chỉ có một vai trò nghiệp vụ và một tenant đang hoạt động tại một thời điểm. Không kết hợp vai trò giáo viên với quản lý/giáo vụ trên cùng tài khoản. Root Admin không phải membership của một tenant.

| Năng lực | Root Admin | Quản lý trung tâm | Giáo vụ/Tư vấn | Giáo viên | Học viên |
|---|---|---|---|---|---|
| Quản lý trung tâm/tenant | Toàn hệ thống | Không | Không | Không | Không |
| Cấu hình trung tâm/chi nhánh | Hỗ trợ | Trung tâm mình | Xem | Không | Không |
| Quản lý tài khoản và vai trò | Toàn hệ thống | Trung tâm mình | Hạn chế | Không | Hồ sơ mình |
| Quản lý học viên | Hỗ trợ | Trung tâm mình | Tạo/sửa/xem | Lớp phụ trách | Hồ sơ mình |
| Quản lý giáo viên | Hỗ trợ | Trung tâm mình | Tạo/sửa/xem | Hồ sơ mình | Không |
| Quản lý khóa học/lớp | Hỗ trợ | Toàn quyền trong tenant | Vận hành | Xem lớp phụ trách | Xem lớp công khai/đã học |
| Gửi yêu cầu đăng ký | Không | Có | Có | Không | Có |
| Duyệt đăng ký | Không | Có | Có | Không | Không |
| Quản lý học phí | Chỉ khi hỗ trợ có lưu vết | Toàn quyền trong tenant | Thu, điều chỉnh và hoàn phí có lý do | Chỉ xem khi được cấp | Học phí của mình |
| Điểm danh | Không | Xem/sửa theo quyền | Xem/sửa | Lớp hoặc buổi phụ trách | Xem của mình |
| Nhập và công bố điểm | Chỉ khi hỗ trợ có lưu vết | Xem/khóa, không sửa nội dung điểm | Không được sửa | Lớp phụ trách | Xem điểm đã công bố |
| AI tư vấn lớp | Không | Xem cấu hình | Sử dụng | Không mặc định | Nhận tư vấn |
| AI tạo bài tập | Không | Xem cấu hình | Không mặc định | Lớp phụ trách | Làm bài được giao |
| Xem tóm tắt tiến độ | Không | Theo quyền trung tâm | Theo quyền nghiệp vụ | Lớp phụ trách | Bản thân |
| Xem audit log | Toàn hệ thống | Trung tâm mình | Hạn chế | Không | Không |

## Quy tắc bắt buộc

- Nền lớp học đã triển khai: chi nhánh/phòng quản lý hoặc Root hỗ trợ được ghi, giáo vụ chỉ xem; lớp nháp cả quản lý/giáo vụ/Root hỗ trợ được ghi. Giáo viên/học viên chưa được truy cập. Hiện scope toàn tenant, chưa giới hạn nhân sự theo từng chi nhánh. Xem [class-foundation.md](./class-foundation.md).

1. Root Admin được truy cập dữ liệu tenant để hỗ trợ kỹ thuật, nhưng phải chọn tenant, cung cấp lý do và tạo audit log cho phiên hỗ trợ.
2. Quản lý, giáo vụ và giáo viên luôn bị giới hạn bởi `organization_id`.
3. Giáo viên còn bị giới hạn bởi phân công lớp hoặc buổi học.
4. Học viên chỉ truy cập tài nguyên của bản thân và nội dung được công bố.
5. Giáo vụ được thực hiện hoàn phí; mỗi lần hoàn phải có lý do, số tiền, người thực hiện, thời điểm và audit log.
6. Chỉ giáo viên phụ trách được nhập hoặc sửa nội dung điểm. Quản lý có thể xem/khóa bảng điểm; giáo vụ chỉ được xem.
7. Thay đổi học phí, hoàn phí, điểm đã khóa, điểm danh đã chốt và quyền người dùng đều phải có audit log.
8. Quyền chi tiết có thể cấu hình theo tenant nhưng không được vượt quá giới hạn an toàn của vai trò gốc.
9. Chuyển trung tâm kết thúc membership cũ và mở membership mới; không tạo hai membership hoạt động đồng thời.
10. Trung tâm mới chỉ đọc lịch sử do trung tâm cũ tạo, đặc biệt không được sửa hoặc thu hộ các khoản công nợ nguồn.

## Quyết định đã xác nhận

- TCH-01/TCH-02: quản lý/giáo vụ quản lý hồ sơ/năng lực/chứng chỉ trong tenant, Root cần hỗ trợ; giáo viên chỉ xem bản thân và sửa điện thoại/giới thiệu. Không trả ghi chú/lý do nội bộ cho giáo viên. Lưu trữ hồ sơ làm toàn bộ phần giáo viên chỉ đọc nhưng không khóa tài khoản; năng lực không cấp quyền lớp/học viên/điểm. Xem [teacher-profiles.md](./teacher-profiles.md).

- STU-03: học viên tự khai/sửa mục tiêu và đọc lịch sử công khai của mình; quản lý/giáo vụ và Root có hỗ trợ được thêm mục, sửa mục tiêu, xác nhận/điều chỉnh/thu hồi có căn cứ/lý do, không tự khai thay. Căn cứ/lý do nội bộ không trả qua API học viên. Hồ sơ lưu trữ chặn mọi mutation trình độ; giáo viên chưa mở quyền khi chưa có phân công. Quyền nhập điểm không thay đổi. Xem [student-proficiencies.md](./student-proficiencies.md).

- Bổ sung bảo trì catalog sau BUG-003: chỉ quản lý/Root hỗ trợ được sửa mã hoặc xóa mục chưa sử dụng; khóa phải là nháp chưa từng công bố. Yêu cầu lý do/version; xóa cần mã hiện tại để xác nhận, giữ audit, không xóa dây chuyền. Giáo vụ/giáo viên/học viên không có quyền này.

- Khóa học đã triển khai: quản lý/Root hỗ trợ được tạo và đổi nhãn danh mục, sửa khóa nháp và chuyển trạng thái có lý do; giáo vụ chỉ xem cấu hình, tạo/sửa nháp, không công bố/lưu trữ. Học viên chỉ đọc khóa công bố trong tenant; giáo viên chưa mở quyền khi chưa có lớp. Bảng tổng quan bên trên bao gồm quyền dự kiến của các module tương lai, không có nghĩa tất cả đã được triển khai. Chi tiết: [course-catalog.md](./course-catalog.md).

- Hồ sơ học viên đã triển khai cho quản lý/giáo vụ trong tenant, Root có hỗ trợ và học viên với hồ sơ của chính mình. Học viên không nhận ghi chú nội bộ từ API. Hồ sơ lưu trữ chỉ đọc cho học viên, không tự khóa tài khoản. Quyền giáo viên xem học viên lớp phụ trách chưa mở vì module phân công lớp chưa triển khai; mặc định từ chối API hồ sơ. Chi tiết: `student-profiles.md`.

- Root Admin có quyền truy cập hỗ trợ vào tenant với lý do và audit log.
- Giáo vụ không được nhập hoặc sửa điểm.
- Giáo vụ được hoàn phí mà không cần bước duyệt bắt buộc của quản lý; thao tác vẫn phải có lý do và audit log.
