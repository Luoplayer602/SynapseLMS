# Kế hoạch: bảo lưu, tiếp tục cùng lớp và quyết toán hoàn phí

Trạng thái: **đã code, test và deploy0014 ngày2026-09-28; chờ người dùng nghiệm thu**. Trước code đã kiểm tra37 file không khác baseline, HEAD3c3a1431c4c4ffbac319aa3ef59a34162de0dea7; không stage/commit. Kết quả cuối ở mục9.
Đề cử model: GPT gpt-6-astra — high. Lý do: đợt này liên quan tiền, quyền theo thời điểm, migration giữ dữ liệu và giao dịch đồng thời.

## 1. Mục tiêu, phạm vi và điểm kết thúc

Hoàn tất luồng giáo vụ chọn học viên đã xếp lớp → bảo lưu/hủy từ một buổi → cập nhật quyền học/roster/lịch → tiếp tục cùng lớp khi hợp lệ hoặc quyết toán phần hoàn → bù công nợ → ghi nhận chi tiền → học viên thấy trạng thái và thông báo.

Phạm vi chính: ENR-06/SYNAPSELMS-84 và FEE-06/SYNAPSELMS-91; trạng thái Jira được cập nhật khi bàn giao ở mục9. Bao gồm hủy yêu cầu đã duyệt còn waiting để không bỏ sót hóa đơn chưa có enrollment. Bảo lưu chỉ cho enrollment đã xếp; hủy submitted tiếp tục dùng từ chối hiện có.

Điểm kết thúc: luồng trên hoạt động xuyên backend/UI Việt–Anh, có lịch sử bất biến và kiểm thử tiền/quyền/tenant/concurrency/migration, triển khai có đối chiếu dữ liệu, bàn giao checklist để người dùng nghiệm thu. Việc duyệt kế hoạch không đồng nghĩa đã nghiệm thu sản phẩm.

Chưa làm: chuyển lớp (ENR-05/SYNAPSELMS-83), học lại khóa bằng đăng ký mới, hoàn thành enrollment/chứng nhận, quyền học bù hoặc gia hạn khóa do thời gian bảo lưu, tự động hoàn ngân hàng, ví/số dư, PDF server, báo cáo chuyên cần cả lớp, doanh thu, AI, học liệu, calendar tháng, email/SMS. Giữ ngày kết thúc lớp; không cam kết bảo lưu giữ chỗ hoặc bù các buổi đã bỏ lỡ.

### Trạng thái đợt trước, tách khỏi đề xuất mới

- Người dùng đã xác nhận trong phiên: **“Đã nghiệm thu đạt toàn bộ phạm vi đã bàn giao”** cho tuyển sinh → học phí → điểm danh → thông báo (0013).
- Đã code/test/deploy theo hồ sơ bàn giao; kiểm tra hiện tại: Docker API/web đang chạy, DB/Mailpit healthy, Alembic 20260927_0013 (head). Hash 75 file API và 34 file web trong container khớp workspace.
- DB hiện có 2 admission_requests, 1 enrollment, 2 invoices, 4 payments, 0 attendance_sheets. Không dùng lại baseline rỗng để triển khai đợt mới, không coi thay đổi này là lỗi hoặc tự sửa.
- Jira đọc lại: 19 story 0013 vẫn In Progress; chưa đồng bộ trạng thái nghiệm thu lên Jira vì phiên này chỉ lập kế hoạch. SYNAPSELMS-78/79/152 thực tế đã Done; lịch tháng chưa có trong code dù story79 Done.
- Việc hành chính còn lại của đợt trước: đồng bộ Jira theo phạm vi đã nghiệm thu ở phiên được phép cập nhật Jira. Không tự đóng toàn bộ FEE-07/92 và ATT-05/99 (PDF chỉ qua trình duyệt; chuyên cần chỉ cá nhân). Đây không phải nhiệm vụ code của đợt mới.
- Báo cáo lịch sử: admissions-full.xml (449 đạt/58 skip, sửa lúc 17:08:39 +07:00), admissions-final.xml (48 đạt/3 skip, 17:15:16), frontend/admissions-ui-results.json (72 đạt, 17:10:04), ngày 2026-09-27. Full 15 E2E và E2E admissions cuối đạt theo bàn giao. Vòng cuối có trùng full. Phiên lập kế hoạch không chạy test; không dùng các kết quả này để chứng nhận code mới.
- HEAD khi khảo sát: db89f5bd937e21833d225f1a8ec09f08bfb36e8e; working tree có nhiều thay đổi và file chưa theo dõi của 0013, gồm compose.yaml mở cổng5432. HEAD không đủ làm baseline; danh sách SHA256 ở cuối file giúp kiểm tra lại trước code.

## 2. Quy tắc nghiệp vụ, quyền, dữ liệu và API

### 2.1 Bảo lưu/hủy và tiếp tục học

