# 01. Cơ Chế Suy Luận LLM: Prefill Phase vs Decode Phase & Memory-Bound Nature

Để vận hành và tối ưu hóa hệ thống LLM serving một cách chuyên nghiệp, kỹ sư không thể coi LLM như một "hộp đen" nhận text và trả ra text. Chúng ta phải hiểu sâu bản chất toán học và vật lý của quá trình suy luận (Inference).

---

## 1. Bản Chất Của Quá Trình Tự Hồi Quy (Autoregressive Generation)

Mô hình ngôn ngữ lớn bản chất là một mạng nơ-ron Transformer Decoder-only. Nhiệm vụ của nó là dự đoán phân phối xác suất của token tiếp theo dựa trên chuỗi các token đã có trong quá khứ:

$$P(x_{t} \mid x_{1}, x_{2}, \dots, x_{t-1}) = \text{Softmax}\left(\frac{Q K^T}{\sqrt{d_k}}\right) V$$

Quá trình này diễn ra **lặp đi lặp lại từng token một**:
1. Nhận chuỗi token đầu vào.
2. Tính toán ma trận Attention qua tất cả các lớp (Layers).
3. Đưa ra 1 token mới (token $x_t$).
4. Ghép token $x_t$ vào cuối chuỗi và lặp lại bước 1 cho token $x_{t+1}$.

---

## 2. Hai Giai Đoạn Tách Biệt: Prefill Phase vs Decode Phase

Quá trình suy luận thực tế luôn được chia thành 2 giai đoạn có đặc tính phần cứng hoàn toàn đối lập:

```
User Prompt: "Giải thích kiến trúc Transformer" (N tokens)
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│ 1. PREFILL PHASE (Prompt Processing)                    │
│ - Xử lý toàn bộ N tokens đầu vào song song một lúc      │
│ - Phép toán: Matrix-Matrix Multiplication (GEMM)         │
│ - Tính chất: COMPUTE-BOUND (Nghẽn tại số nhân tính toán) │
│ - Quyết định chỉ số: TTFT (Time To First Token)         │
└─────────────────────────────────────────────────────────┘
      │
      ▼ (Sinh token đầu tiên và lưu KV Cache)
┌─────────────────────────────────────────────────────────┐
│ 2. DECODE PHASE (Token-by-token Generation)             │
│ - Sinh từng token mới một (x_1, x_2, ... x_M)           │
│ - Phép toán: Matrix-Vector Multiplication (GEMV)         │
│ - Tính chất: MEMORY BANDWIDTH BOUND (Nghẽn băng thông)   │
│ - Quyết định chỉ số: TPOT / ITL (Inter-Token Latency)   │
└─────────────────────────────────────────────────────────┘
```

### So Sánh Kỹ Thuật Giữa Hai Giai Đoạn:

| Tiêu chí | Prefill Phase (Prompt) | Decode Phase (Generation) |
| :--- | :--- | :--- |
| **Đầu vào** | Toàn bộ prompt của người dùng ($N$ tokens) | Chỉ 1 token duy nhất vừa sinh ra ($1$ token) |
| **Dạng toán học** | GEMM (General Matrix Multiply) | GEMV (General Matrix-Vector Multiply) |
| **Nút thắt phần cứng** | **Compute-Bound** (Nghẽn TFLOPS của GPU) | **Memory Bandwidth-Bound** (Nghẽn GB/s VRAM) |
| **Cường độ tính toán ($I$)** | Rất cao (Tận dụng tối đa Tensor Cores) | Cực kỳ thấp ($I \approx 1\text{ FLOP / Byte}$) |
| **Ảnh hưởng trải nghiệm** | **TTFT** (Thời gian người dùng phải chờ token đầu) | **TPOT** (Tốc độ chữ chạy mượt hay giật lag) |

---

## 3. Tại Sao Decode Phase Lại Bị "Nghẽn Băng Thông Bộ Nhớ" (Memory Bandwidth Bound)?

