# Product Requirements Document — SynapseLMS

**Phiên bản:** 0.1  
**Trạng thái:** Draft đã chốt phạm vi nền tảng  
**Mô hình thực hiện:** Một nhà phát triển chính và AI hỗ trợ

## 1. Tầm nhìn

SynapseLMS là hệ thống quản lý học tập mã nguồn mở cho trung tâm ngoại ngữ. Sản phẩm phải dễ cài đặt, dễ làm quen, có thể tùy biến theo quy trình từng trung tâm và không khóa người dùng vào một nhà cung cấp AI.

## 2. Người dùng

- **Root Admin:** quản lý vòng đời các trung tâm trên cùng hệ thống.
- **Quản lý trung tâm:** quản lý cấu hình, nhân sự và dữ liệu của trung tâm mình.
- **Giáo vụ/tư vấn:** quản lý học viên, đăng ký lớp, lịch, học phí và các bước xét duyệt.
- **Giáo viên:** xem lớp phụ trách, điểm danh, nhập điểm, giao bài và xem tiến độ học viên.
- **Học viên:** quản lý hồ sơ cá nhân, gửi yêu cầu đăng ký lớp, xem lịch, học phí, bài tập và tiến độ của bản thân.
- **Phụ huynh/người giám hộ:** là thông tin liên hệ gắn với học viên trong MVP, chưa có tài khoản riêng.

Mỗi tài khoản nghiệp vụ chỉ có một vai trò và thuộc một trung tâm tại một thời điểm. Root Admin là tài khoản hệ thống riêng. Học viên có thể được chuyển sang trung tâm khác bằng quy trình có kiểm soát và audit.

## 3. Giá trị cốt lõi

- Cách ly dữ liệu chắc chắn giữa nhiều trung tâm.
- Quy trình có thể cấu hình thay vì áp đặt một mô hình vận hành duy nhất.
- Giao diện song ngữ Việt/Anh, sẵn sàng bổ sung ngôn ngữ.
- AI hỗ trợ con người, không tự thực hiện quyết định nghiệp vụ có hậu quả.
- Có thể tự host bằng Docker hoặc triển khai trên cloud.

## 4. Phạm vi MVP

### 4.1 Nền tảng

- Multi-tenant với Root Admin.
- Đăng nhập email/mật khẩu, access token và refresh token.
- RBAC và giới hạn dữ liệu theo trung tâm/chi nhánh.
- Root Admin có chế độ truy cập tenant để hỗ trợ kỹ thuật; phiên hỗ trợ phải có lý do và audit log.
- Giao diện Việt/Anh.
- Thông báo trong ứng dụng và adapter mở rộng email/SMS/Zalo.

### 4.2 Học viên và đăng ký

- Học viên tự tạo tài khoản, cung cấp hồ sơ cá nhân và thông tin liên hệ người giám hộ khi cần.
- Mã học viên là duy nhất trên toàn hệ thống.
- Học viên có thể yêu cầu chuyển trung tâm; trung tâm cũ và trung tâm mới đều phải xác nhận.
- Sau chuyển, trung tâm mới xem được toàn bộ lịch sử học tập và giao dịch nguồn dưới dạng chỉ đọc.
- Công nợ cũ không chặn chuyển, vẫn thuộc trung tâm cũ và được hiển thị kèm cảnh báo.
- Học viên hoặc giáo vụ đăng ký khóa học; học viên không chọn lớp trực tiếp trong luồng mặc định.
- Giáo vụ duyệt hoặc từ chối yêu cầu; khi từ chối bắt buộc nhập lý do.
- Khi duyệt, hệ thống tạo hóa đơn ngay rồi thử xếp lớp tự động.
- Nếu không thể xếp tự động, yêu cầu được chuyển cho giáo vụ xếp lớp thủ công.
- Trung tâm có thể bật/tắt việc chặn yêu cầu đăng ký mới khi học viên còn công nợ.
- Kiểm tra sĩ số, đăng ký trùng, điều kiện đầu vào và xung đột lịch trước khi tạo Enrollment.
- Hỗ trợ chuyển lớp, bảo lưu thủ công và danh sách chờ.

### 4.3 Khóa học, lớp và lịch

