# Quản lý giáo trình và tài liệu tham khảo

Trạng thái: luồng bổ sung, chỉ triển khai khi phù hợp; không là điều kiện hoàn thành giai đoạn xác thực/phân quyền hoặc mốc beta hiện tại. Quyền chi tiết, hạn mức và chính sách sau khóa học dưới đây là mặc định đề xuất, chưa phải quyết định khảo sát đã xác nhận. Chưa triển khai code hoặc migration.

## Phạm vi

Mỗi trung tâm có thư viện học liệu riêng gồm giáo trình, tài liệu tham khảo, slide, bài đọc, audio và liên kết ngoài. Giáo trình có thông tin tên, tác giả, nhà xuất bản, ấn bản, ISBN tùy chọn, ngôn ngữ/cấp độ và cấu trúc chương/bài. Không bắt buộc có file toàn bộ sách: có thể chỉ lưu metadata, hướng dẫn trang/chương và liên kết nguồn.

Bản tối thiểu hỗ trợ PDF, PNG/JPEG, MP3 và HTTPS link. DOCX/PPTX, video upload và chuyển đổi xem trước để giai đoạn sau. PDF và ảnh có xem trước, audio có trình phát; link mở ngoài với nhãn nguồn. Ghi tác giả/nguồn và cơ sở cho phép chia sẻ ở mỗi tài liệu; tài liệu có giấy phép hạn chế chỉ lưu thông tin hoặc đường dẫn được phép chia sẻ.

Không gồm thư viện mượn/trả sách vật lý, bán giáo trình, DRM hay đồng biên tập tài liệu. Nút tắt tải xuống không được quảng bá là ngăn sao chép tuyệt đối.

## Quyền mặc định đề xuất

| Vai trò | Thư viện chung của trung tâm | Tài liệu trong lớp |
|---|---|---|
| Root Admin | Qua phiên hỗ trợ có lý do/audit | Cùng cơ chế phiên hỗ trợ |
| Quản lý | Quản lý, công bố/thu hồi, cấu hình quota | Quản lý trong tenant |
| Giáo vụ | Biên mục, gắn khóa, công bố/thu hồi | Gắn và phân phối tới lớp trong tenant |
| Giáo viên | Xem nội dung dành cho giáo viên; tạo bản nháp và gửi đề xuất vào thư viện chung | Tạo/công bố tài liệu của mình ở lớp phụ trách; sử dụng tài liệu thư viện đã duyệt |
| Học viên | Không duyệt toàn bộ thư viện nội bộ | Xem tài liệu đã công bố cho lớp mình có enrollment hợp lệ |

Giáo viên không sửa bản gốc của giáo viên khác hoặc đổi giáo trình chuẩn toàn khóa. Muốn đưa tài liệu lớp thành học liệu chung: gửi đề xuất, giáo vụ/quản lý duyệt; từ chối có lý do. Giáo viên dạy thay chỉ có quyền theo buổi được phân công, không tự có quyền toàn lớp.

Đáp án và hướng dẫn giáo viên là tài liệu riêng gắn đối tượng `teachers`, không đặt chung file học viên rồi chỉ ẩn nút trên UI. Kiểm tra quyền ở cả danh sách, chi tiết, tìm kiếm, xem trước và tải file.

## Luồng 1 — Đưa tài liệu vào thư viện

1. Người có quyền tạo bản nháp, nhập tên, loại, ngôn ngữ/cấp độ, nhãn, tác giả/nguồn, mô tả và đối tượng sử dụng.
2. Tải file hoặc thêm HTTPS link. Backend lấy tenant từ phiên xác thực, sinh khóa lưu trữ riêng; không dùng tên file của người dùng làm đường dẫn.
3. File ở trạng thái kiểm tra: kiểm tra kích thước, MIME/chữ ký file, định dạng và quét mã độc. Chỉ file đạt kiểm tra mới được công bố; lỗi có trạng thái rõ và cho phép thử lại. Link không được server tự tải về trong MVP.
4. Lưu phiên bản đầu tiên. Người tạo có thể xem bản nháp theo quyền; học viên chưa nhìn thấy.
5. Giáo vụ/quản lý công bố tài liệu chung; giáo viên công bố tài liệu riêng trong lớp phụ trách hoặc gửi đề xuất duyệt thư viện chung.

Trạng thái nội dung: `DRAFT → PUBLISHED → ARCHIVED`; có thể `PUBLISHED → WITHDRAWN` để thu hồi truy cập. Luồng duyệt là bản ghi riêng `PENDING → APPROVED/REJECTED`. Trạng thái file tách biệt `PENDING_CHECK → READY/REJECTED`; hạ tầng kiểm tra lỗi thì giữ pending và chặn công bố.

`ARCHIVED` ngăn gắn mới nhưng các lớp đã gắn vẫn được đọc phiên bản cũ theo quyền; `WITHDRAWN` chặn truy cập bình thường ở mọi lớp, lưu lý do và lịch sử. Bản đã công bố không bị ghi đè; chỉnh sửa nội dung tạo phiên bản mới.

