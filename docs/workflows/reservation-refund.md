# Bảo lưu, tiếp tục cùng lớp và hoàn phí

Phiên bản0014, triển khai theo [kế hoạch đã duyệt](../plans/reservation-refund.md). Trạng thái deploy/test/nghiệm thu mới nhất ở [current-state](../current-state.md); checklist nghiệm thu theo vai trò nằm ở mục7 kế hoạch.

## Quyền và giới hạn

Giáo vụ/quản lý/Root có phiên hỗ trợ đúng tenant được bảo lưu, hủy, tiếp tục, lập và duyệt đề xuất, ghi nhận chi trực tiếp. Chỉ quản lý/Root hỗ trợ sửa chính sách khấu trừ. Học viên chỉ đọc quyền học, tiền và thông báo của mình; không có lý do/actor nội bộ. Giáo viên chỉ có roster/điểm danh các buổi được giao, không có API hoàn phí.

Tiếp tục cùng lớp chỉ được **trước quyết toán hoàn dương**, kể cả trường hợp toàn bộ tiền hoàn dùng bù nợ. NO_REFUND (duyệt0) không chặn tiếp tục. Đề xuất chưa duyệt tự hủy cùng transaction khi tiếp tục. Hủy đăng ký chặn tiếp tục. Không chuyển lớp, không giữ chỗ, không bù buổi/gia hạn khóa, không ví, không gọi ngân hàng, không sửa/xóa khoản hoàn đã duyệt.

## Quyền học theo buổi

- Giáo vụ chọn buổi scheduled thuộc chính lớp, chưa bắt đầu, nhập lý do và xem preview trước khi xác nhận. Buổi mốc thuộc phần chưa học.
- Quyền học lưu thành các khoảng UTC [starts_at, ends_at). Bảo lưu/hủy đóng khoảng đang mở; tiếp tục tạo khoảng mới cùng enrollment, không sinh hóa đơn mới. Mốc không được lùi/chồng khoảng trước.
- Trạng thái suspended/cancelled thể hiện thao tác đã ghi nhận; quyền học chỉ dừng từ giờ mốc. UI hiển thị các khoảng để phân biệt mốc tương lai.
- Tiếp tục kiểm tra hồ sơ/tài khoản học viên, lớp/tài nguyên/giáo viên còn hoạt động, sức chứa từng buổi và trùng lịch. Ngoại lệ cho chính lớp đã bắt đầu, không thay điều kiện tuyển sinh mới.
- Lịch cá nhân/roster/chuyên cần/sức chứa/trùng lịch/người nhận thông báo dựa trên quyền học tại giờ bắt đầu từng buổi. Lịch sử điểm danh trước mốc giữ nguyên. Không cho dừng qua sheet đã tồn tại tại/sau mốc.
- Buổi đã dùng làm mốc không được đổi giờ/hủy/khôi phục đổi trạng thái trong đợt này; thay phòng/giáo viên vẫn phải qua guard hiện hành.
- Hủy waiting không cần mốc vì chưa có lớp. Không xóa hóa đơn, nghĩa vụ hoặc tự tạo enrollment. Không cho đăng ký mới cùng khóa để lách nghĩa vụ.
- Hồ sơ còn nợ, bảo lưu hoặc hoàn chờ chi không được archive.

## Quyết toán tiền nguyên VND

T = học phí ròng; P = tổng khoản thu chưa đảo; N = tổng buổi scheduled tại lúc xác nhận dừng; n = số buổi trong tập đó từ mốc. Buổi vắng/muộn/có phép đã diễn ra vẫn sử dụng quyền học; buổi cancelled không tính. Snapshot lưu nguồn và phiên bản để truy vết.

```text
U = floor(T × n / N)                 # waiting: U = T
E = min(P, U)
phí = cố định hoặc floor(E × tỷ lệ / 100)
G đề xuất = max(0, E − phí)
D = T − P − bù nợ đã ghi
O = min(G được duyệt, D)
X = G được duyệt − O
```

N không hợp lệ thì chặn, không chia0. Giáo vụ được đổi G trong khoảng0..P, bắt buộc lý do nếu khác đề xuất. Từ chối/hủy đề xuất cũng cần lý do. Chính sách mặc định khấu trừ0, cố định hoặc phần trăm nguyên0..100, có version và snapshot.

Ví dụ T1.000.000, P700.000, n/N=1/2, phí0: G500.000, D300.000 → bù300.000 và chi200.000. P0 thì G0, nợ vẫn còn. Chưa thanh toán không đồng nghĩa được miễn khoản học chưa sử dụng.

Duyệt ghi bù nợ và khoản chờ chi cùng transaction. X0/G>0 hoàn tất ngay; G0 là no_refund; X>0 chờ giáo vụ ghi nhận toàn bộ chi một lần bằng cash/transfer và tham chiếu. Chỉ xác nhận chi sau khi tiền đã trả bên ngoài.

Không sửa Invoice.total/snapshot/kỳ gốc hoặc dùng Payment âm. Công nợ = tổng − thực thu − bù nợ; chi hoàn không cộng lại nợ. Thu phân bổ vào kỳ sớm trước, bù nợ tiếp phần thiếu sớm nhất. DTO tách paid/offset/remaining; số nợ trong phép tính hoàn là snapshot tại lúc lập đề xuất, khác số dư hiện tại.

Mỗi request tối đa một quyết toán dương (unique settled_request_id). Đã quyết toán dương thì chặn đảo khoản thu của hóa đơn và tiếp tục học. NO_REFUND không khóa vĩnh viễn quyết toán/đảo thu. Sửa sai quyết toán đã duyệt ngoài phạm vi0014.

## Trạng thái, API và tính nguyên tử

Enrollment.state: active → suspended → active hoặc cancelled; waiting bị hủy lưu AdmissionRequest.cancelled_at, API trả cancelled. Giữ request.status cũ để tránh thay constraint/FK của dữ liệu0013.

RefundCase.status: proposed → rejected/cancelled/no_refund/pending/paid; pending → paid khi ghi chi. paid có thể chỉ bù nợ, phải đọc offset_amount/cash_amount/disbursement để phân biệt.

- GET /api/v1/enrollments và /{request_id}: yêu cầu đã có hóa đơn, kể cả waiting; ID trên route là **AdmissionRequest.id**, enrollment_id trả riêng.
- POST /enrollments/{request_id}/preview và /operations: action suspend/resume/cancel; version, request_key, reason, session_id; xác nhận cần source_digest.
- GET/PUT /refunds/policy; POST /refunds/preview, POST/GET /refunds; GET /refunds/{case_id}.
- POST /refunds/{case_id}/decision: approve/reject/cancel, version, amount, reason, request_key.
- POST /refunds/{case_id}/disburse: version, cash/transfer, reference, request_key.

Preview không ghi nghiệp vụ. Xác nhận tính lại dưới khóa tenant/actor, kiểm quyền và version; thay nguồn thu/đảo thu/lịch/policy làm đề xuất hết hiệu lực trả409. Replay cùng key/payload không tạo trùng. Quyền học/sổ tiền/history/audit/inbox commit cùng transaction; lỗi bất kỳ rollback toàn bộ. Inbox không chứa lý do tài chính.

Sáu bảng mới: enrollment_periods, enrollment_operations, refund_policies, refund_cases, invoice_adjustments, refund_disbursements. Migration20260928_0014 backfill một period mở/enrollment cũ với starts_at=effective_at. Không tạo nghiệp vụ tài chính hoặc đổi ngày/số tiền cũ. Downgrade từ chối nếu phải bỏ dữ liệu, kể cả periods đã backfill; không dùng để rollback DB thật.
