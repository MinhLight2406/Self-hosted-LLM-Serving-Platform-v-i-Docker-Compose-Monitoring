# 05. Bốn Chỉ Số Vàng Đo Lường Hiệu Năng LLM Serving (Golden Metrics)

Trong các hệ thống web truyền thống, ta thường giám sát theo tiêu chuẩn Google SRE (Latency, Traffic, Errors, Saturation). Tuy nhiên, đối với hệ thống **LLM Serving**, việc chỉ đo "Request Latency chung chung" là hoàn toàn vô nghĩa, vì một câu trả lời 1000 tokens chắc chắn phải mất nhiều thời gian hơn câu trả lời 10 tokens.

Dưới đây là **4 Chỉ Số Vàng** chuyên biệt của AI Engineering mà bạn bắt buộc phải theo dõi trên Dashboard Grafana.

---

## 1. Time To First Token (TTFT - Thời Gian Đến Token Đầu Tiên)

### Định Nghĩa:
Khoảng thời gian tính từ thời điểm Client bấm gửi request cho đến khi Client nhận được token sinh ra đầu tiên qua giao thức Streaming (SSE):

$$\text{TTFT} = T_{\text{Network}} + T_{\text{Queue}} + T_{\text{Prefill}}$$

### Ý Nghĩa Trải Nghiệm:
- Quyết định cảm giác người dùng: "Hệ thống phản hồi tức thì hay bị đơ lag".
- Đo lường trực tiếp tốc độ của **Prefill Phase** và thời gian request phải xếp hàng chờ trong Queue.

### Tiêu Chuẩn SLA Khuyến Nghị:
- **Interactive Chatbot (Trò chuyện trực tiếp)**: $\le 300\text{ ms} - 800\text{ ms}$.
- **RAG / Tài liệu dài (Context > 4000 tokens)**: $\le 1500\text{ ms} - 2500\text{ ms}$.
- **Báo động đỏ**: Nếu TTFT $> 5\text{ giây}$, chứng tỏ Queue đang bị nghẽn nghiêm trọng hoặc GPU đang quá tải Prefill.

---

## 2. Time Per Output Token (TPOT) / Inter-Token Latency (ITL)

### Định Nghĩa:
Khoảng thời gian trung bình giữa 2 token liên tiếp được sinh ra trong quá trình Streaming:

$$\text{TPOT} = \frac{T_{\text{Tổng thời gian Decode}}}{\text{Tổng số Token sinh ra}} \quad (\text{ms/token})$$

Tốc độ sinh token tương ứng tính theo giây:
$$\text{Tokens/s per user} = \frac{1000}{\text{TPOT (ms)}}$$

### Ý Nghĩa Trải Nghiệm:
- Tốc độ đọc tự nhiên của con người trung bình từ **5 đến 8 words/giây** ($\approx 7 - 12\text{ tokens/giây}$, tức $\text{TPOT} \approx 80 - 140\text{ ms/token}$).
- Nếu $\text{TPOT} \le 40\text{ ms/token}$ ($25\text{ tokens/s}$), người dùng cảm thấy chữ tuôn ra cực nhanh và mượt mà.
- Nếu TPOT dao động thất thường (Jitter), người dùng sẽ thấy chữ bị giật cục từng đợt.

---

## 3. Tổng Thông Lượng Sinh Token (System Generation Throughput)

### Định Nghĩa:
Tổng số token mà toàn bộ hệ thống GPU sinh ra trong một giây cho tất cả người dùng đồng thời:

$$\text{Throughput} = \frac{\sum_{i=1}^{K} \text{Generated Tokens}_i}{\Delta t} \quad (\text{tokens/second})$$

### Ý Nghĩa Kinh Tế:
- Là thước đo **hiệu quả đầu tư phần cứng (ROI)**.
- Khi tải tăng (tăng concurrency), TTFT có thể tăng nhẹ, nhưng tổng Throughput phải tăng lên tiệm cận mức bão hòa của GPU. Nếu concurrency tăng mà Throughput không tăng thì hệ thống đã chạm trần băng thông VRAM.

---

## 4. Tỷ Lệ Chiếm Dụng KV Cache (GPU Cache Usage Factor)

### Định Nghĩa:
Tỷ lệ phần trăm các khối bộ nhớ KV Cache trên GPU đã được cấp phát:

$$\text{Cache Usage (\%)} = \text{vllm:gpu\_cache\_usage\_factor} \times 100$$

### Chỉ Số Cảnh Báo Sớm Nguy Hiểm Nhất:
- **$< 70\%$ (Màu xanh)**: Hệ thống khỏe mạnh, còn dư dả VRAM để nhận thêm request mới.
- **$70\% - 85\%$ (Màu vàng)**: Hệ thống bắt đầu tiệm cận mức tải cao.
- **$> 90\%$ (Màu đỏ)**: **NGUY HIỂM!** vLLM sẽ không thể cấp thêm block KV Cache mới. Các request mới đến sẽ bị đẩy vào hàng đợi chờ (`num_requests_waiting` tăng vọt). Nếu tình trạng kéo dài, vLLM buộc phải **Preempt** (tạm hoãn request đang chạy, đẩy KV Cache sang RAM máy chủ) khiến TPOT tăng đột biến!

---

## 5. Bảng Tổng Hợp Metric Trong Prometheus & PromQL Query

| Chỉ số | Prometheus Metric Name | Câu truy vấn PromQL chuẩn |
| :--- | :--- | :--- |
| **TTFT (p95)** | `vllm:time_to_first_token_seconds_bucket` | `histogram_quantile(0.95, sum(rate(vllm:time_to_first_token_seconds_bucket[1m])) by (le))` |
| **TPOT (p95)** | `vllm:time_per_output_token_seconds_bucket`| `histogram_quantile(0.95, sum(rate(vllm:time_per_output_token_seconds_bucket[1m])) by (le))` |
| **Throughput** | `vllm:generation_tokens_total` | `sum(rate(vllm:generation_tokens_total[1m]))` |
| **KV Cache %** | `vllm:gpu_cache_usage_factor` | `vllm:gpu_cache_usage_factor * 100` |
| **Hàng đợi** | `vllm:num_requests_waiting` | `vllm:num_requests_waiting` |
| **GPU VRAM** | `DCGM_FI_DEV_FB_USED` | `DCGM_FI_DEV_FB_USED / 1024` |