Đây là kiến thức quan trọng nhất giải thích tại sao GPU dù mạnh đến đâu thì tốc độ sinh token đơn luồng (single batch) vẫn có giới hạn trần.

### Mô hình Roofline & Cường độ tính toán (Arithmetic Intensity)
Cường độ tính toán $I$ được định nghĩa bằng số phép tính dấu phẩy động (FLOPs) thực hiện được trên mỗi byte dữ liệu đọc từ bộ nhớ VRAM vào nhân tính toán:

$$I = \frac{\text{Tổng số FLOPs}}{\text{Tổng số Bytes đọc/ghi VRAM}} \quad (\text{FLOPs/Byte})$$

Giả sử ta phục vụ mô hình **Llama-3-8B** ở định dạng **FP16** (mỗi tham số chiếm 2 bytes $\rightarrow$ kích thước weights khoảng 16 GB):
1. Để sinh ra **ĐÚNG 1 TOKEN** trong Decode Phase, GPU bắt buộc phải tải (load) **toàn bộ 16 GB trọng số** của mô hình từ VRAM (HBM/GDDR) vào trong chip xử lý (SRAM / Register).
2. Số phép tính để nhân 1 vector token với ma trận trọng số là:
   $$2 \times 8 \times 10^9 \approx 16 \text{ GFLOPs}$$
3. Cường độ tính toán thực tế:
   $$I = \frac{16 \times 10^9 \text{ FLOPs}}{16 \times 10^9 \text{ Bytes}} = 1 \text{ FLOP / Byte}$$

### Đối chiếu với thông số GPU thực tế:
- **NVIDIA RTX 4090**:
  - Băng thông bộ nhớ (Memory Bandwidth): $\approx 1008 \text{ GB/s}$
  - Năng lực tính toán (FP16 Tensor Core): $\approx 165 \text{ TFLOPS} = 165,000 \text{ GFLOPs/s}$
- Thời gian tối thiểu chỉ để đọc 16 GB weights qua bus bộ nhớ 1008 GB/s:
  $$t_{\text{load}} = \frac{16 \text{ GB}}{1008 \text{ GB/s}} \approx 0.0158 \text{ giây} = 15.8 \text{ ms}$$
- Tốc độ sinh token lý thuyết tối đa khi chạy đơn luồng (Batch size = 1):
  $$\text{Tokens/s} = \frac{1}{0.0158 \text{ s}} \approx 63 \text{ tokens/s}$$

> **Kết luận sống còn**: Trong giai đoạn Decode với batch size nhỏ, **hơn 95% nhân tính toán (Tensor Cores) của GPU đang phải đứng chờ dữ liệu được chuyển từ VRAM vào**. GPU không hề bị quá tải tính toán, mà bị "đói dữ liệu" do giới hạn vật lý của băng thông bộ nhớ!

---

## 4. Giải Pháp Kiến Trúc: Tận Dụng Batching Trong LLM Serving

Để khắc phục hiện tượng lãng phí năng lực tính toán trong Decode phase, giải pháp là **Batching** (gộp nhiều request chạy đồng thời):
- Khi gộp $B$ requests cùng lúc, ta vẫn chỉ cần tải 16 GB weights đó vào GPU một lần.
- Nhưng ta thực hiện phép nhân ma trận với $B$ vectors thay vì 1 vector.
- Phép toán chuyển từ Matrix-Vector (GEMV) thành Matrix-Matrix (GEMM), đẩy cường độ tính toán $I$ tăng gấp $B$ lần!
- Kết quả: GPU tận dụng tối đa năng lực tính toán, tổng Throughput (tokens/giây trên toàn hệ thống) tăng vọt.

Đó chính là lý do vì sao các engine hiện đại như **vLLM** áp dụng **Continuous Batching** để tối ưu hóa triệt để tài nguyên GPU, nội dung này sẽ được phân tích sâu ở bài tiếp theo.