- Giáo vụ, quản lý hoặc Root có phiên hỗ trợ đúng trung tâm được thao tác; bắt buộc lý do, version và request_key. Học viên chỉ xem của mình; giáo viên chỉ xem roster/buổi được giao, không xem tiền hoặc lý do nội bộ.
- Chọn buổi scheduled thuộc đúng enrollment và chưa bắt đầu; mốc là thời điểm bắt đầu buổi, lưu cả session_id và thời điểm UTC. Buổi mốc thuộc phần chưa học. Không hồi tố buổi đã bắt đầu hoặc sửa điểm danh lịch sử.
- Khoảng quyền học có dạng [bắt đầu, kết thúc), kết thúc không bao gồm buổi mốc. Bảo lưu đóng khoảng hiện tại từ mốc đó; hủy kết thúc quyền tiếp tục học. Khi mốc ở tương lai, UI phân biệt đã lên lịch dừng với đã dừng thực tế.
- Bảo lưu không tự sửa tiền/kỳ hạn. Tạo đề xuất hoàn là bước xem xét riêng; có thể giữ bảo lưu và không hoàn.
- Tiếp tục cùng lớp: chọn buổi tương lai, còn buổi scheduled, tài nguyên/giáo viên hoạt động, đủ sức chứa tại tất cả buổi sẽ tham gia, không trùng lịch với quyền học khác. Cho phép ngoại lệ lớp đã bắt đầu chỉ với enrollment bảo lưu của chính lớp đó; đăng ký mới vẫn giữ điều kiện tuyển sinh hiện hành.
- Tiếp tục tạo khoảng quyền học mới, không tạo hóa đơn/enrollment mới, không lấp lại khoảng nghỉ và không tự thêm buổi bù. Có thể nhiều lần bảo lưu/tiếp tục nhưng các khoảng không chồng nhau. Hủy chặn tiếp tục.
- Đã chốt ở mục8: không tiếp tục sau khi đã duyệt hoàn, kể cả hoàn chỉ bằng bù nợ; đề xuất chưa duyệt được hủy nguyên tử khi tiếp tục.
- Sức chứa, roster, lịch cá nhân, chuyên cần, kiểm tra trùng lịch, người nhận thông báo lịch đều dùng cùng quy tắc quyền học tại giờ bắt đầu buổi; không chỉ lọc một trạng thái hiện tại.
- Buổi trước mốc vẫn giữ trong lịch sử/chuyên cần. Bản điểm danh đã chốt không bị thay đổi; nháp không được giữ học viên ngoài roster hợp lệ.
- Với đổi/khôi phục lịch: kiểm tra quyền học theo giờ mới và sức chứa từng buổi dưới khóa tenant. Buổi làm mốc bảo lưu/tiếp tục đã xác nhận không được đổi giờ/hủy làm thay đổi ý nghĩa mốc trong đợt này; thay phòng/giáo viên vẫn áp dụng guard cũ. Thông báo chỉ tới người bị ảnh hưởng, không lộ lý do tài chính.
- Hủy waiting: không cần buổi mốc vì chưa có lớp; lưu lý do và quyết toán theo hóa đơn, phần chưa học bằng toàn bộ học phí ròng. Không tự xóa hóa đơn hoặc nợ.
- Không cho đăng ký mới cùng khóa để lách nghĩa vụ hoặc sau hủy trong đợt này; vòng đời học lại cần kế hoạch riêng. Hồ sơ còn bảo lưu/quyền tiếp tục/nợ hoặc hoàn chờ chi không được archive.

### 2.2 Hoàn phí và đối soát

Giữ quyền đã chốt tại docs/workflows/reservation-refund.md và người dùng vừa xác nhận: **giáo vụ được duyệt và ghi nhận trực tiếp**, không thêm bước quản lý phê duyệt. Chỉ quản lý/Root hỗ trợ cấu hình chính sách khấu trừ.

- Chính sách theo trung tâm, version; khấu trừ tiền nguyên VND cố định hoặc phần trăm, không đồng thời cả hai. Mặc định 0; phần trăm tính trên khoản đủ điều kiện trước khấu trừ, làm tròn xuống đồng. Snapshot chính sách khi xác nhận; sửa chính sách không đổi quyết toán cũ.
- Cách tính lần đầu, theo quyết định đã lưu: T = học phí sau giảm giá; P = tổng thu hợp lệ không bị đảo; N = tổng buổi tính phí; n = số buổi chưa học hợp lệ từ mốc; U = floor(T × n / N). G = max(0, min(P, U) − phí khấu trừ).
- N đề xuất lấy các buổi scheduled của lớp tại lúc xác nhận dừng; n là tập con từ mốc chưa bắt đầu; buổi cancelled không tính, buổi vắng/muộn/có phép đã diễn ra vẫn là đã sử dụng quyền học. Lưu danh sách ID/thời gian/trạng thái dùng tính, N/n và T/P. Nếu không có N hợp lệ thì không chia cho 0: chặn quyết toán, yêu cầu xử lý lịch. Riêng waiting dùng U=T, không chia số buổi.
- Chỉ duyệt một quyết toán hoàn cuối cho mỗi yêu cầu đăng ký trong đợt này. Điều chỉnh G khác đề xuất bắt buộc lý do, 0 ≤ G ≤ thực thu hợp lệ; không được tạo quyền hoàn trùng từ các lần bảo lưu trước. Đề xuất bị hủy/từ chối chưa ghi tiền có thể lập lại. G=0 ghi NO_REFUND, không tạo bù nợ/chi và không tự chặn tiếp tục học của enrollment bảo lưu.
- D = công nợ còn lại của chính hóa đơn, không bù sang khóa/trung tâm khác. O = min(G,D); X = G−O. Khi duyệt, ghi điều chỉnh bù nợ O và khoản phải chi X trong cùng transaction; X=0 thì hoàn tất ngay. X>0 ở trạng thái chờ chi; giáo vụ ghi nhận toàn bộ X một lần, tiền mặt/chuyển khoản, người/thời điểm/tham chiếu.
- Ví dụ T=900.000, P=300.000, U=450.000, phí0: G=300.000; D=600.000 → bù300.000, còn nợ300.000, chi0. Ví dụ P=700.000: G=450.000; D=200.000 → bù200.000, chi250.000. Khi P=0, đề xuất0, nghĩa vụ chưa thu vẫn còn; hủy không tự miễn nợ. Giữ đúng chính sách hiện có, không âm thầm đổi thành xóa toàn bộ học phí chưa học.
- Không đổi total/snapshot/kỳ gốc của Invoice. Khoản thu, bù nợ, khoản chờ chi và chi thực tế hiển thị riêng. Công nợ = T − thu hợp lệ − bù nợ hợp lệ; chi hoàn không cộng lại vào công nợ. Phân bổ thu theo kỳ sớm trước như hiện tại, bù nợ tiếp vào kỳ còn thiếu sớm nhất; tổng remaining và overdue phải khớp sổ điều chỉnh.
- Preview không phải xác nhận: duyệt tính lại dưới khóa, stale financial/source version trả409 và yêu cầu xem lại. Tranh chấp với thu, đảo thu, đổi lịch, cấu hình hoặc quyền không được dùng đề xuất cũ.
- Sau khi có quyết toán được duyệt, chặn đảo thu của hóa đơn trong đợt này để không phá nguồn tiền đã dùng quyết toán; UI giải thích rõ. Đảo khoản thu trước duyệt làm đề xuất cũ hết hiệu lực. Không sửa/xóa quyết toán đã duyệt hoặc chi đã ghi nhận; luồng sửa sai giao dịch hoàn đã ghi nhận ngoài phạm vi, phải nêu trong bàn giao.
- Không gọi ngân hàng. Việc nhập “đã chi” là xác nhận tiền đã được trả bên ngoài, UI cần hiển thị số tiền và đối tượng rõ trước xác nhận.

