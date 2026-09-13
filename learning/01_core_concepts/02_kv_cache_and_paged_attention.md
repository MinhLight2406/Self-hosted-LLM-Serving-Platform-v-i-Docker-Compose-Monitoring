# 02. Bản Chất KV Cache & Thuật Toán Đột Phá PagedAttention

Trong quá trình suy luận Transformer, **KV Cache** là yếu tố tiêu tốn nhiều bộ nhớ VRAM thứ hai (chỉ sau trọng số mô hình) và là nguyên nhân hàng đầu gây ra lỗi **CUDA Out Of Memory (OOM)** khi hệ thống phục vụ nhiều người dùng đồng thời.

---

## 1. KV Cache Là Gì & Tại Sao Bắt Buộc Phải Có?

Trong cơ chế Self-Attention:
$$\text{Attention}(Q, K, V) = \text{Softmax}\left(\frac{Q K^T}{\sqrt{d_k}}\right) V$$

Khi sinh token thứ $t+1$:
- Ta cần vector Query ($Q_{t+1}$) của token hiện tại để so khớp với Key ($K$) và Value ($V$) của **toàn bộ các token từ $1$ đến $t$**.
- Nếu không lưu lại, ở mỗi bước sinh chữ, ta sẽ phải tính toán lại ma trận Key và Value cho tất cả $t$ token trước đó từ đầu $\rightarrow$ Độ phức tạp thời gian tăng theo cấp số $O(N^2)$, làm tốc độ suy luận chậm theo hàm mũ!
- **Giải pháp**: Tính $K$ và $V$ của mỗi token một lần duy nhất, sau đó lưu (cache) lại trong bộ nhớ VRAM của GPU. Bộ nhớ này gọi là **KV Cache**.

---

## 2. Thảm Họa Bộ Nhớ Của Cơ Chế Cũ (Naive KV Cache Allocation)

Trước khi có vLLM (ví dụ trong các framework truyền thống như HuggingFace Accelerate hoặc các naive serving engine), hệ thống cấp phát KV Cache theo kiểu **bộ nhớ liền kề (Contiguous Memory)**:

```
[Request 1: Max len cấu hình = 4096 tokens]
VRAM cấp phát tĩnh: [■■■■■■ (150 tokens thực tế) | □□□□□□□□□□□□□□□□□ (3946 tokens để trống)]
                      ▲                               ▲
                 Đang sử dụng                  Lãng phí VRAM nội vi (Internal Fragmentation)
```

### 3 Nguồn Lãng Phí VRAM Trong Cơ Chế Cũ:
1. **Lãng phí do dự đoán độ dài (Internal Fragmentation)**: Hệ thống phải cấp phát sẵn một mảng VRAM liền kề ứng với độ dài tối đa (ví dụ 4096 tokens). Nếu người dùng chỉ hỏi một câu ngắn và câu trả lời chỉ dài 200 tokens, **95% dung lượng VRAM đã cấp phát bị bỏ phí** và không request nào khác được đụng vào!
2. **Lãng phí do phân mảnh bộ nhớ ngoài (External Fragmentation)**: Khi các request với độ dài khác nhau liên tục kết thúc và giải phóng bộ nhớ, VRAM bị chia cắt thành nhiều mẩu vụn rời rạc không liền kề nhau, khiến request mới không tìm được khối VRAM liền kề đủ lớn để khởi tạo.
3. **Lãng phí do không thể chia sẻ (Over-reservation)**: Trong các tác vụ như Beam Search, Parallel Sampling (sinh nhiều câu trả lời cho cùng 1 prompt), hoặc System Prompt chung (Prefix), hệ thống cũ phải nhân bản toàn bộ KV Cache giống hệt nhau vào các vùng nhớ riêng biệt.

> **Hậu quả**: Nghiên cứu của đại học UC Berkeley chỉ ra rằng: **60% đến 80% dung lượng VRAM dùng cho KV Cache trong các hệ thống truyền thống bị lãng phí hoàn toàn!**

---

## 3. Thuật Toán PagedAttention (Đột Phá Của vLLM)

Được lấy cảm hứng từ cơ chế **Phân trang bộ nhớ ảo (Virtual Memory Paging)** trong các hệ điều hành kinh điển (như Linux kernel), vLLM đã đề xuất **PagedAttention**:

Thay vì ép buộc KV Cache của một chuỗi phải nằm trên một dải VRAM liền kề, PagedAttention cho phép lưu trữ KV Cache trong các **Khối bộ nhớ vật lý (Physical Blocks)** có kích thước cố định (ví dụ 16 tokens hoặc 32 tokens/block) nằm rải rác bất kỳ đâu trên VRAM.

```
Logical KV Cache (Chuỗi token logic liên tục của User)
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Block 0      │ Block 1      │ Block 2      │ Block 3      │
│ (Tokens 0-15)│(Tokens 16-31)│(Tokens 32-47)│ (Đang sinh)  │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Physical #12 │ Physical #3  │ Physical #88 │ Physical #45 │
└──────────────┴──────────────┴──────────────┴──────────────┘
  Các khối bộ nhớ vật lý nằm phân tán linh hoạt trên VRAM GPU
```

### Các Thành Phần Cốt Lõi:
1. **Logical Block**: Chuỗi KV cache được chia nhỏ thành từng block logic (mặc định `block_size = 16`).
2. **Physical Block**: Các ô nhớ thực tế trên VRAM GPU có kích thước bằng 1 Logical Block.
3. **Block Table**: Bảng ánh xạ (Mapping Table) do vLLM quản lý để theo dõi Block logic nào đang trỏ vào Block vật lý nào trên VRAM.
4. **PagedAttention CUDA Kernel**: Nhân tính toán Attention được viết riêng tối ưu bằng Triton/CUDA để có thể đọc dữ liệu KV từ các địa chỉ bộ nhớ phân tán một cách liên tục mà không làm giảm tốc độ tính toán của Tensor Cores.

---

## 4. Tại Sao PagedAttention Giúp Hệ Thống Đạt Hiệu Năng Vượt Trội?

1. **Triệt tiêu 96% sự lãng phí VRAM**: Chỉ cấp phát block mới khi block hiện tại đã đầy 16 tokens. Mức lãng phí tối đa chỉ nằm ở block cuối cùng (trung bình dưới 4%).
2. **Tăng Batch Size gấp 2x - 4x**: Nhờ thu hồi lượng VRAM bị lãng phí, GPU có thể chứa đồng thời số lượng request nhiều gấp nhiều lần trên cùng một phần cứng.
3. **Zero-Copy Prefix Caching**: Khi hàng trăm người dùng cùng gửi prompt có chung System Prompt ("Bạn là trợ lý AI chuyên nghiệp..."), vLLM cho phép tất cả các request này **dùng chung một Physical Block** duy nhất mà không cần sao chép!
4. **Continuous Batching (Orca-style)**: Có thể đưa request mới vào chạy ngay lập tức ở bước tiếp theo và giải phóng tài nguyên của request đã hoàn thành mà không phải chờ cả batch kết thúc.
