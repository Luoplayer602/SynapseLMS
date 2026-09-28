# Đợt tuyển sinh và vận hành học viên

Kế hoạch được duyệt ngày 2026-09-27; đã triển khai Docker/migration 0013 ngày 2026-09-27, chờ người dùng nghiệm thu thủ công. 19 story Jira đã có comment kết quả, giữ In Progress.

Phạm vi: học phí khóa/trả góp/mã giảm giá; yêu cầu đăng ký và duyệt tạo hóa đơn nguyên tử; tự xếp khi đúng một lựa chọn chắc chắn, hàng chờ thủ công; thu tiền/đảo khoản thu/phiếu thu in; lịch học viên; điểm danh theo giáo viên từng buổi; thông báo trong ứng dụng. Không bảo lưu/hoàn phí/chuyển lớp/AI/học liệu/cổng thanh toán trong đợt này.

Mặc định đã được duyệt cùng kế hoạch: một mã mỗi yêu cầu, tiêu thụ khi duyệt; chặn công nợ tính toàn bộ số còn phải trả nếu bật; tự xếp lớp chưa bắt đầu và đang nhận học viên, không đoán khi thiếu dữ liệu; không thu vượt nợ/không ví; chưa điểm danh khác vắng. Học phí tiền nguyên VND trong lần triển khai này; không xuất hóa đơn thuế. Phiếu thu dùng trang in của Chrome. Kỳ trả góp tính theo ngày duyệt (UTC), hiển thị rõ ngày đến hạn. Không đặt yêu cầu đã thu đủ mới xếp lớp.

Mốc kỹ thuật: (1) dữ liệu/API/giao dịch và kiểm thử; (2) UI Việt/Anh nối luồng; (3) test tích hợp/đồng thời/E2E, migration và Docker; (4) cập nhật tài liệu/Jira, checklist. Không tự stage/commit; giữ thay đổi compose.yaml của người dùng. Không triển khai migration DB thật trước khi kiểm chứng.

Rủi ro cần kiểm tra: hai lần duyệt/thu/tranh chỗ cuối, lượt mã cuối, thu đồng thời với đảo thu, đổi lịch gây trùng lịch học viên, thu hồi quyền trong lúc ghi, rò rỉ dữ liệu giữa trung tâm/người học; không sửa/xóa tài chính và lịch sử bằng CRUD chung.

## Cách sử dụng