### 2.3 Dữ liệu/API dự kiến

Tên dưới đây được dự kiến khi lập kế hoạch; hợp đồng thực tế0014 xem [đặc tả đã cập nhật](../workflows/reservation-refund.md).

- Thêm bảng EnrollmentPeriod (khoảng quyền học, FK tenant/enrollment và mốc buổi), EnrollmentOperation (bảo lưu/hủy/tiếp tục, lý do, actor, thời gian, snapshot); thêm version/trạng thái vòng đời phù hợp vào Enrollment. AdmissionRequest giữ lịch sử tuyển sinh, thêm trạng thái cancelled cho hủy waiting; trả vòng đời enrollment riêng để không nhầm với placed.
- Bảng RefundPolicy, RefundCase (snapshot, đề xuất/được duyệt, offset/cash/status/version), InvoiceAdjustment (bù nợ), RefundDisbursement (thực chi). Ràng buộc tenant/FK, số tiền không âm, unique quyết toán trên request và khoản chi trên case; tiền BigInteger. Không dùng Payment âm để mô phỏng hoàn.
- Tái sử dụng BusinessOperation cho idempotency/history, audit và Notification. Các cập nhật quyền học/tài chính/history/inbox commit cùng giao dịch liên quan, lỗi rollback toàn bộ.
- Khóa theo thứ tự đang có: organization → actor/support → tài khoản học viên → enrollment/invoice/case. Không thêm thứ tự ngược với collect/reverse/session operations; tái kiểm tra quyền sau khóa. Concurrency bắt buộc PostgreSQL.
- GET danh sách/chi tiết enrollment và lịch sử; POST preview + bảo lưu/hủy/tiếp tục dưới /api/v1/enrollments (dự kiến).
- GET/PUT chính sách /api/v1/refunds/policy; POST preview/tạo đề xuất, GET list/detail; POST approve/reject/cancel-disposition/disburse dưới /api/v1/refunds (tên thao tác cuối chốt khi code). Cancel chỉ cho đề xuất chưa duyệt; không phải xóa giao dịch tài chính.
- Mở rộng response invoices với adjustment/offset/refund_due/refunded và installments còn phải trả; giữ trường cũ có ý nghĩa nhất quán. Học viên nhận DTO cá nhân được lọc; giáo viên không có API tài chính. Read dùng auth/tenant/no-store/pagination theo mẫu hiện tại.

## 3. Bản đồ thay đổi đã xác minh

Bảng giữ phân loại tại lúc lập kế hoạch; các đường dẫn Tạo đã được triển khai trong đợt0014. Các symbol được nêu ở hàng Sửa/Tái sử dụng đã được tìm trong code, trừ nơi ghi trách nhiệm thay đổi.

