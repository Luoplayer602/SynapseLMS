# Vận hành buổi học và lịch tuần

Phạm vi phiên 2026-09-26, bàn giao 2026-09-27: SCH-04 (SYNAPSELMS-78), SCH-06 (152), phần lịch tuần SCH-05 (79). Đã triển khai và kiểm chứng tự động, chờ người dùng nghiệm thu. Người dùng yêu cầu tăng phạm vi mỗi phiên để giảm đọc lại context, nên gộp lịch tuần có bộ lọc vào cùng nền vận hành buổi. Không coi SCH-05 hoàn tất lịch tháng/kéo-thả.

## Cách dùng và quyền

- Nhân sự (quản lý/giáo vụ) hoặc Root mở hỗ trợ → **Lịch tuần**, chọn ngày bắt đầu 7 ngày, chi nhánh/phòng/giáo viên/trạng thái → Xem lịch. Mặc định tuần hiện tại và ẩn buổi hủy. Mỗi trang tối đa 20 buổi, nhóm theo ngày của múi giờ chi nhánh, không theo timezone trình duyệt. Có tuần trước/sau và phân trang; không phải lưới calendar kéo-thả.
- Mở **Chi tiết / điều chỉnh buổi** tại lịch tuần hoặc danh sách buổi trong **Lớp học → Giáo viên & lịch học**. Chọn thao tác, nhập lý do, xem trước rồi xác nhận. UI nêu thông tin hiện hành và kết quả dự kiến.
- Chỉ buổi chưa bắt đầu được đổi/hủy/khôi phục. Giờ mới cũng phải tương lai, trong khoảng ngày lớp, cùng ngày, giữ chi nhánh/múi giờ/hình thức/sĩ số. Giờ nhập theo IANA chi nhánh; từ chối DST không tồn tại/nhập nhằng.
- Giáo viên chỉ đọc buổi scheduled mình đang phụ trách qua lịch cá nhân. Người bị thay ra không còn thấy buổi tương lai đó; người thay vào thấy buổi. Không trả lý do, waiver, lịch sử nội bộ; không mở quyền điểm/học viên. Học viên chưa được cấp lịch vì chưa xếp lớp.

## Bảo toàn tài nguyên và lịch sử

- Đổi ngày/giờ/phòng giữ ID buổi. Backend dùng cùng kiểm tra xung đột với xác nhận mẫu ban đầu, bỏ chính buổi đang sửa và bỏ các buổi cancelled. Vẫn chặn phòng, giáo viên (cả khác chi nhánh), lớp; liền giờ được phép. Kiểm tra lại dưới khóa tenant/tài khoản giáo viên trước khi ghi, không bỏ lịch cũ nếu lịch mới thất bại.
- Hủy chỉ đổi trạng thái, giải phóng tài nguyên. Khôi phục kiểm tra hoạt động/quyền/năng lực/sức chứa và xung đột như giữ chỗ mới; không giành lại phòng. Không sinh buổi bù hoặc hoàn phí. Buổi đã hủy vẫn giữ ngày/giờ và tập giáo viên cuối để khôi phục.
- Dạy thay thay toàn bộ tập giáo viên của một buổi (1–20), không đổi class_teachers hoặc các buổi khác. Giáo viên có thể ngoài tập mặc định nhưng phải active cùng tenant. Thiếu đúng ngôn ngữ/cấp đầu ra cần lý do ngoại lệ; lý do thay đổi và lý do ngoại lệ là hai trường riêng. Ngoại lệ giữ theo buổi cho các lần đổi giờ/khôi phục sau.
- Mẫu tuần xác nhận giữ làm nguồn gốc, không được sinh lại. Cấu trúc lớp/mã lớp/timezone chi nhánh tiếp tục khóa dù hủy hết buổi. Guard lưu trữ/giảm sức chứa chỉ tính buổi scheduled tương lai **và** vẫn giữ guard lớp nháp cũ: phòng mặc định của lớp nháp có thể vẫn không lưu trữ được dù lịch đã hủy.
- Lịch sử bất biến lưu snapshot trước/sau, actor ID, UTC, action, lý do và version; sắp xếp version giảm dần, phân trang. Snapshot chứa mã/tên/phòng/giáo viên tại lúc thay đổi. Không có endpoint sửa/xóa lịch sử. Phòng đã dùng rồi đổi đi vẫn không được đổi mã do lịch sử tham chiếu, nhưng có thể giải phóng sử dụng/lưu trữ theo điều kiện khác.
- Không tự chặn khóa tài khoản/thu hồi quyền; lịch không tự hủy khi khóa người dạy. Phải đổi giáo viên hoặc hủy buổi thủ công. Không gửi email/push/in-app notification trong bản này; nhân sự phải liên lạc thủ công sau thay đổi.
- Audit `session.reschedule/substitute/cancel/restore` cùng transaction. Lịch sử một buổi không thay thế màn hình log toàn hệ thống đang hoãn.

## API

Prefix `/api/v1`, chỉ nhân sự và Root hỗ trợ; các ID scope tenant. API cá nhân `/teaching-sessions` vẫn riêng cho teacher và chỉ trả scheduled.