1. Root mở hỗ trợ trung tâm; hoặc dùng quản lý/giáo vụ. Vào **Thiết lập tuyển sinh**, mở khóa đã công bố, nhập học phí và các kỳ trả góp. Ví dụ 1.000.000 VND, 50% ngày 0 + 50% ngày 30. Mỗi khóa một chính sách; có version, lịch sử cấu hình và kiểm tra tổng tỷ lệ 100%/ngày tăng dần.
2. Tại cùng màn hình, tạo mã giảm giá nếu cần, bật nhận học viên cho lớp có lịch đã xác nhận và chưa bắt đầu. Có thể dừng nhận mà không ảnh hưởng học viên đã xếp. Nút **Danh sách lớp** hiển thị enrollment, không phải danh sách yêu cầu còn chờ.
3. Học viên hoặc giáo vụ vào **Tuyển sinh**, chọn khóa/học viên, chi nhánh/hình thức và các khoảng rảnh theo ngày trong tuần. Hồ sơ cần họ tên/ngày sinh/điện thoại, tài khoản và membership học viên hoạt động. Giá học phí gốc hiện ở lựa chọn khóa; giá/mã ưu đãi được kiểm tra lại tại thời điểm duyệt.
4. Giáo vụ duyệt hoặc từ chối có lý do. Duyệt lập hóa đơn ngay, kể cả chưa xếp được lớp. Chỉ tự xếp nếu có đúng một ứng viên không cần xem xét thêm. Thiếu trình độ được trung tâm xác nhận hoặc lịch rảnh không chắc chắn → hàng chờ; giáo vụ xem cảnh báo và xác nhận thủ công bằng lý do. Không cho bỏ qua trùng lịch/sĩ số/trạng thái lớp/chi nhánh/hình thức.
5. **Học phí & thu tiền**: xem kỳ đến hạn, tổng phải thu/đã thu/còn nợ/quá hạn; mở hóa đơn để thu tiền mặt/chuyển khoản. Kỳ sớm nhất được phân bổ trước. Chỉ ghi nhận nghiệp vụ nội bộ, hệ thống không chuyển tiền qua ngân hàng. Phiếu thu có mã UUID, ngày, trung tâm/học viên/khóa/số tiền/phương thức/tham chiếu; mở phiếu rồi **In phiếu thu**, dùng Chrome Save as PDF.
6. Thu nhập nhầm → **Đảo khoản thu nhập nhầm**, lý do bắt buộc. Giữ khoản thu gốc và người/thời điểm đảo, khoản đã đảo không tính vào đã thu; công nợ tăng lại. Không phải hoàn học phí và không thực hiện lệnh ngân hàng.
7. Giáo viên dùng **Điểm danh**, chỉ thấy các buổi mình đang phụ trách, mở danh sách. Chỉ được ghi từ lúc buổi bắt đầu. Lưu nháp hoặc chốt; không chốt nếu còn “chưa điểm danh”. Sau chốt chỉ sửa với lý do, không quay lại nháp. Ghi chú sau chốt được học viên xem nên không nhập ghi chú nội bộ vào đây.
8. Học viên dùng **Học tập của tôi** để xem lịch sắp tới và chuyên cần, **Học phí & thu tiền** chỉ cho dữ liệu của mình. Nhân sự không nhập điểm danh thay giáo viên, kể cả Root hỗ trợ.

## Quy tắc dữ liệu và quyền

- Tiền nguyên VND dùng BigInteger, giới hạn 1 tỷ mỗi học phí/giao dịch, không float; chưa đa tiền tệ. Phần lẻ do phân kỳ được dồn vào kỳ cuối; giảm phần trăm làm tròn xuống đồng. Công nợ tổng không đồng nghĩa quá hạn; kỳ quá hạn khi ngày đến hạn UTC nhỏ hơn ngày hiện tại và còn nợ.
- Một mã/yêu cầu; không giữ lượt lúc gửi, chỉ tiêu thụ trong transaction duyệt. Mã đúng tenant/khóa (hoặc toàn tenant), còn hiệu lực theo ngày UTC, active/còn lượt. Sửa học phí sau duyệt không sửa hóa đơn cũ. Mã sai/hết hạn cần từ chối và gửi yêu cầu mới trong bản này; chưa có sửa yêu cầu đã gửi.
- Duyệt, hóa đơn, enrollment nếu tự xếp và các thông báo cùng transaction. Không đủ lớp là kết quả nghiệp vụ `waiting`, không rollback hóa đơn. Lỗi tài chính/quyền/validation rollback toàn bộ. Chưa có hủy hóa đơn hoặc thu hồi quyết định duyệt; không dùng đảo khoản thu để xóa nghĩa vụ học phí.
- PostgreSQL dùng khóa organization → actor/support → tài khoản học viên, kiểm tra lại dưới khóa. Mutation lịch dùng cùng khóa tenant. Row locks không có bảo đảm tương đương trên SQLite; nên dùng PostgreSQL khi nhiều nhân sự ghi đồng thời.
- Mọi mutation nghiệp vụ có request_key + hash action/target/body và ràng buộc actor. Cùng key/payload trả snapshot đã lưu, không thu/duyệt lại; key khác payload/actor bị 409. Version chặn sửa cấu hình/yêu cầu/điểm danh cũ. Sau replay đọc lại để thấy trạng thái mới nhất.
- Từ chối yêu cầu hiển thị lý do cho học viên; lịch sử nghiệp vụ nội bộ chỉ nhân sự. Giáo viên chỉ đọc roster và lịch sử điểm danh các buổi được phân công, không đọc công nợ/hồ sơ nội bộ. Học viên chỉ thấy điểm danh đã chốt của mình; draft không xuất hiện trong chuyên cần.
- Chuyên cần hiện tại: (có mặt + muộn) / (có mặt + muộn + vắng); loại có phép/chưa đánh dấu/buổi hủy. Chưa có tỷ trọng theo khóa hoặc báo cáo tổng hợp cả lớp.
- Không xóa cứng invoices/payments/business_operations qua API. AttendanceSheet lưu một roster JSON/buổi, mỗi student_id duy nhất, kiểm tra tập ID đúng enrollment tại giờ bắt đầu. BusinessOperation giữ snapshot các lần lưu/chốt/sửa. Quan hệ scope chính dùng FK tổng hợp trong DB; thành viên JSON được kiểm tra qua API.
- Mã/xóa khóa có tham chiếu phí/mã ưu đãi/đăng ký bị chặn. Lưu trữ hồ sơ học viên còn yêu cầu submitted/waiting hoặc buổi scheduled tương lai bị chặn. Không tự khóa/xóa tài khoản để xử lý nghĩa vụ tài chính.
- Cập nhật lịch một buổi kiểm tra thêm trùng lịch của học viên đã xếp; lỗi giữ nguyên buổi cũ. Enrollment không thay đổi khi hủy/khôi phục/dạy thay.