| Nhiệm vụ | Đường dẫn chính xác | Tạo/Sửa/Tái sử dụng | Symbol hoặc trách nhiệm thay đổi | Test tương ứng |
| --- | --- | --- | --- | --- |
| Quyền học theo thời điểm | backend/app/models/admissions.py; backend/app/models/__init__.py | Sửa | Enrollment, AdmissionRequest; export model bổ sung | test_admissions.py: migration/period/tenant |
| Mô hình dừng và quyết toán | backend/app/models/enrollment_lifecycle.py | Tạo, dự kiến tạo | Các model mới ở mục2.3 | test_admissions.py: constraints/migration |
| Migration sau0013 | backend/alembic/versions/20260928_0014_reservation_refund.py | Tạo, dự kiến tạo | revision0014 dự kiến; kiểm tra lại head trước tạo | test_admissions.py: dữ liệu cũ/upgrade/downgrade/schema |
| DTO mới | backend/app/api/enrollment_lifecycle_schemas.py | Tạo, dự kiến tạo | Validate mốc, tiền, lý do, version, request_key | test_admissions.py: payload không hợp lệ |
| Nghiệp vụ dừng/tiếp tục/hoàn | backend/app/services/enrollment_lifecycle.py | Tạo, dự kiến tạo | Quy tắc periods, tính/duyệt/chi hoàn, guards | test_admissions.py: state/finance/concurrency |
| API mới | backend/app/api/routes/enrollment_lifecycle.py; backend/app/api/router.py | Tạo file đầu; Sửa router hiện hữu | Endpoint mục2.3, đăng ký router | test_admissions.py: auth/tenant/OpenAPI |
| Tái sử dụng transaction/quyền | backend/app/services/admissions.py; backend/app/api/routes/courses.py; backend/app/api/dependencies.py | Tái sử dụng; Sửa admissions.py | scoped, expected, replay, finish, notify; authorize, lock_actor giữ hợp đồng | test_admissions.py; test_auth_identity.py |
| Sức chứa/trùng lịch và số dư | backend/app/services/admissions.py | Sửa | candidates, session_conflict, place, enrollment_session_guard dùng quyền học theo buổi; paid/debt tích hợp sổ bù nợ, giữ ý nghĩa thu hợp lệ | test_admissions.py; test_session_operations.py; test_schedules.py |
| Tài chính và đăng ký cũ | backend/app/api/routes/admissions.py | Sửa | invoice_view, collect, reverse, openings, class_roster, my_sessions, submit, manual_place; không tạo import vòng | test_admissions.py |
| Điểm danh/chuyên cần | backend/app/api/routes/attendance.py | Sửa | roster, save, mine, history theo quyền tại buổi | test_admissions.py |
| Đổi lịch và người nhận | backend/app/api/routes/session_operations.py | Sửa | candidate, apply_operation; chặn mốc, chọn học viên nhận thông báo | test_session_operations.py; test_admissions.py |
| Archive hồ sơ | backend/app/api/routes/students.py | Sửa | archive xét bảo lưu/nợ/chờ chi | test_students.py; test_admissions.py |
| Inbox | backend/app/api/routes/notifications.py | Tái sử dụng/Sửa nếu cần DTO | notification_view whitelist dữ liệu mới, inbox/read giữ ownership | test_admissions.py |
| UI nghiệp vụ mới | frontend/src/EnrollmentLifecycle.tsx | Tạo, dự kiến tạo | Danh sách/preview/mốc/lịch sử, form bảo lưu/tiếp tục/quyết toán | EnrollmentLifecycle.test.tsx dự kiến tạo |
| UI tích hợp | frontend/src/Admissions.tsx; frontend/src/admissions.css; frontend/src/App.tsx; frontend/src/i18n.ts | Sửa/Tái sử dụng | BusinessForm, InvoicePanel, Finances, MyLearning, Notifications; sidebar/nhãn song ngữ | Admissions.test.tsx; E2E |
| UI mới kiểm thử | frontend/src/EnrollmentLifecycle.test.tsx | Tạo, dự kiến tạo | Quyền, số tiền hiển thị, stale/double submit, mobile | Vitest |
| Backend test | backend/tests/test_admissions.py | Sửa | Tái sử dụng fixture admissions/payload/submit/approve, thêm nhóm bảo lưu/refund/migration | SQLite + PostgreSQL |
| Hồi quy dependency | backend/tests/test_session_operations.py; backend/tests/test_schedules.py; backend/tests/test_students.py; backend/tests/test_auth_identity.py | Tái sử dụng/Sửa ca bị ảnh hưởng | Lịch, archive, tenant/root-support, thu hồi quyền | pytest theo rủi ro |
| E2E | frontend/e2e/admissions.spec.ts; frontend/e2e/scheduling.spec.ts; backend/tests/e2e_server.py | Sửa/Tái sử dụng | Luồng mới và lịch; fixture/clock chỉ môi trường test | Playwright cổng8011/5180, DB tạm |
| Fixture/cấu hình test | backend/tests/conftest.py; backend/pyproject.toml; backend/uv.lock; frontend/package.json; frontend/package-lock.json; frontend/playwright.config.ts | Tái sử dụng | schema test PostgreSQL và lệnh hiện có; chưa cần dependency mới | schema cách ly, lockfiles |
| Tài liệu | docs/workflows/reservation-refund.md; docs/admissions-delivery.md; docs/rbac.md; docs/data-model.md; docs/auth-operations.md | Sửa khi triển khai | Cập nhật đặc tả cũ bằng hành vi thực; dẫn kế hoạch, không sao chép | Review hợp đồng/checklist |
| Tiến độ | docs/plans/reservation-refund.md; docs/current-state.md; myplan.txt | Tạo kế hoạch/Sửa checkpoint/mốc | Trạng thái đợt, quyết định quan trọng | Đối chiếu phạm vi đã duyệt |
| Triển khai | compose.yaml | Tái sử dụng nguyên trạng | Chỉ dùng cấu hình có sẵn, giữ thay đổi người dùng | health/schema/baseline sau deploy |

## 4. Thứ tự và dependency

1. Chốt mục8, duyệt kế hoạch. Đọc git status và so SHA256 mục10; chỉ xem diff liên quan, không khảo sát lại từ đầu.
2. Mô hình/0014 và kiểm thử upgrade giữ dữ liệu có sẵn; xác lập hàm quyền học dùng chung và sổ bù nợ.
3. Bảo lưu/hủy/tiếp tục và API; tích hợp roster/lịch/trùng lịch/capacity/archive. Kiểm chứng dưới PostgreSQL trước thêm hoàn.
4. Chính sách, preview/duyệt/chi hoàn; tích hợp invoice/debt/collect/reverse. Test công thức/rollback/đồng thời/quyền.
5. UI và inbox Việt–Anh; preview nêu tác động tiền/quyền học, xử lý mất mạng/version cũ; E2E luồng kết hợp.
6. Hồi quy theo ma trận rủi ro, lint/build, migration smoke. Cập nhật tài liệu và trạng thái kế hoạch.
7. Khi được duyệt triển khai: lấy baseline mới/backup, build/migrate/update API/web, đối chiếu; Jira chỉ cập nhật đúng phạm vi được phép, giữ chờ nghiệm thu đến khi có xác nhận. Bàn giao theo mục7.