| Endpoint | Chức năng |
| --- | --- |
| GET `/class-sessions/options` | ID/tên chi nhánh, phòng, giáo viên trong tenant cho bộ lọc |
| GET `/class-sessions` | Bắt buộc starts_on/ends_on, tối đa 31 ngày; tùy chọn branch_id/room_id/teacher_id, status=scheduled/cancelled/all, limit (20 mặc định, 100 tối đa), offset |
| GET `/class-sessions/{id}` | Buổi hiện hành, lớp, lựa chọn phòng/giáo viên, lý do ngoại lệ, can_edit/server_now |
| GET `/class-sessions/{id}/history` | Lịch sử nội bộ, limit/offset |
| POST `/class-sessions/{id}/preview` | Xem trước cùng payload thao tác; không ghi hoặc giữ chỗ |
| POST `/class-sessions/{id}/operations` | Kiểm tra lại và áp dụng nguyên tử; trả session và replayed |

Payload chung: `version`, `action`, `reason` (3–500 ký tự), `request_key` UUID. `reschedule` thêm `day`, `starts_at`, `ends_at` (HH:mm), `room_id` (null cho online); `substitute` thêm `teacher_ids`, `override_reason` tùy chọn; cancel/restore không nhận các trường thay giờ/phòng/giáo viên. Trường ngoài schema bị từ chối.

Version riêng từng buổi; thay buổi không đổi version/mẫu của lớp. Request key duy nhất trong tenant, được lưu cùng history. Cùng key+payload trả snapshot kết quả đã xử lý, không thêm history; cùng key khác payload/đích bị 409. Sau replay, GET để đọc trạng thái mới nhất nếu người khác đã sửa tiếp. Xem trước không giữ tài nguyên; xác nhận luôn kiểm tra lại, có thể bị từ chối dù preview trước đó hợp lệ. Lỗi version/trạng thái/quá khứ buộc làm mới; mất mạng/5xx sau mutation không tự gửi lại hoặc cho tiếp tục ghi trước làm mới.

Giới hạn hiệu năng: API giới hạn khoảng ngày và phân trang; bộ lọc options còn tải toàn tenant, bộ lọc ngày chính xác theo timezone thực hiện sau chặn khoảng UTC. Chưa cam kết hiệu năng dữ liệu lớn; chưa lịch rảnh, đệm di chuyển, ngày nghỉ, thao tác hàng loạt, buổi bù ngoài khoảng ngày hoặc calendar tháng.

## Migration và triển khai

`20260926_0012`: thêm status/version/override_reason vào buổi, bảng session_history; bỏ unique lớp+giờ bắt đầu để buổi hủy không chiếm slot; bỏ FK bắt giáo viên buổi thuộc class_teachers nhưng giữ FK teacher/tenant và session/class/tenant.

Migration giữ nguyên ID/thời gian/giáo viên buổi cũ, mặc định scheduled/version 1; kế thừa lý do ngoại lệ cũ từ phân công lớp. Không sinh dữ liệu giả. Để SQLite bật FK vẫn đổi parent an toàn, sao lưu session_teachers vào bảng tạm trong migration, dựng lại schema rồi phục hồi toàn bộ hàng và xóa bảng tạm. PostgreSQL chạy DDL trong transaction. Có test nâng/hạ/nâng trên dữ liệu buổi và đối chiếu model; không downgrade DB thật. Downgrade chủ động từ chối khi đã có lịch sử thao tác để tránh mất dữ liệu.

Không cần tắt PostgreSQL/Mailpit khi code. Khi triển khai, rebuild API/web, áp dụng migration bằng image mới rồi thay API/web. Không xóa volume. Kết quả kiểm chứng/Docker cuối ghi tại `myplan.txt` mục 29 và `docs/current-state.md`.

## Checklist nghiệm thu

Checkpoint 2026-09-27: 402 backend đạt, 55 ca concurrency skip trên SQLite và được kiểm tra trên PostgreSQL; 66 UI/14 E2E Chromium đạt, lint/build đạt. Docker đồng bộ code, DB xác minh ở 0012 và không lệch model. 83 buổi/83 liên kết giáo viên hiện có giữ nguyên số lượng và checksum trước/sau triển khai. Không cần người dùng rebuild lại; làm mới trình duyệt, Root mở phiên hỗ trợ đúng trung tâm trước khi kiểm thử.

1. Lịch tuần → chọn tuần có buổi: lọc phòng/giáo viên đúng, chuyển tuần và trạng thái hủy đúng; xem cả mobile, sáng/tối, Việt/Anh.
2. Đổi buổi sang giờ/phòng trống → xem trước → xác nhận: ID không đổi, chỉ buổi đó đổi; lịch sử ghi trước/sau và lý do, mẫu tuần giữ nguyên.
3. Đổi sang giờ trùng lớp/phòng/giáo viên: bị chặn, lịch cũ nguyên vẹn. Đổi sang giờ liền kề: hợp lệ nếu không có ràng buộc khác.
4. Hủy buổi: biến mất khỏi bộ lọc scheduled và lịch cá nhân, xuất hiện ở cancelled; lớp khác dùng được tài nguyên vừa rảnh. Hủy không xóa lịch sử.
5. Khôi phục khi tài nguyên đã bị chiếm: bị chặn; khi lại trống và giáo viên/phòng hợp lệ: thành công.
6. Dạy thay bằng người ngoài phân công mặc định: chỉ một buổi đổi; người thiếu năng lực cần lý do ngoại lệ. Giáo viên cũ/mới thấy lịch cá nhân đúng sau làm mới, không thấy lý do nội bộ.
7. Buổi đã bắt đầu/quá khứ chỉ đọc. Hai tab sửa cùng buổi: tab cũ bị 409, không ghi đè. Khóa quyền/support thì không ghi được.
8. Lỗi mạng khi xác nhận: làm mới để kiểm tra trước thao tác tiếp; không tạo buổi hoặc history trùng. Không tự gửi thông báo/hoàn phí.