## Thông báo

`notifications` là inbox bền vững theo tenant + user + event_key. Ghi cùng giao dịch, không gọi mạng. Có unread/read, phân trang và chuông đọc lại mỗi phút; không WebSocket. Thông báo không thay quyền của trang đích.

- Giáo vụ/quản lý đang hoạt động: yêu cầu mới và cần xếp thủ công.
- Học viên: quyết định/hóa đơn qua thông báo duyệt, xếp lớp, thu/đảo thu, thay đổi buổi đã enrollment.
- Giáo viên cũ và mới của buổi: đổi lịch/hủy/khôi phục/dạy thay. Thông báo không chứa lý do override nội bộ.
- Nội dung thông báo buổi chỉ lấy tên lớp/giờ/múi giờ/phòng từ snapshot SessionHistory đúng version của sự kiện, không đọc trạng thái hiện tại. Giáo viên đã bị thay ra vì vậy không thấy các thay đổi sau mà họ không còn là người nhận; lý do/waiver/history đầy đủ không được trả vào inbox.
- Root hỗ trợ không giả danh người nhận của trung tâm; inbox chỉ của chính Root nên có thể trống. Nhân sự có thể xem yêu cầu trong Tuyển sinh.
- Liên kết mở module tương ứng, chưa deep-link tới một bản ghi ở trang khác. Email/SMS/Zalo/push chưa gửi; hàm phát sự kiện dùng chung là điểm mở rộng, chưa có worker/adapter gửi ngoài ứng dụng.

## API chính

Tất cả dưới `/api/v1`, có auth/tenant/browser guard và no-store. Danh sách trả items/total/limit/offset, mặc định 20, tối đa 100.

| Nhóm | Endpoint |
| --- | --- |
| Thiết lập | GET/PUT `/admissions/settings`; PUT `/admissions/fees/{course_id}`; GET/POST `/admissions/discounts`; PUT `/admissions/discounts/{id}` |
| Nhận học viên | GET `/admissions/options`, `/admissions/openings`; PUT `/admissions/openings/{class_id}`; GET `/admissions/classes/{class_id}/roster` |
| Đăng ký | GET/POST `/admissions/requests`; POST `/{request_id}/decision`, `/{request_id}/placement`; GET `/{request_id}/candidates` (đều nối dưới requests) |
| Tài chính | GET `/admissions/invoices`, `/admissions/invoices/{id}`; POST `/admissions/invoices/{id}/payments`, `/admissions/payments/{id}/reverse` |
| Lịch sử | GET `/admissions/history/{target_id}` cho nhân sự; không có endpoint sửa/xóa |
| Học viên | GET `/admissions/my-sessions`, `/attendance/mine` |
| Giáo viên | GET `/attendance/sessions`; GET/PUT `/attendance/sessions/{id}`; GET `/attendance/sessions/{id}/history` |
| Inbox | GET `/notifications`; POST `/notifications/{id}/read` (đọc lặp không tạo bản ghi mới) |