- Khóa học đa ngôn ngữ, dùng cấp độ phổ biến và cho phép đổi nhãn hiển thị.
- Mẫu đánh giá và điều kiện hoàn thành được cấu hình theo khóa học.
- Lịch lặp hàng tuần hoặc lịch riêng theo từng buổi.
- Một lớp có nhiều giáo viên; có thể chỉ định giáo viên dạy thay theo buổi.
- Cho phép lưu liên kết lớp trực tuyến; chưa tích hợp trực tiếp Zoom/Google Meet.

### 4.4 Học phí

- Học phí được định nghĩa theo khóa học.
- Thanh toán một lần hoặc trả góp nhiều đợt.
- Mã giảm giá theo phần trăm hoặc số tiền cố định, có thời hạn và giới hạn lượt dùng.
- Bảo lưu do giáo vụ xử lý từ một buổi học được chọn; bảo lưu không tự động dừng các kỳ trả góp.
- Sau bảo lưu, hệ thống đề xuất số tiền hoàn dựa trên học phí sau giảm giá và phần chưa học, tính cả buổi bắt đầu bảo lưu; trung tâm có thể cấu hình phí khấu trừ.
- Khoản hoàn ưu tiên bù trừ công nợ; phần dư mới hoàn bằng tiền mặt hoặc chuyển khoản, có lịch sử và audit log; không giữ thành số dư nội bộ.
- Giáo vụ có quyền hoàn phí; không bắt buộc quản lý duyệt trong quy trình mặc định.
- Phiếu thu cơ bản; chưa phải hóa đơn điện tử theo chuẩn kế toán.

### 4.5 Điểm danh và kết quả

- Điểm danh: có mặt, vắng có phép, vắng không phép, đi muộn, về sớm và ghi chú.
- Giáo viên/giáo vụ thực hiện điểm danh; QR check-in để sau MVP.
- Theo dõi nghe, nói, đọc, viết theo mẫu của khóa học.
- Điều kiện hoàn thành có thể kết hợp điểm, chuyên cần và xác nhận.
- Giáo viên cấu hình thời điểm công bố kết quả theo lớp.
- Chỉ giáo viên phụ trách được nhập hoặc sửa điểm; giáo vụ chỉ được xem kết quả.

### 4.6 AI

- Tư vấn lớp dựa trên các tiêu chí được bật: bài kiểm tra đầu vào, mục tiêu, độ tuổi, lịch rảnh, hình thức học và ngân sách.
- Hệ thống nghiệp vụ lọc lớp hợp lệ trước; AI chỉ xếp hạng và giải thích.
- Sinh bài micro-learning: trắc nghiệm, điền từ, sắp xếp, ghép cặp và nghe audio.
- Tóm tắt tiến độ từ dữ liệu có nguồn; học viên xem bản thân, giáo viên xem lớp phụ trách.
- Có schema validation, timeout, retry giới hạn, fallback và theo dõi chi phí.

### 4.7 Nội dung bổ trợ

- Cho phép gắn tài nguyên YouTube/YouTube Music hợp lệ như nội dung tùy chọn.
- Không tích hợp trực tiếp Better Lyrics trong MVP vì phụ thuộc extension trình duyệt và có rủi ro điều khoản/bản quyền.

## 5. Ngoài phạm vi MVP

- Ứng dụng mobile native.
- Video conference tích hợp sâu.
- Đăng nhập Google hoặc nhà cung cấp danh tính khác.
- QR check-in.
- Cổng thanh toán thực tế và hóa đơn điện tử.
- Tài khoản phụ huynh.
- AI chấm phát âm thời gian thực.

## 6. Tiêu chí thành công MVP

- Hai trung tâm hoạt động trên cùng hệ thống mà không truy cập chéo dữ liệu.
- Hoàn thành luồng mở lớp → yêu cầu đăng ký → duyệt → thu phí → học → điểm danh → nhập kết quả → tóm tắt tiến độ.
- Các luồng đăng ký, học phí, điểm danh và AI có test tự động.
- Hệ thống cài đặt thành công bằng tài liệu Docker trên máy mới.
- Không còn lỗi bảo mật mức nghiêm trọng hoặc cao tại thời điểm phát hành.

## 7. Nguyên tắc lập kế hoạch

Dự án không giả định có đội backend/frontend/QA riêng. Công việc được chia theo lát cắt nhỏ và thực hiện tuần tự bởi một người với AI hỗ trợ. Ước lượng ban đầu dùng Story Point để so sánh độ phức tạp, không dùng để cam kết ngày hoàn thành. Vận tốc sẽ được hiệu chỉnh sau hai iteration.
