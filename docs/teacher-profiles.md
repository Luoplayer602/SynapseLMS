# TCH-01/TCH-02 — Hồ sơ, năng lực và chứng chỉ giáo viên

Triển khai ngày 2026-09-26, chờ người dùng nghiệm thu. Kế hoạch gốc: [teacher-profile-next-step.md](./teacher-profile-next-step.md). BUG-004 select dark mode Chrome vẫn hoãn.

## Luồng sử dụng và quyền

Nhân sự mở sidebar **Giáo viên**; Root mở hỗ trợ trung tâm trước. Chọn **Tạo hồ sơ giáo viên**, tìm/chọn tài khoản giáo viên đang hoạt động trong tenant, nhập thông tin và lưu. Nếu chưa có tài khoản, dùng luồng thành viên/lời mời hiện có; module hồ sơ không tạo tài khoản hoặc thay vai trò.

| Chức năng | Quản lý / giáo vụ | Root | Giáo viên | Học viên |
|---|---|---|---|---|
| Danh sách/tạo hồ sơ | Trong tenant | Phiên hỗ trợ | Không | Không |
| Xem hồ sơ/năng lực/chứng chỉ/lịch sử | Trong tenant | Phiên hỗ trợ | Bản thân qua `/me` | Không |
| Sửa họ tên/ghi chú nội bộ | Có | Phiên hỗ trợ | Không | Không |
| Sửa điện thoại/giới thiệu | Có | Phiên hỗ trợ | Bản thân | Không |
| Ghi nhận/sửa/thu hồi/khôi phục năng lực và chứng chỉ | Có, có lý do | Phiên hỗ trợ, có lý do | Không | Không |
| Lưu trữ/khôi phục hồ sơ | Có, có lý do | Phiên hỗ trợ | Không | Không |

- Hồ sơ gồm họ tên, điện thoại, giới thiệu/chuyên môn, ghi chú nội bộ; email lấy từ tài khoản, chỉ đọc. Chưa có mã giáo viên nghiệp vụ, dùng ID nội bộ.
- Mỗi user/tenant tối đa một hồ sơ, cả khi lưu trữ. Tạo mới chỉ nhận tài khoản active, không phải Root, có membership teacher active/chưa kết thúc trong tenant. Không đổi user/tenant của hồ sơ sau tạo.
- Giáo viên chưa có hồ sơ thấy hướng dẫn liên hệ giáo vụ; GET không tự tạo hồ sơ. Giáo viên không được tự tạo hồ sơ.
- Hồ sơ lưu trữ chặn ghi thông tin, năng lực và chứng chỉ với mọi vai trò, trừ khôi phục hồ sơ. Không khóa tài khoản. Nhân sự vẫn xem lịch sử sau khi membership bị đình chỉ/kết thúc; giáo viên mất quyền nếu membership/tenant/phiên không còn hợp lệ.
- API giáo viên không trả `internal_notes`, lý do nội bộ hoặc phần `internal` của lịch sử. Không chỉ ẩn bằng CSS. Năng lực không cấp quyền xem học viên/nhập điểm; quyền đó đợi phân công lớp.

## Năng lực và chứng chỉ

- Một mục năng lực cho mỗi hồ sơ/ngôn ngữ, chứa tập cấp độ tường minh; các cấp có thể thuộc nhiều bộ trong cùng ngôn ngữ. UI ghi nhãn bộ bên cạnh từng cấp. Không suy ra cấp thấp hơn, không quy đổi giữa hai bộ.
- Có thể tạo mục ngôn ngữ chưa có cấp độ; đây chưa phải căn cứ đủ điều kiện phân công. Ngôn ngữ của mục không đổi; chọn nhầm thì thu hồi và thêm mục đúng, giữ lịch sử. Mục đã thu hồi cần khôi phục trước khi sửa; không tạo lại mục trùng.
- Chứng chỉ: tên bắt buộc, đơn vị cấp, ngày cấp/hết hạn tùy chọn và ghi chú nội bộ. Hết hạn không trước ngày cấp. Mốc hết hạn tính theo ngày UTC: chỉ hết hạn khi ngày hiện tại lớn hơn ngày hết hạn. Hết hạn không tự thu hồi bản ghi hoặc năng lực. Chưa upload hoặc xác minh với đơn vị cấp.
- Tạo/sửa/thu hồi/khôi phục năng lực hoặc chứng chỉ bắt buộc lý do 3–500 ký tự. Một mục tối đa 100 cấp độ mỗi lần lưu. Mục tiêu là ghi nhận thủ công của trung tâm, không tự chứng thực giấy tờ.
- Chứng chỉ cùng tên không bị coi tự động là trùng (có thể tái cấp). Kiểm tra danh sách trước khi tạo lại sau lỗi mạng. Không có idempotency key ở lát cắt này và không tự retry mutation.

