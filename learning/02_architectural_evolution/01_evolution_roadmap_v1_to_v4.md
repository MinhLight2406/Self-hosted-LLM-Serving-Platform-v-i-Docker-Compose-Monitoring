# 01. Nhật Ký Tiến Hóa Kiến Trúc: Từ v1 Sơ Khai Đến v4 Production Ready

Hệ thống phục vụ LLM không được sinh ra hoàn hảo ngay từ ngày đầu tiên. Nó được xây dựng qua quá trình tiến hóa từng bước (Iterative Architecture Evolution) để giải quyết các nút thắt thực tế trong quá trình vận hành.

---

## 🏛️ Sơ Đồ Tổng Quan 4 Giai Đoạn Tiến Hóa

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌────────────────────────┐
│  Phiên bản v1   │       │  Phiên bản v2   │       │  Phiên bản v3   │       │      Phiên bản v4      │
│  (Chỉ Ollama)   │ ────► │  (Chuyển vLLM)  │ ────► │ (+ LiteLLM GW)  │ ────► │ (+ Full Observability) │
│                 │       │                 │       │                 │       │                        │
│ - Local dev     │       │ - PagedAttention│       │ - Unified Proxy │       │ - Prometheus + Grafana │
│ - Đơn giản nhất │       │ - High TP/s     │       │ - Smart Fallback│       │ - DCGM GPU Telemetry   │
│ - Nghẽn khi tải │       │ - Dễ OOM/Crash  │       │ - Rate Limiting │       │ - SLA Tracking (TTFT)  │
└─────────────────┘       └─────────────────┘       └─────────────────┘       └────────────────────────┘
```

---

## 1. Giai Đoạn v1: Ollama Đơn Độc (Local Prototyping)

### Kiến Trúc Ban Đầu:
Client gọi trực tiếp vào API của container Ollama (`http://localhost:11434`).

### Ưu Điểm:
- Cực kỳ nhanh gọn: Chỉ cần 1 file `docker-compose.yml` với 1 service duy nhất.
- Hỗ trợ định dạng GGUF nén gọn, chạy được trên cả CPU lẫn GPU phổ thông.
- Kỹ sư kiểm thử prompt và logic ứng dụng rất nhanh.

### Nút Thắt Dẫn Đến Sự Sụp Đổ:
- **Nghẽn thông lượng khi có nhiều người dùng**: Ollama dùng cơ chế suy luận tuần tự (hoặc batching rất hạn chế). Khi có 5-10 người dùng gọi đồng thời, request bị xếp hàng chờ, thời gian chờ sinh chữ kéo dài hàng chục giây.
- **Không có PagedAttention chuẩn**: VRAM bị phân mảnh nhanh chóng khi phục vụ các đoạn chat dài.

---

## 2. Giai Đoạn v2: Thay Thế Bằng vLLM Engine (High-Throughput Production)

### Thay Đổi Kiến Trúc:
Bổ sung `vllm/vllm-openai` làm engine suy luận chính thay cho Ollama.

### Bước Nhảy Vọt Về Hiệu Năng:
- Nhờ **PagedAttention** và **Continuous Batching**, GPU có thể phục vụ đồng thời 20 - 50 requests mà tổng Throughput hệ thống tăng gấp 3x - 5x so với v1.
- Hỗ trợ chuẩn API của OpenAI (`/v1/chat/completions`), giúp frontend và các thư viện như LangChain, LlamaIndex tích hợp mà không cần sửa code.

### Vấn Đề Phát Sinh:
- **Độc canh công nghệ (Single Point of Failure)**: vLLM ngốn rất nhiều VRAM tĩnh (mặc định chiếm 90% GPU để cấp sẵn cho KV Cache). Nếu một request vượt quá dung lượng context hoặc GPU gặp sự cố, toàn bộ service vLLM bị crash, làm toàn bộ hệ thống sập hoàn toàn.
- Khách hàng bị lỗi 502 / 500 mà không có cơ chế tự động chuyển hướng sang engine dự phòng.

---

## 3. Giai Đoạn v3: Đưa Vào LiteLLM Proxy (Unified Gateway & High Availability)

### Thay Đổi Kiến Trúc:
Không bao giờ cho Client gọi trực tiếp vào vLLM hay Ollama. Đặt một tầng **API Gateway thông minh (LiteLLM Proxy)** đứng phía trước:

```
                  ┌──────────────────────┐
                  │    Client / App      │
                  └──────────┬───────────┘
                             │ Request qua cổng 4000
                             ▼
                  ┌──────────────────────┐
                  │   LiteLLM Gateway    │
                  └─────┬──────────┬─────┘
           Primary Path │          │ Fallback Path
      (Nếu vLLM khỏe)   ▼          ▼ (Khi vLLM quá tải/down)
                 ┌────────────┐  ┌────────────┐
                 │ vLLM (GPU) │  │Ollama (CPU)│
                 └────────────┘  └────────────┘
```

### Lợi Ích Cốt Lõi:
1. **High Availability (Tự Động Fallback)**: Nếu vLLM gặp lỗi OOM hoặc đang khởi động lại, LiteLLM tự động chuyển request sang Ollama làm dự phòng mà Client không hề hay biết (Zero Downtime).
2. **Quản Lý Tập Trung (Centralized Auth & Rate Limit)**: Cung cấp API Key thống nhất, thiết lập giới hạn RPM (Request per minute) cho từng người dùng, ngăn ngừa tấn công làm treo GPU.
3. **Định Danh Endpoint Thống Nhất**: Ứng dụng chỉ cần trỏ về `model: "default-llm"`, việc điều phối chạy trên model nào do Gateway quyết định qua cấu hình `config.yaml`.

---

## 4. Giai Đoạn v4: Toàn Diện Giám Sát (Full Observability Stack)

### Thay Đổi Kiến Trúc:
Bổ sung **Prometheus + Grafana + NVIDIA DCGM Exporter + cAdvisor**.

### Lý Do Bắt Buộc Phải Có Trong Môi Trường Doanh Nghiệp:
- Nếu không có monitoring, bạn hoàn toàn **mù thông tin**:
  - Không biết GPU đang dùng hết bao nhiêu % VRAM?
  - Không biết người dùng đang phải đợi bao nhiêu giây để có token đầu tiên (TTFT)?
  - Khi hệ thống chậm, không biết là do mạng, do CPU máy chủ, do hàng đợi queue của vLLM hay do card GPU quá nóng bị tụt xung (Thermal Throttling)?
- **v4 mang lại sự minh bạch tuyệt đối**: Mọi số liệu từ nhiệt độ GPU, công suất tiêu thụ (Watts), số request đang chờ trong queue, đến tốc độ sinh token (tokens/s) đều hiển thị trực quan trên dashboard với thời gian thực cập nhật từng giây.