## Luồng 2 — Xây dựng giáo trình và gắn khóa học

1. Giáo vụ/quản lý tạo giáo trình và các chương/bài có thứ tự; gắn tài liệu cùng số trang hoặc hướng dẫn học, đánh dấu bắt buộc/tham khảo.
2. Công bố một phiên bản giáo trình gồm cấu trúc và các phiên bản tài liệu cụ thể.
3. Gắn phiên bản đó với khóa học; một khóa có thể có giáo trình chính và giáo trình bổ trợ, kèm nhiều tài liệu tham khảo.
4. Khi mở lớp, ghi nhận phiên bản giáo trình áp dụng. Giáo viên có thể gắn bài/chương với buổi học và thêm tài liệu bổ trợ theo quyền.
5. Khi giáo trình có phiên bản mới, hiển thị thông báo để giáo vụ/quản lý chủ động cập nhật lớp. Không tự thay nội dung lớp đang học; thay phiên bản có ghi actor, thời gian và lý do.

Việc gắn tài liệu với khóa chỉ tạo mẫu nội dung cho lớp; không tự cấp quyền cho mọi người đang xem trang khóa công khai.

## Luồng 3 — Phát tài liệu và học viên sử dụng

1. Giáo viên hoặc giáo vụ chọn phiên bản tài liệu, lớp/buổi và thời điểm công bố; mặc định công bố ngay khi xác nhận.
2. Khi đến thời điểm, học viên có enrollment hợp lệ thấy mục “Tài liệu” trong lớp và nhận thông báo trong ứng dụng. Bản tối thiểu tính khả dụng từ thời gian lưu; thông báo cần job/outbox có chống gửi trùng.
3. Trước mỗi lần xem/tải, backend kiểm tra user, tenant, enrollment, đối tượng tài liệu, trạng thái phiên bản và thời điểm công bố.
4. Đề xuất cho học viên đã hoàn thành khóa đọc lại tài liệu khi vẫn là thành viên trung tâm; chờ duyệt/hủy đăng ký không có quyền. Bảo lưu tạm dừng nội dung mới, giữ các tài liệu đã được cấp trước thời điểm bảo lưu; quyền đã cấp cần lưu rõ, không suy diễn từ trạng thái enrollment hiện tại.
5. Chuyển trung tâm không tự chuyển quyền đối với file giáo trình trung tâm cũ. Lịch sử học có thể giữ tên/phiên bản đã sử dụng; chia sẻ file nguồn cần chính sách và quyền chia sẻ riêng.

MVP dùng download qua API kiểm tra quyền ở mỗi request để thu hồi có hiệu lực ngay. Adapter S3 có thể stream qua API; nếu bật signed URL ở bước mở rộng, phải ghi rõ URL đã cấp có thể còn dùng đến hết TTL ngắn và không hứa thu hồi tức thời. File đã tải về máy học viên không thể thu hồi.

## Luồng 4 — Cập nhật, thu hồi và lưu trữ

- Upload mới tạo `MaterialVersion`; assignment của lớp vẫn trỏ đúng phiên bản cũ đến khi có quyết định cập nhật.
- Thu hồi dùng khi nội dung sai hoặc không còn được phép chia sẻ; chặn cả xem trước/tải, ghi lý do và thông báo các lớp bị ảnh hưởng.
- Không xóa cứng tài liệu/phiên bản đang được sử dụng. Dọn bản nháp và file mồ côi theo thời gian lưu giữ có cấu hình; kiểm tra tham chiếu trước khi xóa file.
- Database transaction không bao trùm object storage: có bước finalize upload và job dọn orphan, retry không tạo hai phiên bản hoặc tính quota hai lần.
- Backup/restore gồm metadata, phiên bản, quyền và file; kiểm thử sau restore truy cập được đúng phiên bản, không chỉ khôi phục bảng.

## Mô hình dữ liệu dự kiến

| Thực thể | Nội dung chính |
|---|---|
| `materials` | Tenant, tên, loại, nguồn, đối tượng, creator và vòng đời |
| `material_versions` | Tenant, material, số phiên bản, file hoặc link, checksum, dung lượng, MIME và trạng thái kiểm tra |
| `material_review_requests` | Tenant, phiên bản được đề xuất, người gửi/duyệt, trạng thái và lý do |
| `curricula`, `curriculum_versions` | Giáo trình, metadata ấn bản và các bản phát hành không ghi đè |
| `curriculum_units`, `curriculum_materials` | Chương/bài của một phiên bản giáo trình, thứ tự và phiên bản tài liệu liên quan |
| `course_curricula`, `class_curricula` | Khóa/lớp và phiên bản giáo trình áp dụng |
| `material_assignments` | Tenant, phiên bản, khóa/lớp/buổi, đối tượng, thời gian công bố; scope cụ thể, tránh liên kết đa hình không kiểm tra được |
| `student_material_grants` | Quyền đã cấp cho học viên/enrollment, thời điểm và thu hồi; phục vụ chính sách bảo lưu |