## 5. Migration/deployment và bảo vệ dữ liệu

- Dự kiến0014 sau0013, xác minh tên/revision chưa bị sử dụng trước code. Bổ sung bảng/cột theo hướng tương thích; mỗi enrollment cũ tạo một period mở với start=effective_at, không đặt lại ngày đăng ký.
- Không sửa tổng tiền/snapshot/kỳ hạn/payment cũ, không tự tạo refund/offset. Giữ UUID/FK, phiên bản mặc định1. Test với nhiều enrollment/invoice/payment đã đảo, session/attendance có dữ liệu.
- Kiểm thử cả nâng từ0013 có dữ liệu và DB trống lên head, metadata/schema khớp; downgrade phải từ chối khi đã có nghiệp vụ mới hoặc cần bỏ dữ liệu. Không downgrade DB thật để thử.
- Chụp baseline mới ngay trước migration: revision, counts và SHA256 toàn hàng ORDER BY id của các bảng bị ảnh hưởng, gồm toàn bộ bảng0013 và bảng lịch; không in dữ liệu cá nhân. Backup nhất quán bằng pg_dump tới vị trí đã thống nhất; thử restore trên DB cách ly trước migration thật, không in chuỗi kết nối/secret.
- Khi deploy đã được phép: build api/web; stop riêng api; run --rm --no-deps api .venv/bin/alembic upgrade head; up -d --no-deps api web. Giữ DB/Mailpit/volume/.env/compose.yaml.
- Health, OpenAPI không test helpers, current/check, frontend module; hash/count bảng không đổi phải khớp. Với bảng được thêm cột/backfill, so projection cột cũ và ánh xạ period thay vì đòi hash toàn hàng y nguyên.
- Nếu migration lỗi: dừng rollout, giữ DB và backup, chẩn đoán transaction; không tự xóa volume/restore đè hoặc chạy code cũ trên schema mới chưa kiểm chứng.
- Rủi ro chính: quyền học quá khứ bị đổi khi chỉ dựa vào status; vượt sĩ số sau tiếp tục; hoàn hai lần hoặc đảo khoản thu đã quyết toán; thay lịch sau preview; rò dữ liệu qua inbox/history. Các test mục6 là điều kiện bàn giao.

## 6. Kiểm thử dự kiến và tiêu chí đạt

Phiên lập kế hoạch không chạy test. Khi code: test nhóm thay đổi trước; hồi quy cuối một vòng theo rủi ro. Các tên file test bên dưới tồn tại trừ EnrollmentLifecycle.test.tsx đã đánh dấu dự kiến tạo.

Từ backend:
~~~powershell
uv run pytest tests/test_admissions.py -k "reservation or refund or resume" --junitxml=test-results/reservation-targeted.xml
uv run pytest tests/test_admissions.py tests/test_session_operations.py tests/test_schedules.py tests/test_students.py tests/test_auth_identity.py --junitxml=test-results/reservation-regression.xml
uv run ruff check app tests
~~~
Tên test mới phải chứa reservation/refund/resume để lệnh chọn đúng; không chấp nhận 0 test được chọn. Lệnh local mặc định bao phủ SQLite; PostgreSQL bắt buộc riêng bên dưới.

Từ gốc dự án, dùng schema tạm do fixture database_engine tạo; cấu hình DB được compose cấp, không sửa .env:
~~~powershell
docker compose run --rm --no-deps -e SYNAPSE_TEST_POSTGRES=1 -v "${PWD}/backend/app:/app/app:ro" -v "${PWD}/backend/alembic:/app/alembic:ro" -v "${PWD}/backend/tests:/app/tests:ro" -v "${PWD}/backend/test-results:/app/test-results" api uv run --frozen pytest tests/test_admissions.py tests/test_session_operations.py tests/test_schedules.py tests/test_students.py tests/test_auth_identity.py --junitxml=test-results/reservation-postgres.xml
~~~
Kiểm tra fixture vẫn đặt search_path vào test_auth_<uuid>; tuyệt đối không chạy migration test vào public. Chỉ mount app/alembic/tests/báo cáo, tránh mount .venv Windows vào Linux; nếu uv cần tải dependency thì xử lý truy cập mạng riêng, không biến lỗi môi trường thành “test đạt”.

Từ frontend:
~~~powershell
npm.cmd run test -- --reporter=json --outputFile=reservation-ui-results.json
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e -- e2e/admissions.spec.ts e2e/scheduling.spec.ts
~~~
Playwright hiện dùng API8011/web5180 và SQLite tạm. Thêm luồng vào file hiện có, không dùng tài khoản/dữ liệu thật. Từ gốc: git diff --check.

