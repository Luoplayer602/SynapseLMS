# STU-03 — Trình độ và mục tiêu học

Ngày triển khai 2026-09-25. Người dùng xác nhận nghiệm thu ổn ngày 2026-09-26. BUG-004 (select dark mode trên Chrome) vẫn hoãn, không nằm trong bản sửa này.

## Phạm vi và quy tắc

- Trong chi tiết hồ sơ chọn **Trình độ và mục tiêu**. Học viên vào **Hồ sơ học viên của tôi**; nhân sự vào **Học viên → Xem hồ sơ**. Root phải mở phiên hỗ trợ trung tâm trước. Không thêm sidebar mới.
- Mỗi hồ sơ tenant có tối đa một mục cho mỗi bộ cấp độ, được dùng nhiều ngôn ngữ/bộ. Không quy đổi giữa các bộ. Thêm mục chỉ tạo bản ghi rỗng, không tự gán cấp độ hay xác nhận.
- Tự khai, xác nhận trung tâm và mục tiêu dùng các trường riêng. Tự khai lại không thay đổi xác nhận. `self_level_id=null` sau khi lưu nghĩa là chưa biết trình độ; `self_declared_at=null` nghĩa là chưa từng khai.
- Mục tiêu gồm nội dung tối đa 5.000 ký tự, cấp độ đích tùy chọn trong cùng bộ và ngày mong muốn tùy chọn. Có thể chọn đích thấp hơn để ôn tập; không tự tính hạn hay điều kiện đăng ký.
- Xác nhận/điều chỉnh bắt buộc cấp độ, nguồn, căn cứ và lý do. Server ghi người/thời điểm; không nhận các giá trị này từ client. Thu hồi cần lý do và xác nhận đang có hiệu lực; dữ liệu xác nhận cũ còn trong lịch sử.
- Hồ sơ lưu trữ: toàn bộ phần trình độ/mục tiêu chỉ đọc cho mọi vai trò, đến khi hồ sơ được khôi phục. Không có API xóa mục hoặc sửa/xóa lịch sử.
- Từng form lưu riêng, không tự lưu các form khác. Mỗi mục dùng chung `version` cho tự khai/mục tiêu/xác nhận; tab cũ nhận 409, phải làm mới và đối chiếu trước khi lưu lại. Lỗi mạng không tự retry mutation.

## Quyền và dữ liệu riêng tư

| Hành động | Học viên | Quản lý / giáo vụ | Root hỗ trợ | Giáo viên |
|---|---|---|---|---|
| Xem/thêm mục, cập nhật mục tiêu | Bản thân | Trong trung tâm | Trung tâm được hỗ trợ | Chưa mở |
| Tự khai | Bản thân | Không khai thay | Không khai thay | Không |
| Xác nhận/điều chỉnh/thu hồi | Không | Có | Có | Không |
| Lịch sử công khai | Bản thân | Trong trung tâm | Trong phiên hỗ trợ | Chưa mở |
| Nguồn/căn cứ/lý do nội bộ | Không | Có | Có | Không |

API học viên dùng `me`, không nhận profile/user/tenant trong body. Không trả căn cứ/lý do nội bộ cho học viên, kể cả trong lịch sử (không chỉ ẩn trên UI). Hiển thị công khai tên người xác nhận, tên/vai trò người cập nhật và thời gian; không trả email/ID tài khoản của họ. Quyền nhập điểm chỉ giáo viên không thay đổi: xác nhận trình độ là đối chiếu hồ sơ thủ công, không phải ghi bảng điểm. Quyền giáo viên đợi phân công lớp.

## Dữ liệu và bảo vệ danh mục

Migration `20260925_0008` thêm `student_proficiencies`, `proficiency_history` và unique index `(id, organization_id)` trên `student_profiles`; không backfill hay sinh dữ liệu mẫu.

