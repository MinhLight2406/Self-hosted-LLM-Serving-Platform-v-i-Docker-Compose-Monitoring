# 03. Công Thức Tính Toán Chính Xác Dung Lượng VRAM Cho LLM Serving

Một trong những sai lầm phổ biến nhất của kỹ sư khi mới triển khai LLM là: **"Model 8B dùng 4-bit chỉ nặng 4.5 GB, vậy card GPU 8GB là đủ để chạy production."**
Thực tế khi đưa vào chạy, hệ thống lập tức sập với lỗi `CUDA Out of Memory`. Bài học này cung cấp công thức toán học chuẩn xác để tính dung lượng VRAM thực tế trước khi cấu hình.

---

## 1. Tổng Dung Lượng VRAM Thực Tế (Total VRAM Budget)

Tổng dung lượng VRAM yêu cầu của một LLM serving engine được cấu thành từ 4 thành phần riêng biệt:

$$\text{VRAM}_{\text{Total}} = \text{VRAM}_{\text{Weights}} + \text{VRAM}_{\text{KV\_Cache}} + \text{VRAM}_{\text{Activation}} + \text{VRAM}_{\text{CUDA\_Runtime}}$$

---

## 2. Chi Tiết Từng Thành Phần

### Thành phần 1: Bộ Nhớ Trọng Số Mô Hình ($\text{VRAM}_{\text{Weights}}$)
Là dung lượng để nạp toàn bộ tham số của mô hình từ ổ cứng lên VRAM:

$$\text{VRAM}_{\text{Weights}} = P \times \frac{B_{\text{weight}}}{8} \times 1.05 \quad (\text{Bytes})$$

- $P$: Tổng số lượng tham số (Parameters), ví dụ 8 tỷ tham số cho Llama-3-8B ($8 \times 10^9$).
- $B_{\text{weight}}$: Số bit biểu diễn cho mỗi trọng số:
  - **FP16 / BF16**: $16\text{ bits} = 2\text{ bytes}$
  - **INT8 / FP8**: $8\text{ bits} = 1\text{ byte}$
  - **INT4 (AWQ / GPTQ / GGUF Q4_K_M)**: $4\text{ bits} = 0.5\text{ byte}$
- $1.05$: Hệ số dự phòng khoảng 5% cho ma trận trọng số phụ (embedding table, normalization layers, quantization scales).

*Ví dụ nhanh*: Mô hình 8B ở FP16 tốn: $8 \times 2 \times 1.05 \approx 16.8\text{ GB}$. Ở 4-bit AWQ tốn: $8 \times 0.5 \times 1.05 \approx 4.2\text{ GB}$.

---

### Thành phần 2: Bộ Nhớ KV Cache ($\text{VRAM}_{\text{KV\_Cache}}$)
Đây là phần bộ nhớ co giãn linh hoạt theo số lượng người dùng đồng thời ($B$) và chiều dài văn bản ($L$).
Đối với kiến trúc **GQA (Grouped-Query Attention)** phổ biến hiện nay (Llama-3, Qwen-2.5, Mistral):

$$\text{KV Cache Size per Token} = 2 \times n_{\text{layers}} \times n_{\text{kv\_heads}} \times d_{\text{head}} \times B_{\text{element}}$$

Trong đó:
- $2$: Đại diện cho 2 ma trận ($K$ và $V$).
- $n_{\text{layers}}$: Số lớp Transformer.
- $n_{\text{kv\_heads}}$: Số lượng head dành cho Key/Value (trong GQA, con số này nhỏ hơn số query heads rất nhiều, thường là 8).
- $d_{\text{head}}$: Chiều của mỗi head ($d_{\text{head}} = \frac{d_{\text{model}}}{n_{\text{query\_heads}}}$, thường là 128).
- $B_{\text{element}}$: Kích thước dữ liệu của KV cache (nếu lưu FP16 thì $B_{\text{element}} = 2\text{ bytes}$, nếu bật FP8 KV cache thì $B_{\text{element}} = 1\text{ byte}$).

