# Phân công giáo viên và lịch học cơ bản

Kế hoạch được người dùng duyệt ngày 2026-09-26; đã triển khai, chờ nghiệm thu. CLS-03, phần lịch tuần/sinh buổi/chống trùng SCH-01/02/03. Không phải hoàn tất toàn bộ vận hành lịch hay lịch rảnh giáo viên.

## Quy tắc đã chọn cho lát cắt này

- Quản lý/giáo vụ và Root đang hỗ trợ phân công một hoặc nhiều giáo viên active trong tenant; năng lực đối chiếu **đúng cấp đầu ra và ngôn ngữ snapshot của lớp**, không tự suy ra cấp thấp. Thiếu năng lực là cảnh báo, phải ghi lý do để vẫn phân công. Giáo viên chỉ xem những buổi được phân công, không thấy lý do nội bộ.
- Một mẫu lịch tuần cho mỗi lớp: khoảng ngày nằm trong ngày dự kiến của lớp, tối đa 366 ngày; tối đa 14 khung/tuần, 500 buổi và 20 giáo viên/lớp. Mỗi khung có thứ (0 = thứ Hai), giờ bắt đầu/kết thúc cùng ngày, phòng và tập giáo viên thuộc phân công lớp. Chưa ca qua đêm, ngoại lệ/ngày nghỉ, thời gian đệm hoặc lịch rảnh.
- Lưu nháp được thiếu phòng/giáo viên, không giữ tài nguyên. Xem trước sinh các buổi trong bộ nhớ, nêu thiếu thông tin/xung đột và phòng không khả dụng. Lịch trực tiếp/kết hợp phải có phòng đủ sức chứa; online không gắn phòng. Xác nhận chỉ khi đủ giáo viên hoạt động, chi nhánh/phòng hợp lệ và không xung đột.
- Chồng giờ dùng khoảng nửa mở `[bắt đầu, kết thúc)`: buổi trước kết thúc đúng giờ buổi sau bắt đầu được phép. Chặn trùng phòng, trùng giáo viên (kể cả khác chi nhánh) và tự trùng lớp. Giáo viên vẫn chỉ có một tenant active theo mô hình hiện hành; chưa giáo viên dùng chung nhiều trung tâm.
- Giờ nhập theo múi giờ IANA của chi nhánh, lưu UTC và tên múi giờ trên buổi. Từ chối giờ không tồn tại hoặc nhập nhằng do DST, không tự chọn offset. Chưa thay đổi múi giờ chi nhánh có lịch xác nhận.
- Xác nhận kiểm tra lại dưới khóa tenant và tạo toàn bộ buổi/phân công trong một transaction; không lưu một phần, không tự retry. `confirmation_key` + digest bản xem trước bảo đảm gửi lại cùng yêu cầu không nhân đôi; dữ liệu đổi sau xem trước phải xem lại. Xem trước không bảo đảm tài nguyên còn trống đến lúc xác nhận.
- Sau xác nhận khóa mẫu lịch/phân công và cấu trúc lớp (ngày, sĩ số, chi nhánh, phòng mặc định, hình thức), vẫn sửa được tên lớp. Chặn sửa mã lớp đã có buổi; chặn lưu trữ lớp/giáo viên/cơ sở vật chất còn buổi tương lai và giảm sức chứa phòng dưới sĩ số buổi tương lai, kể cả phòng khác mặc định lớp. Không ngăn việc thu hồi quyền/khóa tài khoản vì an toàn; lịch đã giữ vẫn tồn tại và chưa tự hủy.
- Lớp vẫn trạng thái nháp/lưu trữ trong module hiện hành; trạng thái **lịch đã xác nhận** độc lập, chưa mở tuyển sinh. Chưa có API sửa/xóa/hủy buổi hoặc giải phóng đặt phòng. Cần xem trước kỹ; luồng đổi/hủy/dạy thay sẽ làm ở lát cắt kế tiếp.
- Ghi audit nghiệp vụ, chưa có màn hình xem log. Nhu cầu xem log đã ghi vào `test-feedback.md` theo yêu cầu người dùng, để sau.

## Kiểm chứng và bàn giao

Test bao phủ SQLite/PostgreSQL, migration roundtrip/model, API phân quyền/tenant/version/FK, xung đột/giờ liền kề/DST/nháp thiếu dữ liệu, toàn bộ hoặc không có buổi, xác nhận lặp, hai yêu cầu cạnh tranh và thu hồi quyền; UI/Chromium và hồi quy module cũ. Kết quả cuối và tình trạng Docker/Jira tại mục 27 `myplan.txt`.

## API và lưu trữ

Prefix `/api/v1`. Nhân sự là quản lý/giáo vụ và Root có phiên hỗ trợ còn hiệu lực. Trường ngoài schema bị từ chối; ID đều được scope tenant.

