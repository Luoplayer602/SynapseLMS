# Checkpoint hiện tại

Cập nhật2026-09-30 từ kết quả triển khai Synapse Soft ngày2026-09-28. Đọc file này trước; chỉ mở tài liệu liên quan. myplan là lịch sử quyết định.

## Đợt hiện tại: Synapse Soft auth đã code/test/deploy — chờ nghiệm thu UI

- [Kế hoạch và bàn giao Synapse Soft](./plans/auth-soft-experience.md): mục7 là checklist theo vai trò; mục9 ghi code, test, deployment và giới hạn; mục10 là baseline trước code. Đã làm login/register/welcome tải thật và vỏ các nhánh email, có desktop/mobile, Việt–Anh, light/dark và reduced motion. Quyền vẫn do server quyết định.
- Full UI97 đạt;10 E2E riêng biệt của auth/account/invitations/courses đạt, auth4 chạy lại sau chỉnh assertion ảnh vẫn đạt và không cộng trùng. Lint/build đạt. Không chạy lại backend vì backend, dependency và cấu hình liên quan không đổi.
- Chỉ web được build/recreate lúc23:23+07 ngày2026-09-28. Web/module/health API/Mailpit HTTP200, Alembic vẫn0014(head);37 file nguồn/package trong image khớp workspace. API/DB/Mailpit giữ nguyên container/StartedAt, volume và dữ liệu; không chạy migration hoặc seed.
- Xác minh lại ngày2026-09-30 sau khi Docker Desktop khởi động lại: bốn container giữ nguyên ID/image nhưng có StartedAt mới khoảng08:50+07. DB từng rơi khỏi network compose nên health nông vẫn200 còn endpoint dùng DB trả500; đã nối lại chính container DB vào `synapselms_default` với alias `db`, không recreate hoặc chạm volume. Sau khôi phục, web/AuthExperience/health/Mailpit và `organizations/public` đều HTTP200; DNS `db` đúng, Alembic vẫn `20260928_0014 (head)`.
- File chính: `frontend/src/AuthExperience.tsx`, `auth.css`, `AuthExperience.test.tsx`, App/App.test/i18n và E2E auth; courses E2E chỉ thêm field xác nhận mật khẩu dùng chung. Không sửa Account/Invitations/useEmailLink/api/styles.css hoặc dependency.
- Hành động tiếp theo: người dùng nghiệm thu tại http://localhost:5173 theo mục7, ưu tiên điện thoại thật/bàn phím mềm, zoom200% thật, mạng chậm, nhánh email và từng vai trò. Viewport320–1440, mô phỏng không gian thu hẹp, bàn phím và reduced motion đã test tự động; chưa coi là nghiệm thu thiết bị thật.
- Soft là mặc định trong phạm vi auth. Theme thưởng/streak/bài tập AI và đổi dashboard chưa triển khai. Điểm số/bài kiểm tra và nền bài tập AI vẫn là nghiệp vụ backend quan trọng tiếp theo nhưng không chặn auth trong khảo sát có giới hạn.
- Người dùng đã commit phần trước trong phiên; HEAD hiện tại `7d1df97b81c8b7e116528032d1afa37d65aab007`. Thay đổi auth/tài liệu còn ở working tree; AI không stage/commit, sửa.env/compose, đổi Jira hoặc dùng subagent.

## Đợt0014: đã code/test/deploy; người dùng test nhanh chưa thấy vấn đề

- Hoàn tất bảo lưu/hủy từ buổi tương lai → quyền học/lịch/roster/điểm danh → tiếp tục cùng lớp → quyết toán/bù nợ/ghi chi → inbox. Chỉ tiếp tục trước quyết toán hoàn dương; NO_REFUND không chặn. Giáo vụ duyệt/ghi chi trực tiếp; manager/Root hỗ trợ cấu hình khấu trừ.
- [Kế hoạch và bằng chứng bàn giao](./plans/reservation-refund.md): mục3 bản đồ file, mục7 checklist theo vai trò, mục9 test/deploy/Jira/source manifest. [Hợp đồng nghiệp vụ/API](./workflows/reservation-refund.md). Không tạo handoff trùng.
- Backend hồi quy bị ảnh hưởng225 đạt/26skip SQLite concurrency, PostgreSQL tương ứng đạt; báo cáo gộp không trùng reservation-final.xml. Vòng đầu lỗi assertion head cũ, đã sửa và chạy lại identity/migration30/30. UI76 đạt tại mốc0014, E2E admissions/scheduling2/2 đạt; Ruff/ESLint/build/schema sạch. Không dùng full449/UI72/E2E15 của0013 để chứng nhận0014.
- Tại rollout0014, Docker API/web đã cập nhật, Alembic20260928_0014(head), health/OpenAPI đạt và không test helpers.80 file API/34 file web trong image khớp workspace. DB/Mailpit giữ nguyên container/StartedAt/volume; compose DB5432 của người dùng giữ nguyên.
- Backup .local-backups/pre0014.dump đã restore/migrate thử PostgreSQL tách biệt trước rollout thật.45 bảng cũ count/hash projection khớp;1 period backfill đúng;5 bảng nghiệp vụ hoàn khác rỗng. Baseline2 requests/1 enrollment/2 invoices/4 payments/0 sheets/83 sessions. Backup/báo cáo riêng bị gitignore, không seed dữ liệu thật.
- Jira SYNAPSELMS-84/91 In Progress, comment10127/10128 theo lần đọc cuối; không truy vấn hoặc cập nhật trong đợt auth. **Người dùng báo test nhanh nghiệp vụ mới chưa có vấn đề**, nhưng chưa xác nhận toàn bộ checklist0014; chưa Done.
- Hành động tiếp theo: người dùng nghiệm thu tại **Bảo lưu & hoàn phí** theo mục7 kế hoạch; sửa lỗi trong scope nếu có. Khi tiếp tục kiểm tra git status, source manifest backend/test-results/reservation-source-manifest.json và Docker thật trước tái sử dụng kết quả.

## Trạng thái cũ và giới hạn

- 0013 tuyển sinh/học phí/điểm danh/thông báo đã được người dùng nghiệm thu toàn bộ phạm vi bàn giao. Hồ sơ lịch sử [next-session-handoff](./next-session-handoff.md) không còn là checkpoint hiện tại.
- 19 story0013 vẫn In Progress theo lần đọc cuối; chưa đồng bộ nghiệm thu trong đợt0014. Không tự Done FEE-07/92 (mới browser print) hoặc ATT-05/99 (mới chuyên cần cá nhân).78/79/152 đã Done; calendar tháng vẫn chưa code.
- Chưa chuyển lớp/học lại, giữ chỗ/bù buổi/gia hạn, sửa sai hoàn đã duyệt, chuyển ngân hàng/ví, PDF server/báo cáo lớp/calendar tháng/AI/học liệu/email/SMS. BUG-004 native select Chrome và UI log chung vẫn hoãn.
- Kết quả cũ chỉ tái sử dụng khi nguồn/dependency/config liên quan còn khớp. Manifest0014 và manifest auth tách riêng; không dùng manifest web0014 để chứng nhận UI auth mới.