Ma trận bắt buộc:
- Tiền: min/cap/khấu trừ/làm tròn; P=0, thu một phần/đủ, khoản đảo; offset-only/cash; kỳ đến hạn UTC; override thiếu lý do; số âm/float/quá mức; không thay hóa đơn cũ.
- Thời điểm: trước/mốc/sau bảo lưu, nhiều khoảng không chồng, resume cùng lớp đã bắt đầu, hết chỗ/trùng lịch, session bị hủy/khôi phục, mốc bị đổi giờ, draft/final attendance lịch sử.
- Quyền/tenant: student/teacher không mutation tiền; staff được duyệt/chi nhưng không đổi policy; Root cần support hợp lệ; membership/support bị thu hồi trong lúc chờ khóa; cross-tenant ID và actor/key/payload replay khác.
- Nguyên tử: gây lỗi ở history/inbox và verify không có nửa giao dịch; version cũ; retry cùng key; tranh resume/chỗ cuối, thu/đảo/duyệt hoàn/chi hoàn, đổi lịch/bảo lưu; PostgreSQL phải chạy thật, không thay bằng SQLite skips.
- Migration: DB trống và0013 có dữ liệu, backfill periods đúng, constraints, schema check, downgrade guard.
- UI/E2E: đúng số tiền và quyền; preview lỗi/stale/mất mạng không tự retry mutation; từ chối/chờ chi/đã chi; inbox riêng; desktop/mobile390px/light-dark.

Đạt khi mọi ca được chọn pass, skip chỉ có giải thích SQLite và ca PostgreSQL tương ứng thực sự pass; lint/build/schema sạch; không regression số dư/quyền/roster. Chỉ chạy full backend/E2E khi thay đổi dependency chung hoặc lỗi hồi quy cho thấy phạm vi ảnh hưởng vượt nhóm trên; ghi lý do. Khi bàn giao lưu report/thời điểm/hash nguồn đã chạy và phân biệt test tự động với nghiệm thu người dùng.

## 7. Checklist nghiệm thu thủ công theo vai trò

Dùng trung tâm/dữ liệu kiểm thử được người dùng chọn; AI không seed DB thật hoặc sửa đồng hồ.

- Root hỗ trợ/quản lý: cấu hình phí khấu trừ; thoát/hết support thì thao tác bị chặn. Giáo vụ không sửa policy.
- Giáo vụ: chọn enrollment/buổi tương lai, preview danh sách buổi bị ảnh hưởng; bảo lưu có lý do. Buổi trước mốc giữ lịch sử, từ mốc không còn roster/lịch học của học viên; hóa đơn/kỳ hạn chưa đổi.
- Giáo vụ: tiếp tục cùng lớp từ một buổi sau mốc; đủ chỗ/không trùng mới thành công, không sinh hóa đơn mới hoặc cộng lại buổi đã bỏ lỡ; hủy enrollment thì không tiếp tục.
- Giáo vụ: hủy waiting có hóa đơn; không giả lập enrollment, nghĩa vụ tiền chỉ đổi khi xác nhận quyết toán.
- Giáo vụ: hai ví dụ tiền mục2.2 lần lượt tạo offset300k/chi0 và offset200k/chi250k; giáo vụ được duyệt trực tiếp. Sửa đề xuất bắt buộc lý do; chi tiền chỉ một lần, đúng phương thức/tham chiếu.
- Giáo viên: roster theo từng buổi đúng trước/sau dừng/tiếp tục; điểm danh cũ không mất; không xem hoặc thao tác khoản hoàn.
- Học viên: chỉ thấy trạng thái, lịch học, số nợ/bù trừ/hoàn của mình và thông báo tương ứng; không thấy lý do nội bộ.
- Kiểm tra chung: hai tab/version cũ, double click, mất mạng sau xác nhận, sai tenant/quyền, đổi lịch ảnh hưởng mốc, thu/đảo cạnh tranh với hoàn; không trùng giao dịch hoặc số dư âm.

## 8. Quyết định và vấn đề còn cần trả lời

Đã xác nhận trong phiên:
1. Đợt0013 đã nghiệm thu toàn bộ phạm vi đã bàn giao.
2. Có tiếp tục học lại cùng lớp sau bảo lưu, chưa chuyển lớp.
3. Giáo vụ duyệt và ghi nhận hoàn trực tiếp, phù hợp đặc tả cũ.

Đã chốt ngày2026-09-28: chỉ tiếp tục trước khi duyệt hoàn (kể cả bù nợ); NO_REFUND không tạo quyết toán tiền và không chặn tiếp tục. Người dùng yêu cầu bắt đầu triển khai.

Các chi tiết được duyệt cùng kế hoạch: chỉ mốc buổi tương lai; không giữ chỗ/không bù buổi; không bù chéo hóa đơn; scheduled là tập buổi tính phí tại thời điểm xác nhận; một quyết toán cuối/yêu cầu; chặn đảo thu sau duyệt hoàn.

## 9. Trạng thái thực thi và lần tiếp theo

- [x] Khảo sát có giới hạn, xác minh file/symbol/Docker/Jira và ghi nhận nghiệm thu0013.
- [x] Lưu kế hoạch, bản đồ file, test/deployment/checklist.
- [x] Chốt câu hỏi mục8 và người dùng duyệt kế hoạch triển khai.
- [x] Code/migration/test mới.
- [x] Deploy/Jira/bàn giao đợt mới.
- [ ] Người dùng nghiệm thu đợt mới.

Đã triển khai theo bản đồ mục3, với các chi tiết chốt khi code:
- Revision thực tế20260928_0014. Thêm AdmissionRequest.cancelled_at để biểu diễn hủy waiting qua API, giữ constraint/status cũ và FK0013. Endpoint enrollment dùng request_id để hỗ trợ waiting chưa có enrollment_id.
- EnrollmentPeriod tự tạo khi ORM thêm Enrollment; migration backfill đúng effective_at. Money SUM trên PostgreSQL ép int trước tính/JSON, tránh Decimal từ SUM(BigInteger).
- Refund API dùng /decision (approve/reject/cancel) và /disburse; DTO tiền tách snapshot khỏi số dư hiện tại. UI có preview buổi, phép tính offset/cash theo khoản duyệt và xác nhận rõ trước ghi.
- Ngoài bản đồ ban đầu, sửa assertion head trong backend/tests/test_auth_identity.py từ0013 thành0014; không đổi logic sản phẩm khi sửa test. Hợp đồng thực tế ở [đặc tả](../workflows/reservation-refund.md).