Mutation dùng `request_key` UUID; thao tác sửa còn có `version` (0 khi chưa có cấu hình/sheet). Chỉ quản lý/Root hỗ trợ sửa block_debt; giáo vụ được cấu hình phí/mã/mở nhận, duyệt/xếp/thu/đảo. Chỉ giáo viên hiện hành của buổi sửa điểm danh, không staff/Root.

## Giới hạn và phạm vi chưa làm

- Không nhập học giữa khóa, chuyển lớp, bảo lưu/hoàn phí, rút yêu cầu đã duyệt, hoàn thành enrollment hoặc học lại cùng khóa đã placed. Các trạng thái vòng đời này cần đợt sau; hiện không tự đóng enrollment theo ngày.
- Hàng chờ là yêu cầu cần xếp thủ công, chưa phải hàng đợi FIFO/waitlist theo lớp. Chưa tự chạy lại xếp lớp khi thêm lớp/mở chỗ; giáo vụ chủ động thao tác.
- Không báo cáo doanh thu toàn trung tâm/xuất Excel, cảnh báo vắng ngưỡng, nhắc nợ tự động, QR hoặc điểm số. Tỷ lệ hiện chỉ cho học viên; ATT-05 chưa hoàn tất báo cáo lớp.
- Options tải dữ liệu chọn toàn tenant; API inbox/danh sách chính phân trang. Chưa tối ưu cho dữ liệu lớn; không hứa hiệu năng quy mô lớn hoặc lưu trữ history vô hạn không cần chính sách.
- Phiếu thu in/lưu PDF qua trình duyệt, chưa dịch vụ sinh PDF phía server và chưa số phiếu tuần tự. Snapshot hóa đơn giữ khóa/chính sách; tên trung tâm/học viên và phiếu in lấy nhãn hiện tại. Chưa chứng từ kế toán bất biến đầy đủ.
- BUG-004 select native Chrome và UI log toàn hệ thống vẫn hoãn. Lịch sử ở đây không thay màn hình log toàn hệ thống.

## Kiểm chứng và nghiệm thu

Migration `20260927_0013` chỉ thêm 11 bảng, không backfill/đổi buổi hiện có; downgrade từ chối nếu bất kỳ bảng mới có dữ liệu. Test dùng SQLite tạm/PostgreSQL schema test, không seed DB thật.

- Kết quả đã hoàn tất: full backend 449 đạt/58 skip/0 lỗi; vòng cuối 48 đạt/3 skip/0 lỗi (có trùng full), schema bổ sung 1 đạt; UI 72 đạt, toàn bộ 15 E2E đạt và ca admissions cuối đạt; Ruff/ESLint/build đạt. Phiên bàn giao chỉ đọc lại báo cáo và kiểm tra triển khai, không chạy lại full test.
- Triển khai thực tế: Alembic `20260927_0013 (head)`, schema check sạch; API health/web/module Admissions/Mailpit HTTP 200, OpenAPI có đủ 24 path ba nhóm mới, không `__test`. Hash/count 10 bảng cũ khớp trước/sau, 11 bảng mới rỗng lúc bàn giao; giữ DB/Mailpit/volume/compose.yaml, không .env/seed/commit/stage. Bằng chứng và comment IDs: [checkpoint](./next-session-handoff.md).

### Checklist theo vai trò

Các ca dưới đây dành cho người dùng nghiệm thu bằng dữ liệu phù hợp trong trung tâm kiểm thử; phiên triển khai chưa tự tạo dữ liệu. Không sửa đồng hồ DB thật để thử điểm danh.

