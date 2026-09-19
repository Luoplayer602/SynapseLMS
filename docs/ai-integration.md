# Tích hợp AI SynapseLMS

**Phiên bản:** 0.1  
**Provider demo mặc định:** Gemini API

## Provider được hỗ trợ

- Cloud API: Gemini, OpenAI, Claude và Hugging Face.
- Local/OpenAI-compatible endpoint: Ollama, LM Studio và dịch vụ tương thích khác.
- Provider mới được thêm qua adapter, không sửa logic nghiệp vụ.

## Cấu hình

Root Admin quản lý provider, model, base URL và API key dùng chung cho hệ thống. Trung tâm không tự nhập API key trong MVP. Có thể cấu hình provider/model theo loại tác vụ nhưng secret chỉ do Root Admin quản lý.

```text
AIProvider
├── generate_structured(request, schema)
├── generate_text(request)
├── health_check()
└── usage_metadata()
```

Mỗi cấu hình gồm:

- Provider type.
- Model name.
- Base URL cho endpoint local/tương thích.
- Secret reference, không lưu API key plaintext trong bảng nghiệp vụ.
- Timeout, retry limit, token/output limit.
- Allowed tasks và trạng thái bật/tắt.

## Luồng gọi AI

```text
Domain request
  → deterministic eligibility/filtering
  → privacy whitelist payload
  → prompt template + version
  → provider adapter
  → schema validation
  → safety/business validation
  → persist result + usage
  → human review where required
```

## Fallback

- Tư vấn lớp: fallback sang xếp hạng dựa trên quy tắc.
- Sinh bài: báo lỗi có thể thử lại; không lưu bài sai schema.
- Tóm tắt tiến độ: hiển thị dữ liệu tổng hợp không-AI nếu provider lỗi.
- Circuit breaker tạm dừng provider khi lỗi liên tiếp.

## Bảo mật và riêng tư

- Chỉ gửi trường nằm trong whitelist; ưu tiên mã giả danh thay vì tên/email/số điện thoại.
- Không gửi lịch sử tài chính cho tác vụ không cần tài chính.
- API key mã hóa bằng secret do người triển khai cung cấp hoặc secret manager của cloud.
- Log lưu provider/model, phiên bản prompt, token, độ trễ và trạng thái; không log prompt chứa dữ liệu cá nhân theo mặc định.
- Có thể tắt hoàn toàn AI mà các nghiệp vụ cốt lõi vẫn hoạt động.

## Kiểm thử

- CI dùng fake provider có phản hồi cố định; không gọi API thật.
- Contract test cho từng adapter.
- Evaluation dataset riêng cho tư vấn lớp, bài tập và tóm tắt tiến độ.
- Smoke test Gemini API chỉ chạy thủ công hoặc theo môi trường được cấp secret.