Các liên kết phải kiểm tra cùng tenant, ưu tiên khóa ngoại ghép `(organization_id, id)`; không chỉ lọc danh sách. File lưu ngoài database trong volume riêng hoặc S3 private. Không dùng đường dẫn public chứa file gốc; quota kiểm tra cả trước upload và khi finalize. Hạn mức file/quota sẽ chốt khi triển khai; metadata và object key không xuất hiện trong response học viên nếu không cần thiết.

## Backlog đề xuất — Epic 16

P1/P2 biểu thị thứ tự ưu tiên nội bộ nếu module được đưa vào triển khai, không cam kết làm trước beta. SP chỉ là ước lượng tương đối ban đầu, không quy đổi thành ngày cam kết. Test và UI nằm trong từng story.

| ID | Công việc | Ưu tiên | SP | Nghiệm thu chính |
|---|---|---|---:|---|
| MAT-01 | Model/migration học liệu và policy tenant | P1 | 5 | Không thể liên kết material/course/class khác tenant; có migration với test dữ liệu |
| MAT-02 | Storage private, upload/finalize, kiểm tra file và quota | P1 | 8 | Sai loại/quá lớn/file bị từ chối không công bố được; retry không nhân bản |
| MAT-03 | Thư viện, tìm kiếm/lọc, bản nháp và duyệt | P1 | 5 | Quản lý/giáo vụ vận hành thư viện; giáo viên gửi duyệt; học viên không thấy bản nháp |
| MAT-04 | Giáo trình chương/bài, phiên bản và gắn khóa | P1 | 8 | Lớp mới lấy đúng phiên bản; bản phát hành không bị ghi đè |
| MAT-05 | Gắn lớp/buổi, công bố và thông báo | P1 | 5 | Giáo viên đúng phân công mới được công bố; thời gian mở và thông báo chống trùng |
| MAT-06 | Trang tài liệu học viên, preview/audio/download có kiểm tra quyền | P1 | 8 | Chặn enrollment chưa duyệt, khác lớp/tenant, tài liệu đáp án; đúng chính sách bảo lưu/chuyển |
| MAT-07 | Nâng phiên bản, archive/withdraw, audit và restore | P1 | 5 | Lớp giữ bản cũ; thu hồi chặn tải; restore khôi phục file và quyền |
| MAT-08 | DOCX/PPTX/video và chuyển đổi xem trước | P2 | 8 | Xử lý nền, giới hạn tài nguyên và trạng thái lỗi rõ |
| MAT-09 | Theo dõi đọc/nghe và tìm kiếm trong nội dung | P2 | 5 | Phân biệt mở file với hoàn thành học; kết quả tìm kiếm vẫn theo quyền |
| MAT-10 | AI sinh bài/tóm tắt dựa trên học liệu có trích nguồn | P2 | 8 | Chỉ dùng nội dung được cấp quyền; cách ly retrieval theo tenant/lớp và giáo viên duyệt bài |

MAT-10 phụ thuộc cả module AI và xử lý nội dung: không tự gửi toàn bộ giáo trình tới Gemini/API bên ngoài. Cần chính sách cho phép xử lý, lọc dữ liệu, trích dẫn phiên bản/trang và xử lý tài liệu chứa chỉ dẫn độc hại. Đánh dấu đây là mở rộng sau luồng học liệu thủ công hoạt động ổn định.

## Thứ tự thực hiện và kiểm thử

1. Hoàn thiện checkpoint auth và tenant/RBAC; dùng lớp/khóa test để kiểm tra quyền.
2. MAT-01 → MAT-02 → MAT-03: lát cắt tạo/tải/duyệt thư viện; phụ thuộc storage và audit tối thiểu.
3. Khi CRS/CLS/SCH/ENR đã có: MAT-04 → MAT-05 → MAT-06; NTF-01 cung cấp thông báo, luồng bảo lưu/chuyển cung cấp trạng thái quyền.
4. Khi triển khai module, MAT-07 hoàn thiện trước khi phát hành học liệu; MAT-08–10 sau khi đo nhu cầu thực tế. Không ép học liệu vào bước auth hoặc mốc beta hiện tại.

Các ca bắt buộc: đoán UUID/file key khác tenant; giáo viên không được phân công; học viên chưa duyệt/hủy/bảo lưu/chuyển; lộ đáp án qua search/preview; công bố trước lịch; thay file nhưng lớp vẫn dùng phiên bản cũ; thu hồi; retry upload; vượt quota đồng thời; MIME giả/path traversal; storage hoặc kiểm tra file lỗi; tải audio theo range vẫn kiểm tra quyền; phục hồi backup. Test quyền chạy trên API và PostgreSQL, thêm E2E giáo viên công bố → học viên đọc → thu hồi → học viên bị chặn.