Kiểm thử cuối ngày2026-09-28 (giờ+07:00):
- backend/test-results/reservation-postgres.xml: vòng5 file dừng tại assertion head cũ;219 đạt/26skip/1 lỗi assertion. Các nhóm admissions83, session_operations31, schedules51, students30 đạt;26skip đều chỉ SQLite concurrency.
- backend/test-results/reservation-auth-final.xml:30/30 identity/migration đạt lúc22:38 sau sửa assertion. Không chạy lại4 nhóm đã đạt vì code/dependency liên quan không đổi.
- backend/test-results/reservation-final.xml là **báo cáo gộp, không phải một lần chạy riêng**: bỏ toàn bộ identity vòng cũ, thay bằng30 ca vòng cuối →225 đạt/26skip/0 lỗi,251 ca không trùng. Giữ nguyên báo cáo gốc; có provenance trong XML. Mỗi ca skip SQLite có biến thể PostgreSQL đạt.
- reservation-targeted-postgres.xml:21 ca nghiệp vụ mới PostgreSQL đạt; trùng nhóm hồi quy, không cộng thêm. SQLite vòng phát triển ở reservation-targeted.xml không dùng thay chứng nhận PostgreSQL.
- frontend/reservation-ui-results.json:76 đạt/0 lỗi (17:56); ESLint, build và Ruff đạt. Hai E2E admissions/scheduling chạy lại trên source cuối lúc22:45,2/2 đạt trong39.9s; admissions bao phủ bảo lưu→resume→bảo lưu→đề xuất→bù nợ→ghi chi và riêng tư học viên, ảnh mobile dark390px không tràn. Không chạy full suite0013.
- backend/test-results/reservation-source-manifest.json lưu SHA256 source/config/test (chuẩn hóa LF); digest tổng5835946fe974425dfb1b84c70b8e57ed4bdb2cd11bca301b9ee87b07fe96817a. Chỉ tái sử dụng kết quả khi các nguồn liên quan vẫn khớp. Hash mục10 là lịch sử **trước** triển khai, không phải source cuối.

Triển khai22:40–22:43:
- Dừng riêng API; baseline mới và pg_dump public nhất quán tại .local-backups/pre0014-baseline.json và pre0014.dump (264768byte). Restore vào PostgreSQL tmpfs tách mạng, upgrade0014/check/so hash đều đạt trước DB thật; container tạm đã dừng. Backup chứa dữ liệu riêng, bị gitignore, không đưa vào Git/Jira.
- Baseline đầu phiên khác refresh_tokens do API đang hoạt động; không sửa dữ liệu để ép khớp. Đã thay bằng baseline khi API dừng, đối chiếu toàn bộ45 bảng gồm bảng có khóa tổng hợp.
- DB thật đã upgrade20260928_0014(head), Alembic check sạch. .local-backups/deployed0014-report.json:45/45 count+SHA projection cột cũ khớp;1 period backfill=effective_at;5 bảng operation/policy/case/adjustment/disbursement rỗng. Giữ2 requests/1 enrollment/2 invoices/4 payments/0 attendance_sheets/83 sessions.
- API/web đã up --no-deps. Health API/web/module EnrollmentLifecycle/Mailpit HTTP200;10 path enrollment/refund trong OpenAPI, không __test. Manifest80 file API và34 file web khớp workspace; lưu .local-backups/deployed-{api,web}-sources.json.
- API image sha256:f11b749b9f7fd8d0b5ac3d5d838655a2f96cc88f2ea2dc67f9f1d482b38d8457; web image sha256:0e0703090a8bb2204c6d3f0f8a9735624673b21fa4f232f58d63e2eb05c02bf5. API/web StartedAt15:41:36/37 UTC.
- DB/Mailpit giữ container18c0b2202fed…/e1376460d909…, StartedAt2026-09-27T15:51:46.637635301Z/.63115817Z; volume synapselms_postgres_data, compose cổng5432 giữ nguyên. Không .env/seed/stage/commit/subagent.

Jira: SYNAPSELMS-84 và91 đã chuyển In Progress; comment10127/10128 ghi phạm vi/test/deploy/checklist. Chưa Done vì0014 chưa được người dùng nghiệm thu. 19 story0013 không đổi trong đợt này; việc đồng bộ nghiệm thu0013 còn tách riêng, không tự đóng92/99 vì phạm vi chưa đầy đủ.

Lần tiếp theo: đọc current-state → mục7 nghiệm thu theo vai trò. Nhận lỗi hoặc xác nhận của người dùng cho0014; kiểm tra git status/manifest/trạng thái thực tế trước sửa. Không bắt đầu đợt chuyển lớp hoặc chạy lại toàn bộ test nếu không có thay đổi liên quan.

## 10. Dấu vân tay file đã khảo sát

SHA256 toàn file tại lúc lập kế hoạch; không dựa vào HEAD của working tree chưa commit. File mới không có hash. Khi được duyệt triển khai, đối chiếu danh sách này; khác biệt cần đọc diff/ảnh hưởng trước code. Cấu hình hoặc test thay đổi cũng làm kết quả cũ không tự động còn hiệu lực.