| Vai trò | Thao tác và kết quả cần đạt |
| --- | --- |
| Root hỗ trợ / quản lý | Mở đúng trung tâm; đặt phí 1.000.000 VND, hai kỳ 50/50, mã giảm 10%, mở nhận lớp có lịch tương lai. Kiểm tra bật/tắt chặn nợ; inbox Root chỉ của chính Root; không được điểm danh thay. |
| Giáo vụ | Duyệt một lần ra hóa đơn 900.000, hai kỳ 450.000; đủ điều kiện tự xếp, thiếu dữ liệu vào waiting rồi xếp thủ công có lý do. Thu 300.000 còn 600.000; đảo có lý do nợ lại 900.000 và giữ lịch sử. In/lưu PDF chỉ có phiếu. Không đổi công tắc chặn nợ hoặc điểm danh thay. |
| Học viên | Đủ hồ sơ mới gửi được; chỉ xem yêu cầu, lịch, hóa đơn, chuyên cần đã chốt và inbox của mình. Đánh dấu thông báo đã đọc giảm unread; không thấy bản nháp điểm danh. |
| Giáo viên thực tế của buổi | Sau giờ bắt đầu, mở roster → lưu nháp → chốt đủ trạng thái; sửa sau chốt có lý do/lịch sử. Giáo viên không còn phụ trách không được ghi. |
| Kiểm tra chung | Trùng lịch/hết chỗ/thu quá nợ/sai quyền hoặc tenant/version cũ phải bị chặn; retry không nhân đôi; không có dữ liệu dở dang. Đổi/hủy/khôi phục/dạy thay tạo đúng thông báo liên quan. |

### Ca kiểm tra chi tiết

1. Cấu hình phí 1.000.000, hai kỳ 50/50; tổng tỷ lệ khác 100 bị từ chối. Tạo mã 10% còn hạn, một lượt.
2. Học viên thiếu điện thoại/ngày sinh không gửi được. Đủ hồ sơ gửi một lần; đăng ký trùng cùng khóa bị chặn.
3. Duyệt sinh đúng một hóa đơn 900.000, hai kỳ 450.000; retry không nhân đôi. Người thứ hai không dùng được lượt mã đã hết. Từ chối cần lý do học viên nhìn thấy.
4. Một lớp chắc chắn phù hợp → tự xếp; thiếu lịch rảnh → chờ thủ công. Lớp hết chỗ hoặc trùng lịch không được xếp. Hai người tranh chỗ cuối không vượt sĩ số trên PostgreSQL.
5. Thu 300.000 → còn 600.000, kỳ đầu còn 150.000; thu quá nợ bị chặn. In phiếu. Đảo khoản thu có lý do → nợ về 900.000, giữ lịch sử khoản gốc. Đây chỉ là ghi nhận test nội bộ, không có tiền chuyển tự động.
6. Bật chặn công nợ bằng quản lý: gửi/duyệt khóa mới bị chặn khi còn nợ; tắt thì cho phép. Giáo vụ không tự đổi công tắc này.
7. Học viên thấy đúng lịch/hóa đơn của mình; đổi lịch buổi trùng lịch khác của học viên bị chặn; hủy ẩn khỏi lịch và tạo đúng một thông báo khi retry, không tự hoàn phí.
8. Giáo viên đúng buổi điểm danh từ lúc bắt đầu, lưu nháp chưa hiện cho học viên; chốt cần đủ trạng thái; sửa sau chốt cần lý do. Giáo viên khác, nhân sự và học viên không ghi được.
9. Học viên xem tỷ lệ/chuyên cần đã chốt; inbox có thông báo riêng, đánh dấu đã đọc giảm unread. Kiểm tra tenant khác không xem/sửa được.
10. Hai tab sửa cấu hình/duyệt/điểm danh: tab cũ báo xung đột, không ghi đè. Khi mất mạng sau xác nhận, làm mới để đối chiếu trước thao tác tiếp.