Tổng dung lượng KV Cache cần thiết cho $B$ request đồng thời với độ dài context trung bình $L$:

$$\text{VRAM}_{\text{KV\_Cache}} = B \times L \times (\text{KV Cache Size per Token})$$

---

### Thành phần 3: Bộ Nhớ Tạm Tính Toán (Activation Memory)
Trong giai đoạn Prefill, khi xử lý một prompt dài, GPU cần tạo ra các ma trận trung gian (intermediate attention maps, residual connections). Kích thước này phụ thuộc vào kích thước prompt đầu vào tối đa và thường dao động từ **0.5 GB đến 2.0 GB**.

---

### Thành phần 4: VRAM Hệ Thống & CUDA Context ($\text{VRAM}_{\text{CUDA\_Runtime}}$)
Khi PyTorch và CUDA driver khởi tạo một process trên GPU:
- CUDA context mặc định chiếm khoảng **0.4 GB - 0.8 GB**.
- NCCL communicator (nếu chạy multi-GPU) chiếm thêm khoảng **0.3 GB**.
- Tổng mức tiêu hao nền tối thiểu: $\approx 1.0\text{ GB}$.

---

## 3. Bài Toán Thực Tế: Phục Vụ Qwen2.5-7B-Instruct

Hãy tính toán chính xác để biết card **NVIDIA RTX 3060 12GB** hoặc **RTX 4090 24GB** chịu được bao nhiêu tải:

**Thông số kỹ thuật của Qwen2.5-7B**:
- Số tham số ($P$): $7.61 \times 10^9$
- Số layers ($n_{\text{layers}}$): $28$
- Số KV heads ($n_{\text{kv\_heads}}$): $4$
- Head dimension ($d_{\text{head}}$): $128$
- Định dạng weights: **4-bit AWQ** ($0.5\text{ byte/param}$)
- Định dạng KV Cache: **FP16** ($2\text{ bytes/element}$)

### Bước 1: Tính VRAM Weights
$$\text{VRAM}_{\text{Weights}} = 7.61 \times 0.5 \times 1.05 \approx 4.0\text{ GB}$$

### Bước 2: Tính KV Cache per Token
$$\text{KV per token} = 2 \times 28 \times 4 \times 128 \times 2 = 57,344\text{ bytes} \approx 0.0547\text{ MB/token}$$

### Bước 3: Tính toán khả năng chịu tải trên GPU 16GB (với Context length = 4096 tokens)
- Dung lượng VRAM vật lý: $16.0\text{ GB}$
- vLLM cấu hình cờ: `--gpu-memory-utilization 0.90` $\rightarrow$ vLLM chiếm: $16 \times 0.9 = 14.4\text{ GB}$.
- Trừ đi Weights: $14.4 - 4.0 = 10.4\text{ GB}$ còn trống.
- Trừ đi CUDA Runtime & Activations: $10.4 - 1.5 = 8.9\text{ GB}$ dành riêng cho KV Cache.
- Mỗi request dài tối đa $4096$ tokens tiêu hao:
  $$\text{VRAM per full request} = 4096 \times 0.0547\text{ MB} \approx 224\text{ MB} = 0.219\text{ GB}$$
- **Số lượng request đồng thời tối đa không bị tràn VRAM**:
  $$B_{\text{max}} = \frac{8.9\text{ GB}}{0.219\text{ GB}} \approx 40\text{ concurrent requests}$$

> **Ý nghĩa thực chiến**: 
> Nhờ công thức này, bạn có thể giải thích chính xác với sếp hoặc khách hàng: "Với card 16GB, hệ thống có thể đáp ứng 40 người chat đồng thời ở độ dài 4000 chữ. Nếu muốn phục vụ 100 người, ta phải giảm `--max-model-len` xuống 2048 hoặc kích hoạt FP8 KV Cache (`--kv-cache-dtype fp8`)."