- Unique `(student_profile_id, framework_id)` và version bảo vệ tạo trùng/ghi đè. Khóa ngoại tổng hợp ràng buộc profile/tenant/ngôn ngữ/bộ và ba loại cấp độ.
- Mỗi mutation ghi trạng thái sau cập nhật vào lịch sử cùng transaction; gồm cả sự kiện tạo bản ghi rỗng. Lịch sử giữ snapshot mã/nhãn, tác giả/vai trò và thời gian. Đổi nhãn danh mục không viết lại lịch sử. Thời gian API được chuẩn hóa UTC, UI hiển thị theo máy người dùng.
- Snapshot public và internal tách riêng. Audit kỹ thuật chỉ giữ hành động, target ID và version, không sao chép mục tiêu/căn cứ tự do. Lịch sử nghiệp vụ vẫn chứa dữ liệu cá nhân, cần bảo vệ như hồ sơ; chưa có chính sách lưu giữ/xóa dữ liệu tự động.
- `require_unused` chặn xóa/đổi mã ngôn ngữ, bộ và cấp độ được mục hiện hành, mục tiêu hoặc lịch sử tham chiếu (`CATALOG_PROFICIENCY_IN_USE`). Xóa mục tiêu/thu hồi xác nhận không giải phóng tham chiếu lịch sử. Nhãn vẫn sửa được theo quyền catalog. FK là lớp bảo vệ xóa cuối cùng, không thay cho kiểm tra đổi mã.
- Giữ thứ tự khóa organization → actor → support, cùng kiểm tra lại quyền/phiên/tenant sau khóa. Đọc đồng thời của Root không bỏ audit để né deadlock.

Lịch sử chỉ append qua ứng dụng, chưa có trigger ngăn quản trị viên DB sửa trực tiếp. Downgrade migration xóa hai bảng mới và dữ liệu của chúng; chỉ kiểm thử downgrade trên DB tạm, không dùng để rollback dữ liệu thật đã nhập.

## API

Prefix `/api/v1`. `{profile}` là `me` cho học viên, UUID hồ sơ cho nhân sự/Root. Mọi route yêu cầu phiên/tenant hợp lệ.

| Method / đường dẫn | Nội dung |
|---|---|
| GET `/student-proficiency-options/{kind}` | `languages`, `frameworks`, `levels`; metadata tối thiểu trong tenant, không cần khóa công bố; limit mặc định 100, tối đa 100, offset |
| GET `/student-proficiencies/{profile}` | Danh sách; limit mặc định 20, tối đa 100, offset |
| POST `/student-proficiencies/{profile}` | `{framework_id}`; 201 và sự kiện tạo, chưa khai/xác nhận |
| GET `/student-proficiencies/{profile}/{id}` | Chi tiết hiện hành |
| PATCH `…/{id}/declaration` | `{version, self_level_id}`; chỉ học viên, null phải gửi tường minh |
| PATCH `…/{id}/goals` | `{version, goal_text, goal_level_id, target_date}`; thay cả phần mục tiêu, trường bỏ qua về rỗng/null |
| POST `…/{id}/verification` | `{version, action: "verify", level_id, source, evidence, reason}` hoặc `{version, action: "revoke", reason}` |
| GET `…/{id}/history` | Mới nhất trước, limit mặc định 20/tối đa 100, offset; response `id` là ID sự kiện lịch sử |

Lỗi chính: 403 `FORBIDDEN`; 404 `STUDENT_NOT_FOUND`/`PROFICIENCY_NOT_FOUND`; 409 `PROFICIENCY_CONFLICT` (trùng mục hoặc version cũ), `STUDENT_ARCHIVED`, `PROFICIENCY_NOT_VERIFIED`; 422 `PROFICIENCY_LEVEL_MISMATCH`, `PROFICIENCY_EVIDENCE_REQUIRED`. Trường giả mạo/ngoài schema bị từ chối. Quyền truy cập metadata mới không cấp quyền API quản trị catalog cho học viên.

## Checklist nghiệm thu trên Chrome

