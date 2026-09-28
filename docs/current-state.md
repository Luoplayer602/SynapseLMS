# Checkpoint hiện tại

Cập nhật2026-09-28, sau lập kế hoạch UI auth; rollout0014 lúc22:41+07:00 giữ nguyên. Đọc file này trước; chỉ mở tài liệu liên quan. myplan là lịch sử quyết định.

## Đợt tiếp theo: đã lập kế hoạch UI auth, chưa duyệt triển khai

- [Kế hoạch Synapse Soft: đăng nhập, đăng ký và màn chào](./plans/auth-soft-experience.md) chứa đánh giá backend, thiết kế PC/mobile, bản đồ file đã xác minh, test và baseline SHA256. Chưa code/test/deploy/Jira đợt UI.
- Người dùng chọn Soft mặc định, theme khác làm phần thưởng chuỗi ngày bài tập AI; giữ chào nhanh khi tải. Login một form, role do server quyết định. Streak/quyền mở theme thuộc đợt AI riêng, chưa triển khai giả trên client.
- Kiểm tra thực tế: Docker0014/health ổn, source khớp manifest đã test; chưa thấy backend blocker cho đổi UI auth. Điểm số/bài kiểm tra và bài tập AI còn quan trọng nhưng không là dependency của đợt này. Không coi backend đã hoàn chỉnh hoặc0014 đã nghiệm thu.
- Hành động tiếp theo: chờ duyệt kế hoạch auth; khi được duyệt so git status/SHA mục10 rồi triển khai. Nếu có lỗi nghiệm thu0014 liên quan tiền/quyền/dữ liệu thì ưu tiên sửa trước rollout UI. Không đọc lại toàn myplan.

## Đợt0014: đã code, test, deploy — chờ người dùng nghiệm thu

- Hoàn tất bảo lưu/hủy từ buổi tương lai → quyền học/lịch/roster/điểm danh → tiếp tục cùng lớp → quyết toán/bù nợ/ghi chi → inbox. Chỉ tiếp tục trước quyết toán hoàn dương; NO_REFUND không chặn. Giáo vụ duyệt/ghi chi trực tiếp; manager/Root hỗ trợ cấu hình khấu trừ.
- [Kế hoạch và bằng chứng bàn giao](./plans/reservation-refund.md): mục3 bản đồ file, mục7 checklist theo vai trò, mục9 test/deploy/Jira/source manifest. [Hợp đồng nghiệp vụ/API](./workflows/reservation-refund.md). Không tạo handoff trùng.
- Backend hồi quy bị ảnh hưởng225 đạt/26skip SQLite concurrency, PostgreSQL tương ứng đạt; báo cáo gộp không trùng reservation-final.xml. Vòng đầu lỗi assertion head cũ, đã sửa và chạy lại identity/migration30/30. UI76 đạt, E2E admissions/scheduling2/2 đạt; Ruff/ESLint/build/schema sạch. Không dùng full449/UI72/E2E15 của0013 để chứng nhận0014.
- Docker API/web đã cập nhật, Alembic20260928_0014(head), health/OpenAPI đạt và không test helpers.80 file API/34 file web trong image khớp workspace. DB/Mailpit giữ nguyên container/StartedAt/volume; compose DB5432 của người dùng giữ nguyên.
- Backup .local-backups/pre0014.dump đã restore/migrate thử PostgreSQL tách biệt trước rollout thật.45 bảng cũ count/hash projection khớp;1 period backfill đúng;5 bảng nghiệp vụ hoàn khác rỗng. Baseline2 requests/1 enrollment/2 invoices/4 payments/0 sheets/83 sessions. Backup/báo cáo riêng bị gitignore, không seed dữ liệu thật.
- Jira SYNAPSELMS-84/91 In Progress, comment10127/10128. **Chưa người dùng nghiệm thu0014**, chưa Done.
- Hành động tiếp theo: người dùng nghiệm thu tại **Bảo lưu & hoàn phí** theo mục7 kế hoạch; sửa lỗi trong scope nếu có. Khi tiếp tục kiểm tra git status, source manifest backend/test-results/reservation-source-manifest.json và Docker thật trước tái sử dụng kết quả.

## Trạng thái cũ và giới hạn

- 0013 tuyển sinh/học phí/điểm danh/thông báo đã được người dùng nghiệm thu toàn bộ phạm vi bàn giao. Hồ sơ lịch sử [next-session-handoff](./next-session-handoff.md) không còn là checkpoint hiện tại.
- 19 story0013 vẫn In Progress theo lần đọc cuối; chưa đồng bộ nghiệm thu trong đợt0014. Không tự Done FEE-07/92 (mới browser print) hoặc ATT-05/99 (mới chuyên cần cá nhân).78/79/152 đã Done; calendar tháng vẫn chưa code.
- Chưa chuyển lớp/học lại, giữ chỗ/bù buổi/gia hạn, sửa sai hoàn đã duyệt, chuyển ngân hàng/ví, PDF server/báo cáo lớp/calendar tháng/AI/học liệu/email/SMS. BUG-004 native select Chrome và UI log chung vẫn hoãn.
- Đợt này chưa stage/commit, không sửa.env, không subagent hoặc xóa volume. Giữ mọi thay đổi có sẵn; HEAD trước triển khai3c3a1431c4c4ffbac319aa3ef59a34162de0dea7,37 file kế hoạch khớp trước code. Hiện working tree có thay đổi0014 và tài liệu chưa commit.