| File hiện hữu | SHA256 |
| --- | --- |
| backend/app/models/admissions.py | a23d78b6273243a3f55eecd8a93e4db47b1ae2eed31f1690818ec4024b23108a |
| backend/app/models/__init__.py | c46d5118d02dde0eed10363351ec7e555c9408013336c7a1b6884f296672a46b |
| backend/app/api/admission_schemas.py | f9f82234fe6e268ed87e5218eee395411019c0ce3d3aa31dc88c7255d0e54d07 |
| backend/app/api/routes/admissions.py | d5694de5833488eb7d9a6e90c6c0e2cab9e4005a46315b32f6013541276edf52 |
| backend/app/api/routes/attendance.py | e9126801c5fc6ebee00d6c45d0335cfe4d640afcb67ce56654007cf5f5973506 |
| backend/app/api/routes/session_operations.py | b1e2ca768e0abd3754fb11374aa13dd8373bff7900b1cc55a77e93fd17a8400d |
| backend/app/api/routes/students.py | 0b9cc8b9c13186a93fe267a91204b602f58e99b2b88aa25024d06b09f1a2b9dc |
| backend/app/api/routes/notifications.py | d128c2ab4c3a44442c8113ecdea4ea448039a6db7b4dad01c055aa12679464e2 |
| backend/app/api/routes/courses.py | 59209a70eacd7d380838274c4bd8bbe07d009644f30bb8e76c25801856bc086f |
| backend/app/api/dependencies.py | 5a0e010cd9463d9a5c3c6b24f12a0fe0ea16f4cc98d6353def518d570ef9e71b |
| backend/app/api/router.py | c7e276fe546bb9ba3ef05282755c493b9893e743207486ead40cfeb4e0b7c096 |
| backend/app/services/admissions.py | b7a555ea992e5f4382a5b04de05298c1c1d3b50f9fb1e33a873913ce350bc533 |
| backend/tests/test_admissions.py | c013957a44497c6201689ff1b011d899a835660adccfc1765b5cc33d9d1ca7d3 |
| backend/tests/test_session_operations.py | 325bbe7c8025865661a64f1d76d2c9d13bdfe5a2e5f07e128b61e85b69f076b4 |
| backend/tests/test_schedules.py | 92ac8f8cbe001b78e8b8f8a17f430ec7f003493b34f7af37a55677ed564d0380 |
| backend/tests/test_students.py | cc3f6731a0cde7fdef4e6d6a8c49739f9667a5ee480fb822e43ddcd5f06f0d39 |
| backend/tests/test_auth_identity.py | bccda1a1b90820c663059bfa932cf9e258ee5b98871d8c3bc4c5bf97638ad96d |
| backend/tests/conftest.py | 90744af582308a7b3a0e50f400dc0884c54c1dbbbff83496d728ebbc22ee75bc |
| backend/tests/e2e_server.py | 0f86e9779b86067cef48bb4422e87b2a1fbaa44dae00a5785c64d810e25f61a5 |
| backend/pyproject.toml | 8c1e5217d8e7b48aa35b74df1c549e812f5775884b5a7eeb0129f8305fb2094d |
| backend/uv.lock | 9c92471949e46007c1d884ba6b29307b9a935697735f40e08002aae08774682f |
| frontend/src/Admissions.tsx | db25228d2b63ef509d0a3a6826c97d2277f4d88ac9cf060b8a97107c23b9db6e |
| frontend/src/Admissions.test.tsx | e3e1ee5f6d6939c62b5454c33e0dcbf2df10e400fcb4e372bdc8f49580ae83a4 |
| frontend/src/admissions.css | 3cfd49e281e32edd359b8c132bf7d5b77ea7132087b622855ebd4f342ed13f62 |
| frontend/src/App.tsx | 88e941866c999cf0048b373a19913ce409e9e46a724609ae1c7f1245a93f9937 |
| frontend/src/i18n.ts | 993495dc6e7e83ba9d8da747e2289577e8c5aa0eb84931ed25e43732b40dd3bb |
| frontend/e2e/admissions.spec.ts | a241829094a040ad38eafefb9526177f732337bc7a583ac8bf3e034981c81050 |
| frontend/e2e/scheduling.spec.ts | d6fd2aecc457ac18c2965a51c655b7d2509e9d9ebb2709fed23bb46636fc0492 |
| frontend/package.json | db626cf53278ed9cb7d307dbea370422300a2a37977aa14116ed0deb931d7926 |
| frontend/package-lock.json | 9fe1ae0b9e2167d7ab0cabdc3f13805c4e26947d302bc03e88512c4dbb37f357 |
| frontend/playwright.config.ts | beee5a9a6a8b6da58e37b94af67c2c51098a6dd4e93dc8f75b2d1166d2ff2fda |
| compose.yaml | e18c9dc4364b0d53f5f89fca46bcd77286b5fd94b5d0eb46802a804257da00ca |
| docs/workflows/reservation-refund.md | 649a59b29b3645e15e6415b24ab44e9f4b073437cfcda57d33f5ae5cf7491c38 |
| docs/admissions-delivery.md | 0e4c4ff02e71dbbd6d9d1682b6ab7c78789b004aeec3d80d64a8fa56ce26009a |
| docs/rbac.md | 907e1180763516eb29e7a9dcd004593712185ae3a3be8538b07cbc4914b0d2c5 |
| docs/data-model.md | 8785fdf59ac78da402063d8086704ffece272d1eb79dd70c92f32882e49b071a |
| docs/auth-operations.md | 4470955e7a787665043ca2f142b9e273bc6a401d3dbda78ea993cae8a5af132a |
