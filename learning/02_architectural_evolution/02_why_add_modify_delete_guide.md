# 02. Cẩm Nang "Tại Sao Phải Thêm - Xóa - Sửa" Từng Dòng Cấu Hình (Diff Reasoning)

Khi xem một file cấu hình hạ tầng (`docker-compose.yml`, `config.yaml`, `prometheus.yml`), kỹ sư giỏi không học vẹt cú pháp mà nhìn thấy **nguyên nhân đằng sau từng dòng code**.

Dưới đây là bảng đối chiếu thực tế (Code Diff) và phân tích chuyên sâu lý do tại sao phải **Thêm, Xóa, Sửa** các cờ cấu hình quan trọng nhất trong đồ án này.

---

## 1. Đối Với Cấu Hình vLLM Engine Trong `docker-compose.yml`

```diff
  vllm-engine:
    image: vllm/vllm-openai:v0.6.3.post1
+   ipc: host
    ports:
-     - "8000:8000"
+     - "127.0.0.1:8000:8000"
    command: >
      --model Qwen/Qwen2.5-7B-Instruct-AWQ
+     --gpu-memory-utilization 0.90
+     --max-model-len 4096
-     --enforce-eager
+     --trust-remote-code
+   healthcheck:
+     test: ["CMD-SHELL", "curl -f http://localhost:8000/v1/models || exit 1"]
+     interval: 30s
+     start_period: 60s
```

### 🔍 Giải Thích Từng Điểm Thay Đổi:

### 1.1. Thêm `ipc: host` (CỰC KỲ QUAN TRỌNG)
- **Hiện tượng nếu thiếu**: Khi có nhiều request đồng thời, container lập tức crash với lỗi `Bus error (core dumped)` hoặc NCCL communication deadlock.
- **Lý do**: Mặc định Docker chỉ cấp 64MB cho `/dev/shm`. PyTorch cần hàng gigabytes bộ nhớ dùng chung để trao đổi dữ liệu giữa CPU workers và GPU. Thêm `ipc: host` gỡ bỏ giới hạn này bằng cách dùng chung bộ nhớ chia sẻ của máy chủ.

### 1.2. Thêm `--gpu-memory-utilization 0.90` (Thay vì để 1.0 hoặc mặc định)
- **Tại sao không để 1.0 (100%)?**: vLLM sẽ chiếm sạch toàn bộ VRAM để tạo sẵn các block KV Cache. Khi một prompt dài được gửi vào, giai đoạn Prefill cần một lượng VRAM tạm thời cho Activation Tensors. Nếu không còn lấy 1 MB VRAM nào trống, GPU sẽ crash ngay lập tức vì `CUDA Out of Memory`.
- **Tại sao 0.90 là con số vàng?**: Dành 90% cho Trọng số mô hình + KV Cache, và để dành đúng 10% VRAM dự phòng cho Activation Tensors và CUDA runtime context.

### 1.3. Thêm `--max-model-len 4096` (Thay vì để nguyên 32,768 hoặc 128,000 tokens mặc định của model)
- **Lý do**: Các model hiện đại như Qwen2.5 hay Llama-3.1 hỗ trợ context window lên tới 32k hoặc 128k tokens. Nếu bạn không giới hạn `--max-model-len`, vLLM sẽ tính toán dung lượng block KV Cache dựa trên chiều dài tối đa này. Kết quả: VRAM bị chia sẻ cho context quá lớn, khiến **số lượng người dùng đồng thời (Concurrency) bị tụt từ 40 người xuống chỉ còn 1 hoặc 2 người!** Giới hạn 4096 tokens là điểm cân bằng hoàn hảo cho nhu cầu chat nghiệp vụ.

### 1.4. Xóa cờ `--enforce-eager` (Chuyển sang CUDA Graphs)
- **Lý do**: `--enforce-eager` tắt cơ chế bắt đồ thị tính toán (CUDA Graphs) của PyTorch, khiến mỗi bước sinh token đều phải gọi kernel qua CPU driver. Xóa cờ này đi để vLLM kích hoạt **CUDA Graph Capture**, giúp giảm thiểu tối đa độ trễ CPU-overhead và tăng tốc độ sinh token (TPOT) từ 15% đến 25% trong Decode Phase!

### 1.5. Thêm `healthcheck` với `start_period: 60s`
- **Lý do**: Model LLM nặng hàng gigabytes cần từ 30 đến 60 giây để nạp từ đĩa cứng vào VRAM GPU. Nếu không có `healthcheck` và `start_period`, container LiteLLM Gateway sẽ khởi động cùng lúc, gửi request kiểm tra và thấy cổng 8000 chưa sẵn sàng $\rightarrow$ Gateway lập tức crash và báo lỗi kết nối.

---

## 2. Đối Với Cấu Hình LiteLLM Gateway Trong `config/litellm/config.yaml`

```diff
  model_list:
    - model_name: default-llm
      litellm_params:
        model: openai/Qwen/Qwen2.5-7B-Instruct-AWQ
        api_base: http://vllm-engine:8000/v1
+       rpm: 1000
+       timeout: 120

+ router_settings:
+   routing_strategy: "least-busy"
+   fallbacks:
+     - default-llm: ["ollama-fallback"]
+   num_retries: 2
+   cooldown_time: 30

+ litellm_settings:
+   success_callback: ["prometheus"]
+   failure_callback: ["prometheus"]
```

### 🔍 Giải Thích Từng Điểm Thay Đổi:

### 2.1. Thêm `fallbacks: - default-llm: ["ollama-fallback"]`
- **Lý do**: Đây là cơ chế **Graceful Degradation (Suy giảm mượt mà)** chuẩn Enterprise. Khi GPU vLLM bị quá tải hoặc gặp sự cố khởi động lại, Gateway không trả về lỗi `500 Internal Server Error` cho người dùng mà tự động định tuyến ngầm câu hỏi đó sang container Ollama (dù tốc độ có thể chậm hơn một chút nhưng hệ thống không bao giờ bị gián đoạn).

### 2.2. Thêm `success_callback: ["prometheus"]`
- **Lý do**: Mặc định LiteLLM chỉ in log ra màn hình console. Thêm callback này để LiteLLM tự động sinh ra các metrics chuẩn Prometheus tại endpoint `/metrics` (đếm số lượt request thành công, số lượt bị từ chối do rate limit, thời gian phản hồi của từng model).

---

## 3. Đối Với Cấu Hình Prometheus Trong `prometheus.yml`

```diff
  global:
-   scrape_interval: 15s
+   scrape_interval: 5s
-   scrape_timeout: 10s
+   scrape_timeout: 4s
```

### 🔍 Giải Thích:
- **Tại sao phải sửa `scrape_interval` từ 15s xuống 5s?**:
  Trong giám sát web thông thường, 15 giây là đủ. Nhưng một request LLM thường chỉ diễn ra trong vòng 2 đến 4 giây. Nếu bạn cào dữ liệu 15s/lần, bạn sẽ **bỏ lỡ hoàn toàn các xung đột biến tải (Latency Spikes)** và sự dao động đột ngột của hàng đợi Queue! Thu thập mỗi 5s giúp biểu đồ Grafana bắt trọn từng biến động của GPU.
- **Tại sao phải sửa `scrape_timeout: 4s`?**:
  Quy tắc vàng trong Prometheus: `scrape_timeout` luôn phải nhỏ hơn `scrape_interval` để tránh việc đợt cào dữ liệu mới bắt đầu khi đợt cũ vẫn chưa kết thúc, gây tràn luồng thu thập.