Chuẩn bị: một trung tâm có ngôn ngữ/bộ với ít nhất hai cấp độ; tài khoản học viên có hồ sơ đang hoạt động và tài khoản giáo vụ/quản lý. Root mở hỗ trợ để làm phần nhân sự, nhưng cần tài khoản học viên riêng để kiểm tra tự khai. Dùng dữ liệu test, không nhập chứng chỉ hay thông tin nhạy cảm thật. Không cần có khóa công bố.

| Thao tác | Kết quả mong đợi / dấu hiệu lỗi |
|---|---|
| Học viên mở hồ sơ → Trình độ và mục tiêu → thêm một bộ | Ban đầu chưa khai/chưa xác nhận; thêm trùng bị chặn, không có hai mục cùng bộ |
| Chọn cấp độ tự khai và Lưu tự khai; nhập mục tiêu, đích, ngày rồi Lưu mục tiêu; tải lại | Đúng giá trị và thời gian, hai lần lưu tách biệt; lỗi nếu mất dữ liệu đã lưu hoặc tự có xác nhận |
| Giáo vụ vào hồ sơ đó → Xem trình độ và mục tiêu → Xác nhận/điều chỉnh | Phải điền cấp độ/nguồn/căn cứ/lý do; Hủy không ghi thay đổi; lưu xong có người và thời gian xác nhận |
| Học viên làm mới, đổi tự khai sang cấp khác hoặc Chưa biết trình độ | Xác nhận trung tâm không đổi; không có nút xác nhận/căn cứ/lý do nội bộ. Network response chi tiết/lịch sử không chứa nội dung nội bộ |
| Nhân sự điều chỉnh rồi thu hồi với lý do, mở lịch sử | Hiện hành hết xác nhận sau thu hồi; các lần xác nhận trước còn nguyên, nhãn/người/thời điểm đúng. Học viên chỉ xem lịch sử công khai |
| Đặt mục tiêu sang cấp khác rồi xóa mục tiêu; quản lý thử đổi mã/xóa cấp cũ | Bị chặn vì lịch sử; sửa nhãn được nhưng lịch sử giữ nhãn tại thời điểm cũ |
| Mở cùng mục trên hai tab, tab A lưu rồi tab B lưu bản cũ | Tab B báo xung đột, giữ nội dung đang nhập, không ghi đè A; làm mới rồi đối chiếu |
| Lưu trữ hồ sơ và làm mới màn hình trình độ | Xem được lịch sử, không thêm/tự khai/sửa mục tiêu/xác nhận; khôi phục thì thao tác lại được |
| Kết thúc hỗ trợ Root rồi tải/lưu lại; thử tài khoản giáo viên hoặc tenant khác | Bị từ chối, không đọc/ghi dữ liệu ngoài quyền; không xuất hiện lỗi 500 |
| Đổi Việt/Anh, desktop/mobile, sáng/tối | Nhãn/form/lịch sử đổi ngôn ngữ, không tràn ngang; BUG-004 popup select dark mode vẫn là lỗi đã biết, không đánh dấu đã sửa |

Không phát sinh đăng ký, hóa đơn hoặc xếp lớp sau cập nhật trình độ. AI, bài thi/điểm, upload chứng chỉ, quy đổi bộ cấp độ, chuyển trung tâm và thư viện học liệu tiếp tục ngoài phạm vi.

## Kiểm chứng kỹ thuật

Kết quả chạy và triển khai cuối được ghi tại mục STU-03 trong `myplan.txt`. Test tự động dùng SQLite/schema PostgreSQL tạm; không tạo/xóa hồ sơ thật. Có test quyền/tenant/FK, stale version, lịch sử/phân trang/riêng tư, catalog tham chiếu hiện tại và lịch sử, tạo/sửa đối đầu xóa/đổi mã và Root đọc đồng thời với thu hồi hỗ trợ. E2E dùng Chromium của Playwright; người dùng nghiệm thu trên Chrome đang sử dụng.
