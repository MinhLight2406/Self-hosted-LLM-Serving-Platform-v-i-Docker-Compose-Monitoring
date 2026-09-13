# 04. Mở Rộng Phần Cứng: Scale Multi-GPU Với Tensor Parallelism vs Data Parallelism

Khi doanh nghiệp phát triển hoặc cần phục vụ các mô hình lớn (như Llama-3-70B, Qwen-2.5-72B), một GPU đơn lẻ không còn đủ VRAM để chứa mô hình. Bạn phải mở rộng hệ thống sang **Nhiều GPU (Multi-GPU)**.

---

## 1. Ba Kỹ Thuật Song Song Hóa Phổ Biến (Parallelism Strategies)

```
                       CÁC PHƯƠNG PHÁP SCALE MULTI-GPU
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│ Tensor Parallel  │         │ Pipeline Parallel│         │  Data Parallel   │
│       (TP)       │         │       (PP)       │         │       (DP)       │
├──────────────────┤         ├──────────────────┤         ├──────────────────┤
│ Cắt nhỏ ma trận  │         │ Cắt theo lớp     │         │ Nhân bản model   │
│ trọng số trong   │         │ (Layer 1-16: GPU0│         │ nguyên vẹn sang  │
│ từng Layer ra các│         │  Layer 17-32:GPU1│         │ từng card riêng  │
│ GPU cùng tính    │         │                  │         │ biệt             │
└──────────────────┘         └──────────────────┘         └──────────────────┘
```

---

## 2. So Sánh Bản Chất: Tensor Parallelism (TP) vs Data Parallelism (DP)

Rất nhiều kỹ sư mắc sai lầm: **Cứ có 2 GPU là bật `tensor-parallel-size=2`**. Đây là tư duy chưa tối ưu!

| Tiêu chí | Tensor Parallelism (TP) | Data Parallelism (DP via LiteLLM) |
| :--- | :--- | :--- |
| **Bản chất** | Chia nhỏ 1 model instance lên nhiều GPU | Chạy nhiều model instances độc lập trên từng GPU |
| **Giao tiếp liên GPU** | Cực kỳ dày đặc (gọi **All-Reduce** sau mỗi layer) | **Bằng 0** (Không cần giao tiếp giữa các GPU) |
| **Yêu cầu phần cứng** | Bắt buộc bus tốc độ cao (**NVLink** hoặc PCIe Gen4/5 x16) | Chỉ cần PCIe bình thường, card cắm rời độc lập |
| **Tác dụng chính** | **Giảm độ trễ đơn luồng** & chứa model vượt quá VRAM 1 card | **Tăng gấp đôi tổng Throughput** hệ thống |
| **Khi nào nên dùng?** | Khi **bắt buộc** (Model 70B không thể nhét vừa 1 GPU) | Khi model đã vừa 1 GPU (7B/8B) và muốn phục vụ nhiều người hơn |

> **Quy Tắc Vàng Của AI Systems Architect**:
> Nếu model của bạn **nhét vừa 1 GPU**, hãy dùng **Data Parallelism** (chạy 2 container vLLM riêng biệt trên GPU 0 và GPU 1, để LiteLLM Gateway chia tải cân bằng `round-robin` hoặc `least-busy`). Cách này cho tổng thông lượng (Throughput) cao hơn hẳn Tensor Parallelism vì không tốn thời gian trao đổi dữ liệu All-Reduce qua đường truyền PCIe!

---

## 3. Hướng Dẫn Cấu Hình Tensor Parallelism Khi Model Quá Lớn

Khi bạn cần chạy mô hình 70B (yêu cầu ghép 2 card RTX 3090/4090 24GB hoặc 2 card A100):

### 1. Cập nhật `.env`:
```bash
# Sử dụng 2 GPU chạy song song
VLLM_TENSOR_PARALLEL_SIZE=2
```

### 2. Kiểm tra `docker-compose.yml`:
Đảm bảo container vLLM được cấp phép nhìn thấy cả 2 card GPU:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 2 # Hoặc device_ids: ['0', '1']
          capabilities: [gpu]
```

### 3. Nguyên lý chia Head Attention của TP:
Số lượng Attention Heads hoặc KV Heads của mô hình bắt buộc phải **chia hết** cho giá trị `tensor-parallel-size`.
- *Ví dụ*: Llama-3-70B có 8 KV heads. Bạn có thể chọn `tensor-parallel-size` là **1, 2, 4, hoặc 8**. Bạn **không thể** chọn 3 hoặc 6 vì sẽ gây lỗi crash ma trận trọng số không chia đều được.