## Dữ liệu, lịch sử và catalog

Migration `20260926_0009`, sau 0008, thêm sáu bảng: `teacher_profiles`, `teaching_capabilities`, `teaching_capability_levels`, `teacher_credentials`, `teacher_history`, `teacher_history_levels`. Không backfill/seed. FK tổng hợp bảo vệ profile/tenant và cấp độ/ngôn ngữ/bộ; history giữ FK tới đúng hồ sơ, mục năng lực/chứng chỉ và các cấp đã từng dùng. Unique chống hồ sơ/ngôn ngữ/cấp trùng. Không cascade hoặc API xóa cứng.

Mỗi mục năng lực/chứng chỉ có version riêng; hồ sơ dùng version riêng. Lưu một mục không tự lưu form khác. Version cũ nhận 409; UI giữ bản nháp và yêu cầu làm mới/đối chiếu. Request vẫn kiểm tra trạng thái hồ sơ lưu trữ ở server.

Mỗi lần ghi năng lực/chứng chỉ lưu snapshot sau thay đổi cùng transaction: nội dung công khai, mã/nhãn gốc, actor/vai trò, thời gian UTC; phần internal giữ lý do và ghi chú. UI hiện thời gian theo máy người dùng. Lịch sử sắp mới nhất trước, phân trang. Trạng thái hết hạn trong snapshot là tại thời điểm ghi, không được tính lại theo ngày xem. Lịch sử chỉ append qua API; chưa có trigger chống người có quyền DB sửa trực tiếp hoặc chính sách retention tự động.

Audit hồ sơ ghi hành động/tên trường; lưu trữ/khôi phục hồ sơ ghi lý do. Audit năng lực/chứng chỉ chỉ giữ ID/version/hành động, không chép nội dung chứng chỉ/lý do nội bộ sang audit. Lịch sử nghiệp vụ chứa thông tin cá nhân và cần được bảo vệ như hồ sơ.

`require_unused` chặn xóa/đổi mã danh mục được năng lực hiện hành hoặc lịch sử dùng (`CATALOG_TEACHER_IN_USE`). Bỏ cấp khỏi mục hiện hành/thu hồi không giải phóng tham chiếu cũ. Nhãn được sửa theo quyền catalog, snapshot cũ giữ nguyên. Framework chỉ được tham chiếu khi chọn cấp thuộc bộ đó; ghi nhận ngôn ngữ đơn thuần không tự khóa mọi bộ/cấp dưới nó.

Giữ khóa organization → actor → support và kiểm tra lại quyền sau khóa; tạo hồ sơ khóa thêm tài khoản đích trước kiểm tra membership. Không mở rộng quyền của endpoint học viên hoặc catalog quản trị cho giáo viên.

## API

Prefix `/api/v1/teachers`. `{profile}` là `me` cho giáo viên đọc, UUID hồ sơ cho nhân sự; endpoint ghi năng lực/chứng chỉ chỉ nhận UUID hồ sơ và kiểm tra quyền nhân sự. `kind` là `capabilities` hoặc `credentials`.

| Method / đường dẫn | Nội dung |
|---|---|
| GET `/` | `q` tìm tên/email, `status=active/archived/all`, limit 20 tối đa 100, offset |
| GET `/candidates` | Tài khoản teacher active chưa có hồ sơ, tìm tên/email/phân trang |
| POST `/` | `{user_id, full_name, phone?, introduction?, internal_notes?}` |
| GET `/{profile}` | Chi tiết, whitelist theo vai trò |
| PATCH `/me` | `{version, phone?, introduction?}`; chỉ giáo viên |
| PATCH `/{profile_id}` | `{version, full_name, phone?, introduction?, internal_notes?}`; nhân sự |
| POST `/{profile_id}/archive` | `{version, archived, reason}` |
| GET `/options/{kind}` | kind ở đây là `languages/frameworks/levels`; metadata tối thiểu trong tenant, limit 100 tối đa 100/offset |
| GET `/{profile}/{kind}` | Danh sách năng lực/chứng chỉ, gồm thu hồi; limit 20 tối đa 100/offset |
| POST `/{profile_id}/capabilities` | `{language_id, level_ids: [], reason}` |
| PATCH `/{profile_id}/capabilities/{id}` | `{version, level_ids: [], reason}` thay toàn bộ tập cấp, không đổi ngôn ngữ |
| POST `/{profile_id}/credentials` | `{name, issuer?, issued_on?, expires_on?, internal_notes?, reason}` |
| PATCH `/{profile_id}/credentials/{id}` | Các trường chứng chỉ như trên + version, thay toàn bộ phần form |
| POST `/{profile_id}/{kind}/{id}/state` | `{version, revoked, reason}` |
| GET `/{profile}/history` | Lịch sử hai loại bản ghi, phân trang 20/tối đa 100; `id` là ID sự kiện, `kind`/`action` phân loại |

