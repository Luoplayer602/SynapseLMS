# Kế hoạch tiếp theo — Đổi/hủy buổi và giáo viên dạy thay

Ngày 2026-09-26. Người dùng xác nhận pass phần phân công/lịch cơ bản và duyệt triển khai kế hoạch này, yêu cầu tăng phạm vi nghiệp vụ mỗi phiên. Đã bổ sung lịch tuần dạng danh sách theo ngày, bộ lọc chi nhánh/phòng/giáo viên/trạng thái, mở điều chỉnh trực tiếp. Đặc tả hiện hành và checklist tại [session-operations.md](./session-operations.md). Phần dưới giữ kế hoạch gốc; không mở lại mẫu tuần đã xác nhận để sinh lại toàn bộ lịch.

## Mục tiêu và phạm vi

Cho nhân sự xử lý thay đổi thực tế trên **từng buổi tương lai** mà vẫn bảo vệ phòng, giáo viên và lịch sử. Ưu tiên trước calendar tuần/tháng vì bản hiện hành chưa thể sửa sai hoặc giải phóng lịch đã xác nhận. Thuộc nhóm vận hành lịch SCH-04/05/06/07 trong lộ trình; cần đối chiếu acceptance criteria Jira trước khi gán từng story, không coi cả nhóm đã hoàn thành.

### 1. Dữ liệu và nguyên tắc

- Thêm trạng thái buổi `scheduled/cancelled`, version và lịch sử thay đổi bất biến: người, thời điểm, loại thao tác, lý do nội bộ, snapshot trước/sau. Giữ nguyên ID buổi khi đổi lịch; không xóa cứng. Buổi cũ được migration giữ nguyên giờ/phòng/giáo viên, mặc định scheduled.
- Mẫu tuần đã xác nhận giữ làm nguồn gốc; thay đổi từng buổi không sửa mẫu hoặc các buổi khác. UI phân biệt lịch ban đầu với lịch hiện hành.
- Mặc định đề xuất: chỉ sửa/hủy/khôi phục buổi chưa bắt đầu; cả giờ cũ và giờ mới phải còn tương lai. Không sửa buổi quá khứ hoặc đang diễn ra trong phiên này.
- Giữ chi nhánh, múi giờ, hình thức và sĩ số theo lớp; đổi ngày trong khoảng ngày dự kiến của lớp, cùng ngày, không qua đêm. Nhu cầu học bù vượt khoảng ngày hoặc đổi chi nhánh/hình thức cần kế hoạch riêng, không nới âm thầm.
- Lý do bắt buộc; version chống ghi đè và khóa yêu cầu chống lặp cho mutation. Cùng khóa/cùng payload trả kết quả đã xử lý; cùng khóa/khác payload bị từ chối. Mất mạng không tự retry, hướng dẫn làm mới.

### 2. Đổi ngày/giờ/phòng

- Chọn một buổi → nhập thay đổi và lý do → xem trước tác động → xác nhận. Kiểm tra phòng đúng chi nhánh/active/đủ sức chứa, giáo viên còn hoạt động và khả năng giảng dạy theo quy tắc hiện hành.
- Backend kiểm tra lại trùng phòng, giáo viên và lớp, bỏ chính buổi đang sửa khỏi so sánh, chỉ xét các buổi scheduled. Giữ khoảng `[bắt đầu, kết thúc)` và quy tắc DST hiện hành.
- Đổi lịch là một transaction: thành công mới giải phóng giờ/phòng cũ và giữ giờ/phòng mới. Nếu xung đột, quyền bị thu hồi hoặc version cũ thì lịch ban đầu không thay đổi; không có bước bỏ giữ chỗ trước khi kiểm tra.

### 3. Hủy và khôi phục

- Hủy có xác nhận và lý do; buổi còn trong danh sách/lịch sử nhưng không chiếm phòng/giáo viên hoặc chặn lưu trữ vì đặt lịch tương lai.
- Khôi phục là hành động riêng, kiểm tra lại toàn bộ điều kiện và xung đột. Phòng đã được lớp khác dùng thì khôi phục bị chặn; không tự giành lại phòng hoặc chuyển giờ.
- Chưa hủy hàng loạt, tự sinh buổi bù hoặc hoàn phí. Hủy không tự thay công nợ/đăng ký/điểm danh; những module này chưa triển khai.
- Không mở khóa cấu trúc/mẫu lớp chỉ vì đã hủy hết buổi; tham chiếu lịch sử vẫn chặn xóa/đổi mã. Guard phòng/sĩ số/lưu trữ phải phân biệt buổi scheduled với cancelled, đồng thời giữ các guard lớp nháp hiện hữu.

### 4. Giáo viên dạy thay theo buổi

