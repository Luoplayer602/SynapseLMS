# Kết quả học tập: mẫu điểm, sổ điểm và công bố

Đợt RES-01–05 và phần khóa sổ RES-07 dùng migration `20260930_0015`. Không tạo mẫu, sổ hay điểm mặc định cho dữ liệu cũ. Lớp chưa có mẫu đang công bố vẫn học, điểm danh và thu phí bình thường.

## Luồng và quyền

Quản lý trung tâm (hoặc Root có phiên hỗ trợ đúng tenant) tạo mẫu đầu điểm cho khóa học, mỗi đầu điểm có mã, tên, kỹ năng, điểm tối đa hai chữ số thập phân và trọng số basis point. Tổng trọng số phải bằng 10.000 trước khi công bố. Một khóa chỉ có một mẫu đang công bố; mẫu đã công bố không sửa, muốn thay đổi thì clone phiên bản nháp mới rồi ngừng dùng mẫu cũ. Giáo vụ xem mẫu nhưng không sửa.

Giáo viên có hồ sơ còn hoạt động và `ClassTeacher` của lớp khởi tạo một sổ duy nhất từ mẫu đang công bố của đúng khóa; sổ chụp snapshot, không tự đổi khi mẫu gốc đổi. Quyền dạy thay một buổi không cấp quyền sổ lớp. Giáo viên đặt `assessed_at` UTC, tùy chọn buổi cùng lớp, trước khi chấm; không đổi thời điểm khi đã có điểm. Roster lấy từ `EnrollmentPeriod` hiệu lực tại thời điểm đánh giá. Bảo lưu/hủy về sau không xóa điểm cũ và học viên vào lớp sau thời điểm đánh giá không được chấm đầu điểm đó.

Lưu điểm hàng loạt theo đầu điểm yêu cầu đúng toàn bộ roster, `version` và `request_key`. Điểm là Decimal từ 0 tới điểm tối đa; ô trống là chưa chấm, không phải 0. Nhận xét là công khai cho học viên. Trước khi công bố giáo viên sửa tự do; sau khi đã đến giờ công bố cần lý do nội bộ và lịch sử trước/sau; khi khóa sổ không thể sửa. Quản lý chỉ xem và khóa/mở khóa có lý do, không sửa điểm; giáo vụ chỉ xem. Học viên chỉ thấy enrollment của chính mình khi `publish_at <=` giờ server, không thấy lý do/actor nội bộ. Đã công bố không được lùi/hủy thời điểm để che kết quả.

Điểm tổng thang 100 bằng tổng `(điểm / điểm tối đa) × trọng số`, làm tròn hai số theo half-up. Nếu học viên chỉ đủ điều kiện một phần đầu điểm thì chuẩn hóa trên phần trọng số đó và trả `coverage_percent`; bất kỳ đầu điểm đủ điều kiện nào chưa chấm khiến `final_score=null`. Kỹ năng tính riêng trên đầu điểm cùng kỹ năng; `general` chỉ góp tổng. Chuyên cần từ điểm danh đã chốt chỉ là tham khảo, không quyết định đạt/rớt. Chưa có pass/fail, tự hoàn thành enrollment, chứng chỉ, xuất Excel/PDF, AI hoặc notification hẹn giờ. Công bố hẹn giờ hiển thị khi đến giờ qua truy vấn, không chạy worker.

## API và dữ liệu

Mọi endpoint nằm dưới `/api/v1/results`, xác thực và `Cache-Control: no-store`:

| Nhóm | Endpoint |
| --- | --- |
| Mẫu | `GET/POST /schemes`, `GET/PATCH /schemes/{id}`, `POST /schemes/{id}/publish`, `/retire`, `/clone` |
| Sổ lớp | `GET /classes`, `POST /classes/{class_id}/gradebook`, `GET /classes/{class_id}` |
| Điểm | `POST /classes/{class_id}/items/{item_id}/timing`, `PUT /classes/{class_id}/items/{item_id}` |
| Công bố/khóa | `POST /classes/{class_id}/publication`, `/lock`, `/unlock` |
| Cá nhân | `GET /mine?limit=…&offset=…` |

Lệnh ghi dùng UUID `request_key`; đổi payload với cùng key bị từ chối. `version` chặn tab cũ. `BusinessOperation` lưu kết quả, trước/sau và audit actor; nội dung này không trả cho học viên. Năm bảng mới: `course_grading_schemes`, `course_grading_components`, `class_gradebooks`, `class_grade_items`, `student_scores`. FK tổng hợp ghim course/class/tenant và enrollment/class/tenant. Downgrade bị từ chối nếu bảng kết quả đã có dữ liệu. UI ở `/grading-settings`, `/gradebook`, `/my-results`, Việt–Anh, desktop/mobile.

## Nghiệm thu thủ công

- Quản lý/Root hỗ trợ: thử tổng trọng số sai, công bố, clone/ngừng dùng mẫu; xem sổ và khóa/mở khóa có lý do; không có quyền sửa nội dung điểm.
- Giáo vụ: xem mẫu và sổ, không có nút chấm/công bố/khóa; API ghi trực tiếp trả 403.
- Giáo viên phụ trách: tạo sổ, đặt thời điểm, nhập điểm thập phân và nhận xét, thử sai một dòng để kiểm tra rollback; hẹn công bố và sửa sau công bố phải có lý do; bị chặn sau khóa.
- Giáo viên dạy thay/lớp khác: không xem hoặc sửa sổ không phụ trách; sau thu hồi phân công cũng bị chặn.
- Học viên: trước giờ công bố chưa thấy điểm; sau giờ chỉ thấy điểm và nhận xét của mình, coverage/kỹ năng/chuyên cần; bảo lưu sau bài không làm mất điểm cũ.
- Vận hành: kiểm tra mobile/keyboard/light-dark, hai tab cùng version, health và endpoint DB sau restart; DB/Mailpit/volume và dữ liệu cũ còn nguyên. Việc người dùng nghiệm thu cần ghi riêng sau khi tự kiểm tra.

Bằng chứng kiểm thử, migration và triển khai cụ thể nằm ở [kế hoạch đợt kết quả](./plans/learning-results.md), mục 9; checkpoint ngắn ở [current-state](./current-state.md).