Các form PATCH là full-form: trường tùy chọn bị bỏ qua về rỗng/null, không phải merge patch. Trường ngoài schema bị từ chối. Không có endpoint sửa/xóa lịch sử, tải file hoặc tự xét điều kiện xếp lớp.

Lỗi chính: 403 quyền/tenant/support, 404 `TEACHER_NOT_FOUND`, `TEACHER_ACCOUNT_UNAVAILABLE`, `TEACHER_RECORD_NOT_FOUND`; 409 `TEACHER_CONFLICT`, `TEACHER_ARCHIVED`, `TEACHER_RECORD_REVOKED`; 422 `TEACHER_LEVEL_MISMATCH` hoặc lỗi validation trường/ngày/trùng cấp.

## Checklist nghiệm thu trên Chrome

Chuẩn bị một trung tâm có ngôn ngữ/bộ với hai cấp độ; tài khoản giáo viên đang hoạt động và giáo vụ/quản lý. Root phải mở hỗ trợ; test giao diện cá nhân cần tài khoản giáo viên riêng. Dùng thông tin tổng hợp, không cần chứng chỉ thật.

| Thao tác | Kết quả mong đợi / dấu hiệu lỗi |
|---|---|
| Giáo viên mở Hồ sơ giáo viên của tôi khi chưa có hồ sơ | Có hướng dẫn liên hệ giáo vụ; không tự tạo dữ liệu hoặc có nút tạo |
| Nhân sự vào Giáo viên → Tạo hồ sơ, chọn tài khoản và lưu | Chỉ chọn teacher active trong tenant; tạo một hồ sơ, email đúng; không trùng sau tải lại |
| Sửa tên/liên hệ/giới thiệu; tìm tên/email và lọc danh sách | Dữ liệu đã lưu vẫn còn khi tải lại, phân trang/lọc đúng |
| Năng lực giảng dạy → Thêm, chọn ngôn ngữ và chỉ cấp cao hơn | Danh sách chỉ có cấp đã chọn, không tự thêm cấp thấp; bộ cấp hiển thị đúng |
| Thêm mục ngôn ngữ không chọn cấp | Ghi nhận được, cảnh báo chưa có cấp/không đủ căn cứ phân công |
| Thêm chứng chỉ, nhập ngày hết hạn trước ngày cấp rồi thử lưu | Bị từ chối, không có bản ghi dở; sửa ngày hợp lệ mới lưu được |
| Lưu chứng chỉ đã hết hạn | Hiện cảnh báo, không tự thu hồi năng lực hoặc tài khoản |
| Giáo viên xem hồ sơ, năng lực, chứng chỉ và lịch sử | Chỉ thấy bản thân; sửa được liên hệ/giới thiệu, không có nút quản lý năng lực/chứng chỉ; không nhận ghi chú/lý do nội bộ cả trong Network response |
| Nhân sự sửa/thu hồi/khôi phục năng lực hoặc chứng chỉ | Cần lý do; Hủy không ghi; lịch sử giữ nội dung cũ, người/thời điểm đúng; bản thu hồi phải khôi phục trước sửa |
| Bỏ cấp khỏi năng lực rồi quản lý thử xóa/đổi mã cấp đó | Bị chặn do lịch sử; sửa nhãn được nhưng lịch sử giữ nhãn cũ |
| Hai tab cùng version: A lưu rồi B lưu | B báo xung đột và giữ nội dung đang nhập, không ghi đè A; cần làm mới |
| Lưu trữ hồ sơ và làm mới cả hai phiên | Tất cả phần chỉ đọc; tài khoản giáo viên vẫn đăng nhập được; nhân sự khôi phục thì sửa lại được |
| Kết thúc support hoặc đình chỉ membership rồi tải/lưu lại | Bị chặn; không lộ dữ liệu tenant khác, không lỗi 500 |
| Việt/Anh, desktop/mobile, sáng/tối | Nhãn đọc được và không tràn ngang; popup native select dark mode vẫn là BUG-004 đã hoãn |

Không phát sinh lớp/lịch, lương, điểm hoặc quyền xem học viên từ thao tác trên. TCH-03/04/05, AI, học liệu, payroll, import, upload/xác minh chứng chỉ và chuyển giáo viên liên trung tâm để sau.

## Vận hành và kiểm chứng

Test chạy trên DB/schema tạm; migration nâng/hạ/nâng và đối chiếu model/schema nằm trong bộ hồi quy. Downgrade 0009 sẽ xóa sáu bảng mới và dữ liệu tương ứng: không thực hiện trên DB thật đã nhập thông tin. Kết quả cuối, Docker và Jira ghi tại `myplan.txt` mục 24. Chỉ rebuild/upgrade sau khi test đạt, không tắt DB hay xóa volume. Chưa commit; chờ người dùng nghiệm thu.