- Nhân sự thay tập giáo viên của một buổi, không đổi phân công mặc định hoặc các buổi khác. Người dạy thay có thể ngoài tập giáo viên mặc định của lớp nhưng phải có hồ sơ active cùng tenant.
- Kiểm tra năng lực đúng ngôn ngữ/cấp đầu ra; thiếu năng lực phải có lý do ngoại lệ, không bỏ qua kiểm tra xung đột giờ. Buổi scheduled luôn cần ít nhất một giáo viên.
- Điều chỉnh FK hiện hành đang bắt giáo viên buổi thuộc class_teachers: cho phép phân công trực tiếp từng buổi nhưng vẫn bảo vệ teacher/session/class/tenant và không xóa lịch sử người dạy ban đầu.
- Người được thay ra không còn thấy buổi tương lai đó trong lịch hiện hành của mình; người thay vào thấy buổi. Lịch sử nội bộ giữ người trước/sau, không mở toàn bộ nhật ký cho giáo viên. Không tự cấp quyền xem hồ sơ học viên/nhập điểm.

### 5. Quyền và giao diện

- Quản lý/giáo vụ trong tenant và Root có hỗ trợ thực hiện thay đổi; giáo viên chỉ xem lịch hiện hành của mình, không tự đổi/hủy hoặc tự chọn dạy thay. Học viên chưa có lịch khi chưa xếp lớp.
- Mở từ danh sách buổi đã xác nhận trong Giáo viên & lịch học; thêm nhãn trạng thái, chi tiết buổi, ba hành động đổi lịch/dạy thay/hủy và khôi phục cho buổi đã hủy.
- Lịch sử **riêng của buổi** phục vụ kiểm tra nghiệp vụ; không triển khai màn hình log toàn hệ thống đã hoãn. Giáo viên không nhận lý do nội bộ hoặc dữ liệu giáo viên/lớp khác ngoài phạm vi cần thiết.
- Việt/Anh, sáng/tối, mobile; cảnh báo rõ đang thay một buổi chứ không phải cả chuỗi. Chưa calendar kéo-thả, email/push/thông báo trong ứng dụng hoặc link họp online; cần nhắc nhân sự liên lạc thủ công khi đổi lịch.

## Thứ tự triển khai

1. Đối chiếu backlog và code hiện hành; chốt contract trạng thái/version/idempotency/history, migration/FK và phạm vi quyền.
2. Backend: dịch vụ kiểm tra tài nguyên dùng chung cho xác nhận ban đầu, đổi lịch, dạy thay, khôi phục; không tạo các phiên bản kiểm tra lệch nhau. Chuẩn hóa thứ tự khóa tenant → actor/support → tài khoản đích.
3. API xem trước/áp dụng thao tác, hủy/khôi phục và lịch sử phân trang; guard tài nguyên và truy vấn lịch cá nhân theo trạng thái mới.
4. UI chi tiết buổi và form xác nhận; dữ liệu trước/sau, lỗi rõ ràng, giữ dữ liệu nhập khi conflict và không tự retry.
5. Test hồi quy, migration trên SQLite/PostgreSQL tạm, test cạnh tranh PostgreSQL, UI/E2E Chromium và kiểm tra ảnh; cập nhật tài liệu/Jira rồi mới rebuild API/web và migrate DB demo, giữ volume.

## Tiêu chí nghiệm thu sau triển khai

- Đổi một buổi hợp lệ: chỉ buổi đó đổi, tài nguyên cũ rảnh, tài nguyên mới được giữ; ID không đổi.
- Đổi sang phòng/giáo viên/giờ trùng: bị chặn, lịch cũ nguyên vẹn; hai buổi liền giờ vẫn hợp lệ.
- Hủy: giữ bản ghi/lý do/lịch sử, tài nguyên được dùng lại. Khôi phục sau khi tài nguyên đã bị chiếm: bị chặn; khi trống và hợp lệ: thành công.
- Dạy thay: lịch giáo viên cũ/mới đúng sau làm mới; không đổi giáo viên các buổi khác; thiếu năng lực cần lý do, sai tenant/không active bị chặn.
- Buổi đã bắt đầu/quá khứ và người không có quyền không thể sửa; không rò lý do nội bộ qua API giáo viên.
- Hai người đổi cùng buổi, đổi lịch cạnh tranh xác nhận lớp khác, hủy/khôi phục cạnh tranh đặt phòng, khóa tài khoản/thu hồi support: không đặt trùng, không ghi đè, không lưu một phần hoặc lỗi deadlock 500.
- Gửi lặp cùng yêu cầu không tạo lịch sử trùng; migration giữ nguyên lịch đã xác nhận; các test catalog/auth/phân công/lịch cơ bản vẫn đạt.

## Sau bước này

Lập kế hoạch lịch tuần/tháng và bộ lọc phòng/giáo viên để dễ kiểm tra sử dụng tài nguyên; tiếp đó thông báo và nền học phí trước khi duyệt đăng ký tạo hóa đơn/xếp lớp. Lịch rảnh giáo viên, quy tắc nghỉ/bù hàng loạt, link online, màn hình log chung, BUG-004 và học liệu/AI tiếp tục tách riêng.

Không cần tắt container để lập kế hoạch/code. Khi bàn giao bản triển khai, chỉ thay API/web và chạy migration đã kiểm thử; PostgreSQL/Mailpit tiếp tục chạy. Đề cử cho phiên code: GPT gpt-6-astra high (giữ lựa chọn hiện tại); chưa bắt đầu code từ kế hoạch này.
