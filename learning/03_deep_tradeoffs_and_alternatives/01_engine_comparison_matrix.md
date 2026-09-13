# 01. Ma Trận So Sánh Các LLM Serving Engines Hàng Đầu Hiện Nay

Khi xây dựng hạ tầng phục vụ mô hình ngôn ngữ lớn, việc chọn sai Serving Engine có thể khiến doanh nghiệp lãng phí hàng nghìn USD tiền thuê GPU mỗi tháng hoặc khiến hệ thống chịu độ trễ cao không thể chấp nhận được.

Dưới đây là bảng so sánh định lượng và định tính giữa 5 engine phổ biến nhất: **vLLM, Ollama, TGI, TensorRT-LLM, và SGLang**.

---

## 📊 Bảng Ma Trận So Sánh Tổng Thể

| Tiêu chí | vLLM | Ollama (llama.cpp) | HuggingFace TGI | NVIDIA TensorRT-LLM | SGLang |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ngôn ngữ cốt lõi** | Python + CUDA / Triton | C++ (llama.cpp) + Go | Rust + C++ + Python | C++ thuần + TensorRT | Python + CUDA / C++ |
| **Thuật toán bộ nhớ** | **PagedAttention** | Naive memory / Static | Paged Attention | Paged KV Cache | **RadixAttention** |
| **Thông lượng (Throughput)**| ⭐️⭐️⭐️⭐️⭐️ (Rất cao) | ⭐️⭐️ (Trung bình/Thấp) | ⭐️⭐️⭐️⭐️ (Cao) | ⭐️⭐️⭐️⭐️⭐️ (Cực đại) | ⭐️⭐️⭐️⭐️⭐️ (Rất cao) |
| **Độ trễ First Token (TTFT)**| Nhanh | Nhanh (Single user) | Nhanh | **Siêu nhanh (Tối ưu nhất)**| Nhanh (Có cache prefix) |
| **Hỗ trợ CPU Offload** | Hạn chế (ưu tiên GPU) | **⭐️⭐️⭐️⭐️⭐️ (Xuất sắc)** | Không hỗ trợ | Không hỗ trợ | Hạn chế |
| **Độ phức tạp triển khai** | Dễ (Docker 1 dòng lệnh) | Siêu dễ (Cài như app) | Dễ (Docker chính thức) | **Rất khó (Phải compile)**| Dễ (Tương tự vLLM) |
| **Tương thích phần cứng** | NVIDIA, AMD ROCm, Intel | NVIDIA, AMD, Apple M, CPU | NVIDIA, AMD, Habana | **Chỉ NVIDIA GPU** | NVIDIA, AMD ROCm |
| **Thế mạnh đặc thù** | Phục vụ đồng thời nhiều người | Local dev, máy cá nhân | Hệ sinh thái HuggingFace | Ép xung tối đa cho H100 | Multi-turn chat, JSON output |

---

## 🔍 Phân Tích Chuyên Sâu Từng Engine

### 1. vLLM (Lựa Chọn Mặc Định Cho Production Của Dự Án Này)
- **Điểm mạnh nhất**: Cân bằng hoàn hảo giữa hiệu năng cực cao và tính dễ sử dụng. Cộng đồng phát triển mạnh mẽ nhất thế giới hiện nay. Hỗ trợ chuẩn API của OpenAI ngay khi khởi động.
- **Điểm yếu**: Ngốn VRAM tĩnh khá lớn để cấp phát cho KV Cache (`gpu_memory_utilization`), không phù hợp cho máy không có card đồ họa rời.

### 2. Ollama (Dự Phòng Fallback Cho Dự Án Này)
- **Điểm mạnh nhất**: Tính cơ động và khả năng tương thích phần cứng tuyệt vời. Chạy mượt mà trên laptop MacBook (Apple Silicon M1/M2/M3/M4) và máy chủ chỉ có CPU nhờ backend `llama.cpp`. Quản lý tải model dạng "kéo thả" như Docker image (`ollama pull`).
- **Điểm yếu**: Không thiết kế cho môi trường chịu tải đồng thời hàng trăm người (High Concurrency). Khi nhiều người cùng chat, tốc độ tụt thảm hại do thiếu cơ chế Continuous Batching ở quy mô lớn.

### 3. NVIDIA TensorRT-LLM
- **Điểm mạnh nhất**: Đạt đỉnh cao về tốc độ tính toán (Latency thấp nhất và Throughput cao nhất trên phần cứng NVIDIA A100/H100) nhờ việc compile toàn bộ mạng nơ-ron thành đồ thị TensorRT chuyên dụng, tối ưu hóa đến từng chu kỳ xung nhịp của vi kiến trúc GPU.
- **Điểm yếu**: Rào cản kỹ thuật cực cao. Mỗi khi đổi model hoặc đổi phiên bản, kỹ sư phải thực hiện bước build engine kéo dài hàng chục phút, file engine sau khi build bị gắn chặt vào một loại card GPU duy nhất (không mang chạy sang card khác được).

### 4. SGLang
- **Điểm mạnh nhất**: Kế thừa vLLM nhưng phát triển thuật toán **RadixAttention**, tự động lưu lại cây phân nhánh KV Cache của các cuộc trò chuyện nhiều lượt (Multi-turn conversation) và các tác vụ Agent gọi tool nhiều lần. Tốc độ sinh cấu trúc dữ liệu JSON nhanh gấp 2x - 3x.
- **Điểm yếu**: Hệ sinh thái công cụ hỗ trợ và độ ổn định lâu dài trên các môi trường cloud chưa phong phú bằng vLLM.

---

## 🎯 Cây Quyết Định (Decision Tree): Khi Nào Chọn Cái Gì?

```
Bạn cần phục vụ LLM trong tình huống nào?
│
├── 1. Bạn chỉ muốn test code cục bộ, máy chỉ có CPU hoặc MacBook?
│   └── ➔ CHỌN OLLAMA
│
├── 2. Bạn cần dựng hệ thống Production phục vụ nhiều người dùng, muốn nhanh, ổn định, chuẩn OpenAI API?
│   └── ➔ CHỌN vLLM (Lựa chọn tối ưu nhất cho 90% dự án thực tế)
│
├── 3. Ứng dụng của bạn là AI Agent, gọi Tool liên tục, context lặp lại nhiều vòng?
│   └── ➔ CHỌN SGLang
│
└── 4. Bạn có ngân sách hàng chục triệu USD, sở hữu cụm siêu máy tính NVIDIA H100, cần ép từng millisecond độ trễ?
    └── ➔ CHỌN NVIDIA TensorRT-LLM
```
