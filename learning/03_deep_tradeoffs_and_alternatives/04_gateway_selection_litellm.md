# 04. Tại Sao Chọn LiteLLM Proxy Thay Vì Tự Viết API Gateway Hoặc Dùng Nginx?

Trong kiến trúc của đồ án này, container `litellm-gateway` đóng vai trò là "bộ não điều phối giao thông" tiếp nhận toàn bộ request từ bên ngoài.

Tại sao chúng ta không dùng **Nginx**, không tự code một service bằng **FastAPI**, mà lại chọn **LiteLLM Proxy**?

---

## 1. Hạn Chế Của Nginx / Traefik Đối Với Tải LLM

Nginx và Traefik là những Web Server / Reverse Proxy xuất sắc nhất thế giới cho ứng dụng web truyền thống, nhưng chúng gặp các hạn chế nghiêm trọng khi xử lý suy luận LLM:

1. **Không thể đọc payload nội dung JSON ở tầng ứng dụng**: Nginx hoạt động dựa trên URL path hoặc HTTP headers. Nó không thể mở body JSON của request để đọc trường `"model": "qwen2.5"` để quyết định điều hướng sang backend nào.
2. **Không hiểu khái niệm Token & Chi phí**: Nginx chỉ đếm số Bytes truyền qua mạng hoặc số mã lỗi HTTP (200, 500). Nó không thể phân tích xem request tiêu tốn bao nhiêu **Prompt Tokens** hay **Completion Tokens** để tính tiền và rate-limit.
3. **Không xử lý được lỗi nghiệp vụ của LLM**: Khi vLLM trả về mã lỗi `400 Bad Request` với thông điệp `"Maximum context length exceeded (4096 tokens)"`, Nginx coi đó là lỗi của client và trả thẳng về cho user. Nginx không thể tự động nhận diện để chuyển câu hỏi sang một model khác có context dài hơn (như 32k tokens).

---

## 2. Cạm Bẫy Khi "Tự Viết Gateway Bằng FastAPI"

Nhiều đội ngũ kỹ sư bắt đầu bằng việc tự viết một ứng dụng Python FastAPI để làm proxy đứng trước vLLM. Sau vài tuần, họ rơi vào "cơn ác mộng bảo trì" vì phải tự giải quyết các bài toán phức tạp:

- **Quản lý Server-Sent Events (SSE Streaming)**: Chuyển tiếp (proxy) từng chunk dữ liệu chữ chạy theo thời gian thực mà không bị đệm (buffering) trong bộ nhớ, không làm tăng độ trễ TTFT và tự động hủy sinh chữ trên GPU khi người dùng ngắt kết nối (`Disconnect handling`).
- **Cơ chế Fallback & Backoff Retry**: Tự viết vòng lặp bắt ngoại lệ, tự quản lý danh sách backend khỏe/yếu (Circuit Breaker).
- **Chuẩn hóa API Schema**: Phải tự map các tham số giữa các chuẩn API khác nhau của vLLM, Ollama, HuggingFace, Anthropic...

---

## 3. Giá Trị Thực Chiến Vượt Trội Của LiteLLM Proxy

LiteLLM Proxy giải quyết trọn gói toàn bộ các bài toán trên chỉ với một file cấu hình `config.yaml`:

```
               Ứng dụng Client (Web UI, Mobile, LangChain, AutoGen)
                                      │
                                      ▼ (Gọi chuẩn OpenAI API: /v1/chat/completions)
                     ┌───────────────────────────────────┐
                     │       LiteLLM Proxy Gateway       │
                     │  - OpenAI API Standardization     │
                     │  - Zero-Latency SSE Streaming     │
                     │  - Smart Routing & Fallback       │
                     │  - Rate Limit (RPM, TPM)          │
                     │  - Native Prometheus Scrape (/metrics)│
                     └────────────────┬──────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
   ┌───────────────────────────┐             ┌───────────────────────────┐
   │ vLLM Engine (Primary GPU) │             │  Ollama Engine (Fallback) │
   └───────────────────────────┘             └───────────────────────────┘
```

### 4 Tính Năng Sát Sườn Được Sử Dụng Trong Đồ Án Này:
1. **Thống nhất chuẩn giao tiếp (Universal OpenAI Format)**: Dù backend phía sau là vLLM (OpenAI-like) hay Ollama (Ollama native format), LiteLLM tự động chuyển đổi cấu trúc JSON 2 chiều. Toàn bộ client bên ngoài chỉ cần dùng thư viện `openai-python` để gọi.
2. **High Availability Fallback tự động**: Cấu hình cực kỳ ngắn gọn trong `config.yaml`:
   ```yaml
   router_settings:
     fallbacks:
       - default-llm: ["ollama-fallback"]
   ```
   Nếu vLLM chết hoặc bị nghẽn, request tự trôi sang Ollama ngay lập tức.
3. **Tích hợp Prometheus Metrics tự nhiên**: Chỉ cần bật cờ `success_callback: ["prometheus"]`, LiteLLM lập tức mở cổng `/metrics` xuất đầy đủ số liệu latency, số request theo model mà không cần viết thêm dòng code nào.
4. **Quản lý khóa truy cập (API Keys) & Phân quyền**: Dễ dàng tạo các token riêng biệt cho từng phòng ban và đặt hạn mức ngân sách chi tiêu hàng ngày.