| Endpoint | Hợp đồng |
| --- | --- |
| GET `/classes/{id}/planning` | Nhân sự: lớp, lựa chọn giáo viên/phòng, phân công, mẫu nháp và buổi đã xác nhận |
| PUT `/classes/{id}/teachers` | `{version, teacher_ids, override_reason?}`; thay cả tập, tối đa 20; cho phép bỏ hết khi nháp |
| PUT `/classes/{id}/schedule` | `{version, starts_on, ends_on, slots}`; thay cả mẫu; mỗi slot `{weekday, starts_at, ends_at, room_id?, teacher_ids}` |
| GET `/classes/{id}/schedule/preview?version=N` | Sinh xem trước, issues/conflicts/room_checks, can_confirm và preview_digest; version tùy chọn ở API, UI luôn gửi |
| POST `/classes/{id}/schedule/confirm` | `{version, preview_digest, confirmation_key}`; UUID từ client, tạo tất cả hoặc không có buổi; trả context sau lưu |
| GET `/teaching-sessions?limit=20&offset=0` | Chỉ giáo viên, chỉ buổi được phân công cho bản thân; limit tối đa 100 |

Migration `20260926_0011` thêm bốn bảng `class_teachers`, `schedule_plans`, `class_sessions`, `session_teachers` và unique index lớp phục vụ FK tổng hợp. Không seed/backfill; không downgrade trên dữ liệu thật vì sẽ xóa các bảng này. Lớp cũ không tự có lịch hoặc giáo viên.

Version lớp được dùng chung giữa sửa lớp/phân công/mẫu/xác nhận. Digest bao gồm dữ liệu lựa chọn giáo viên/phòng; thay đổi liên quan sau xem trước buộc tải lại. Có thể cần xem lại cả khi một lựa chọn chưa dùng thay đổi (kiểm tra bảo thủ). PostgreSQL xác nhận dưới khóa tenant → actor/support → tài khoản giáo viên; đổi membership cũng khóa tenant trước. Khóa tài khoản toàn hệ thống lấy actor trước tài khoản đích. Không có cam kết chống đặt trùng cho SQL ghi trực tiếp ngoài API; SQLite không có khóa hàng tương đương, dùng PostgreSQL khi nhiều nhân sự cùng thao tác.

Audit: `class.teachers`, `schedule.draft`, `schedule.confirm`. Đây là nhật ký thao tác, không phải màn hình tra cứu log. Không tự retry mutation sau lỗi mạng; làm mới để kiểm tra đã lưu hay chưa. Form phân công và mẫu lịch lưu độc lập, phải lưu phần đang sửa trước khi đổi sang phần còn lại để tránh mất dữ liệu chưa lưu.

## Checklist nghiệm thu trên Chrome

Chuẩn bị dữ liệu thử: khóa công bố có cấp đầu ra, chi nhánh/phòng đủ sức chứa, hai lớp cùng khoảng ngày, tài khoản giáo viên active và hồ sơ có năng lực đúng ngôn ngữ/cấp đầu ra. Root mở hỗ trợ trung tâm trước; kiểm tra lịch cá nhân bằng tài khoản giáo viên riêng. Dùng buổi thử có ngày tương lai; bản này chưa có nút hủy lịch đã xác nhận.

| Thao tác | Kết quả mong đợi |
| --- | --- |
| Lớp học → Giáo viên & lịch học → chọn giáo viên → Lưu phân công | Lưu thành công; giáo viên xuất hiện ở lựa chọn cho từng khung giờ |
| Chọn người thiếu năng lực phù hợp | Cảnh báo và yêu cầu lý do tối thiểu 3 ký tự; người không hoạt động không được phân công mới |
| Chọn khoảng ngày/thứ/giờ/phòng/giáo viên → Lưu lịch nháp → Xem trước | Đúng số buổi và múi giờ chi nhánh; mục buổi đã xác nhận vẫn trống, chưa giữ phòng |
| Nháp thiếu phòng hoặc thiếu giáo viên, hoặc hai khung tự chồng giờ | Lưu nháp được, xem trước nêu lỗi và không cho xác nhận |
| Lịch hợp lệ → Xác nhận lịch → đọc cảnh báo → Xác nhận | Tạo đủ buổi một lần; tải lại vẫn có buổi, form chỉ đọc, không mở tuyển sinh |
| Lớp thứ hai cùng phòng hoặc cùng giáo viên, cùng ngày/giờ | Xem trước chỉ rõ loại xung đột và lớp liên quan; nút xác nhận bị chặn; phòng bận bị đánh dấu không khả dụng |
| Đổi lớp thứ hai bắt đầu đúng giờ lớp trước kết thúc → lưu → xem trước | Không còn xung đột nếu không có ràng buộc khác; có thể xác nhận |
| Hai tab cùng sửa/xác nhận, hoặc dữ liệu/quyền thay đổi sau xem trước | Không ghi đè phiên bản mới, không giữ lịch trùng; yêu cầu làm mới hoặc từ chối quyền; không lỗi 500 |
| Giáo viên đăng nhập → Lịch dạy của tôi | Chỉ thấy buổi mình được phân công, không có nút sửa hoặc lý do nội bộ; giáo viên khác không thấy buổi không thuộc mình |
| Đổi tên lớp đã xác nhận; thử đổi ngày/sĩ số/phòng/mã hoặc lưu trữ khi còn buổi tương lai | Tên đổi được; các thay đổi ảnh hưởng lịch bị từ chối rõ ràng |

Xem cả sáng/tối, Việt/Anh và chiều rộng mobile. BUG-004 popup native select trên Chrome tiếp tục hoãn theo yêu cầu; kiểm thử Chromium/ảnh ô select đóng không đồng nghĩa popup native đã được nghiệm thu. Tối ưu tải lựa chọn/số truy vấn và calendar tuần/tháng thuộc bước sau, không phải cam kết hiệu năng quy mô lớn của bản này.
