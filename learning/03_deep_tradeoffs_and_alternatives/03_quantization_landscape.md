# 03. Toàn Cảnh Kỹ Thuật Nén Mô Hình (Quantization Landscape): AWQ vs GPTQ vs GGUF vs FP8

Khi triển khai mô hình ngôn ngữ lớn trên hạ tầng tự host (Self-hosted), kỹ thuật **Lượng tử hóa (Quantization)** là chìa khóa để cắt giảm 50% đến 75% chi phí phần cứng mà vẫn giữ được 98-99% độ thông minh của mô hình gốc.

---

## 1. Bản Chất Của Lượng Tử Hóa (Quantization Là Gì?)

Trong mô hình gốc, các trọng số (Weights) được lưu dưới dạng số thực dấu phẩy động 16-bit (**FP16** hoặc **BF16** - mỗi tham số chiếm 2 bytes).
- Model 8 tỷ tham số cần: $8 \times 2 = 16\text{ GB}$ VRAM.
- Model 70 tỷ tham số cần: $70 \times 2 = 140\text{ GB}$ VRAM.

**Lượng tử hóa** là kỹ thuật ánh xạ dải giá trị số thực FP16 sang các định dạng số nguyên có độ dài bit nhỏ hơn (INT8, INT4, hoặc FP8):
- **4-bit (AWQ / GPTQ / GGUF Q4)**: Mỗi tham số chỉ còn chiếm $0.5\text{ byte}$. Model 8B giảm từ 16GB xuống còn **4.2 GB**!

---

## 2. So Sánh Chi Tiết Các Chuẩn Quantization Phổ Biến

### 1. AWQ (Activation-aware Weight Quantization) - *Khuyến nghị hàng đầu cho vLLM*
- **Nguyên lý đột phá**: AWQ nhận ra rằng trong hàng tỷ tham số của LLM, **không phải trọng số nào cũng quan trọng như nhau**. Chỉ có khoảng **1% số trọng số (Salient Weights)** quyết định độ nhạy bén của mô hình. AWQ bảo vệ nguyên vẹn 1% trọng số này và nén 99% các trọng số còn lại về 4-bit.
- **Tối ưu trên GPU**: Kernel tính toán AWQ GEMM được tối ưu trực tiếp cho nhân Tensor Core của NVIDIA (Ampere RTX 30xx, Ada RTX 40xx, Hopper H100).
- **Đánh giá**: Giữ Perplexity (độ thông minh) tốt hơn GPTQ, tốc độ giải mã (Decode) cực kỳ ấn tượng trên vLLM.

### 2. GPTQ (Generative Pre-trained Transformer Quantization)
- **Nguyên lý**: Sử dụng ma trận đạo hàm bậc 2 (Hessian matrix) để bù trừ sai số khi nén từng cột trọng số về 4-bit.
- **Đánh giá**: Là tiêu chuẩn 4-bit đời đầu. Rất phổ biến trên HuggingFace nhưng tốc độ kernel trong vLLM thường chậm hơn AWQ từ 5% đến 10%.

### 3. GGUF (Định dạng chuẩn của `llama.cpp` & Ollama)
- **Nguyên lý**: Thiết kế dạng file nhị phân nguyên khối (Single Binary File) chứa cả cấu trúc mạng nơ-ron, vocab tokenizer, metadata và trọng số nén theo nhiều cấp độ (Q4_K_M, Q5_K_M, Q8_0).
- **Thế mạnh độc tôn**: **CPU & Hybrid Memory Offloading**. Nếu máy bạn có card 8GB nhưng model nặng 10GB, GGUF cho phép nạp 7GB vào GPU và đẩy 3GB còn lại sang RAM máy tính để chạy phối hợp (vLLM không làm được điều này một cách hiệu quả).

### 4. FP8 (Floating Point 8-bit: E4M3 & E5M2) - *Tiêu chuẩn tương lai*
- **Nguyên lý**: Thay vì đổi sang số nguyên INT, FP8 vẫn giữ nguyên cấu trúc số thực dấu phẩy động (1 bit dấu, 4 bit số mũ exponent, 3 bit phần định trị mantissa).
- **Thế mạnh phần cứng**: Được hỗ trợ bằng vi kiến trúc phần cứng trên card **RTX 4090 (Ada Lovelace)** và **H100 (Hopper)**. Phép nhân ma trận FP8 diễn ra trực tiếp trên phần cứng mà không cần bước giải nén (dequantize) ngược lại FP16!
- **Đánh giá**: Độ suy hao trí tuệ gần như bằng 0 (dưới 0.5% so với BF16 gốc).

---

## 📊 Bảng Ma Trận So Sánh Các Định Dạng

| Tiêu chí | BF16 / FP16 (Gốc) | FP8 | AWQ (4-bit) | GPTQ (4-bit) | GGUF (Q4_K_M) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kích thước VRAM** | 100% (Gốc) | ~50% | ~28% | ~28% | ~28% |
| **Suy hao độ chính xác** | 0% (Hoàn hảo) | Cực thấp (<0.5%) | Rất thấp (~1-2%) | Thấp (~2-3%) | Rất thấp (~1-2%) |
| **Engine tương thích tốt nhất**| vLLM / TGI | vLLM (Ada/Hopper) | **vLLM** | vLLM / AutoGPTQ | **Ollama / llama.cpp** |
| **Khả năng chạy trên CPU** | Rất chậm | Không hỗ trợ | Không hỗ trợ | Không hỗ trợ | **⭐️⭐️⭐️⭐️⭐️ (Tuyệt vời)** |
| **Tốc độ sinh chữ GPU** | Tiêu chuẩn | **Rất nhanh** | **Rất nhanh** | Nhanh | Trung bình |

---

## 🎯 Hướng Dẫn Thực Chiến: Chọn File Gì Khi Lên HuggingFace?

Khi tìm model trên HuggingFace:
1. Nếu bạn chạy **vLLM trên GPU NVIDIA (RTX 3090, 4090, A100)**:
   - Hãy gõ tìm tên model kèm hậu tố `-AWQ` (ví dụ: `Qwen/Qwen2.5-7B-Instruct-AWQ` hoặc `neuralmagic/Meta-Llama-3.1-8B-Instruct-quantized.w4a16`).
2. Nếu bạn chạy **Ollama trên máy tính cá nhân, MacBook hoặc máy chỉ có CPU**:
   - Hãy chọn các file định dạng `.gguf` với mức nén `Q4_K_M` hoặc `Q5_K_M`.
3. Nếu bạn sở hữu **cụm NVIDIA H100**:
   - Hãy chọn model nén `FP8` để tận dụng trọn vẹn sức mạnh của nhân thế hệ mới Transformer Engine!
