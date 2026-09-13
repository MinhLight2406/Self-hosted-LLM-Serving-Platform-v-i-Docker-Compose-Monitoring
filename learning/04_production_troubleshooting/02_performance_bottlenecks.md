# 02. Chẩn Đoán & Khắc Phục Nghẽn Cổ Chai Hiệu Năng (Performance Bottlenecks)

Khi người dùng phàn nàn: **"Hệ thống hôm nay chậm quá!"**, một kỹ sư MLOps không thể trả lời chung chung. Bạn cần mở Grafana và xác định chính xác nút thắt cổ chai đang nằm ở đâu.

Dưới đây là 3 kịch bản nghẽn hiệu năng phổ biến nhất và giải pháp kỹ thuật.

---

## 🛑 Kịch Bản 1: TTFT Rất Cao (Chờ Mãi Không Thấy Chữ Đầu Tiên), Nhưng Chữ Đã Ra Thì Chạy Rất Nhanh

### 1. Triệu Chứng Trên Grafana:
- Panel **Time To First Token (TTFT)** vọt lên $3 - 5\text{ giây}$.
- Panel **Time Per Output Token (TPOT)** vẫn mượt mà ở mức $20 - 30\text{ ms/token}$.
- Panel **Waiting Requests in Queue** xuất hiện các số dương ($> 5$ requests đang xếp hàng).

### 2. Nguyên Nhân Kỹ Thuật:
- Giai đoạn **Prefill** của các request trước đó đang chiếm dụng toàn bộ năng lực tính toán của GPU, khiến các request mới đến phải đứng chờ ngoài cửa phòng chờ (Queue).
- Hoặc một người dùng vừa gửi vào một prompt tài liệu cực dài (ví dụ 10,000 tokens), khiến GPU mất cả giây chỉ để tính toán ma trận Attention đầu vào.

### 3. Giải Pháp Triệt Để:
1. **Kích hoạt Chunked Prefill**:
   Cho phép vLLM chia nhỏ các prompt dài thành từng mẩu nhỏ (chunks) để xử lý xen kẽ với các bước Decode của những request khác, không để 1 prompt dài làm nghẽn toàn bộ hệ thống:
   ```bash
   # Thêm vào command vLLM:
   --enable-chunked-prefill true
   --max-num-batched-tokens 512
   ```
2. **Kích hoạt Tự Động Lưu Cache Tiền Tố (Automatic Prefix Caching)**:
   Nếu nhiều người dùng cùng dùng chung một System Prompt dài (ví dụ bảng hướng dẫn nhân viên 2000 từ), bật cờ này để vLLM lưu lại KV Cache của prompt đó:
   ```bash
   --enable-prefix-caching
   ```
   TTFT của những câu hỏi tiếp theo sẽ giảm từ $2000\text{ ms}$ xuống còn **dưới $50\text{ ms}$!**

---

## 🛑 Kịch Bản 2: Chữ Sinh Ra Bị Giật Cục, Tốc Độ Đọc Bị Tụt (High TPOT / Inter-Token Latency)

### 1. Triệu Chứng Trên Grafana:
- Panel **TPOT** tăng từ $25\text{ ms/token}$ lên $90 - 150\text{ ms/token}$.
- Panel **GPU Temperature** trên dashboard DCGM vượt quá **$83^\circ\text{C} - 86^\circ\text{C}$**.
- Panel **SM Clock** bị tụt đột ngột từ $2500\text{ MHz}$ xuống còn $1200\text{ MHz}$.

### 2. Nguyên Nhân Kỹ Thuật:
- **Hiện tượng tụt xung do quá nhiệt (Thermal Throttling)**: Card GPU chạy hết công suất liên tục, quạt tản nhiệt của máy chủ không kịp thoát nhiệt. Chip đồ họa tự động hạ xung nhịp để chống cháy phần cứng, làm tốc độ tính toán giảm một nửa!
- Hoặc số lượng request đồng thời quá cao khiến băng thông bộ nhớ VRAM bị quá tải (Memory Bandwidth Saturation).

### 3. Giải Pháp:
- Kiểm tra hệ thống tản nhiệt và quạt thông gió của máy chủ.
- Thiết lập ngưỡng giới hạn tốc độ (Rate Limiting) trên LiteLLM Gateway (`rpm: 500`) để không dồn quá nhiều request vượt quá khả năng xử lý của phần cứng.

---

## 🛑 Kịch Bản 3: Hiện Tượng Bị Ngắt Quãng Bất Thường (Preemption Spikes)

### 1. Triệu Chứng:
- Đột nhiên một số request đang streaming thì bị dừng lại vài giây rồi mới chạy tiếp, hoặc xuất hiện lỗi timeout.
- Metric Prometheus `vllm:num_preemptions_total` tăng lên.

### 2. Nguyên Nhân:
- **VRAM KV Cache bị bão hòa 100%**: vLLM không còn chỗ chứa token mới cho request hiện tại, buộc phải tạm dừng (Preempt) một request khác, đẩy KV Cache của nó ra RAM máy tính và sau đó nạp lại vào GPU khi có chỗ trống.

### 3. Giải Pháp:
- Giảm `--gpu-memory-utilization` về mức hợp lý hoặc giảm `--max-model-len`.
- Bật nén `--kv-cache-dtype fp8`.
- Bổ sung thêm card GPU chạy Data Parallelism để chia tải.
