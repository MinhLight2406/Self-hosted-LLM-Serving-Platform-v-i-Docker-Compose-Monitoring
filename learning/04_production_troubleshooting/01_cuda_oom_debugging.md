# 01. Sổ Tay Xử Lý Triệt Để Lỗi CUDA Out Of Memory (OOM Runbook)

Lỗi kinh điển nhất trong kỹ thuật phục vụ LLM là:
```text
torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.14 GiB (GPU 0; 23.69 GiB total capacity; 21.80 GiB already allocated; 1.20 GiB free; 21.90 GiB reserved in total by PyTorch)
```

Khi gặp lỗi này, hãy thực hiện theo quy trình khám nghiệm 4 bước chuẩn sau đây.

---

## 🔍 Bước 1: Điều Tra Tiến Trình "Ma" (Zombie Processes) Đang Chiếm VRAM

Trước khi nghi ngờ cấu hình vLLM, rất có thể một tiến trình Python cũ bị crash nhưng chưa giải phóng VRAM trên GPU máy chủ:

```bash
# Xem ứng dụng nào đang chiếm VRAM
nvidia-smi

# Xem danh sách PID đang giữ file thiết bị GPU
sudo fuser -v /dev/nvidia*

# Diệt triệt để tiến trình ma bị treo (Thay PID bằng số thực tế)
sudo kill -9 <PID>
```

---

## 🔍 Bước 2: Kiểm Tra Tỷ Lệ Cấp Phát VRAM (`gpu-memory-utilization`)

Trong `docker-compose.yml`, kiểm tra cờ `--gpu-memory-utilization`:

- **Nếu bạn đang để `0.95` hoặc `1.0`**: Hãy **hạ ngay xuống `0.85` hoặc `0.90`**.
- **Lý do**: Khi khởi động, vLLM sẽ tính toán và lấy đúng tỷ lệ phần trăm này để dành riêng cho Trọng số và KV Cache. Nếu bạn để quá cao, GPU không còn đủ vài trăm megabytes VRAM trống cho **Activation Tensors** sinh ra đột ngột trong giai đoạn Prefill của prompt dài, dẫn đến OOM tức thì.

---

## 🔍 Bước 3: Giới Hạn Chiều Dài Context Tối Đa (`max-model-len`)

Rất nhiều model mới khai báo context window mặc định là 32,768 hoặc 131,072 tokens:
- Nếu bạn không ép tham số `--max-model-len`, vLLM sẽ cố gắng chuẩn bị không gian KV cache cho chiều dài khủng khiếp này.
- **Cách khắc phục trong `.env`**:
  ```bash
  # Giảm chiều dài tối đa xuống mức đáp ứng đủ nhu cầu nghiệp vụ
  VLLM_MAX_MODEL_LEN=4096
  ```
- Thao tác này ngay lập tức giải phóng hàng Gigabytes VRAM cho KV Cache!

---

## 🔍 Bước 4: Kích Hoạt Kỹ Thuật Nén KV Cache (FP8 KV Cache)

Nếu bạn vẫn muốn giữ context dài mà không bị tràn VRAM, hãy kích hoạt cơ chế lưu trữ KV Cache ở định dạng FP8 thay vì FP16 mặc định:

Thêm cờ sau vào lệnh chạy của `vllm-engine` trong `docker-compose.yml`:
```yaml
command: >
  --model ${VLLM_MODEL}
  --kv-cache-dtype fp8
  ...
```

### Kết Quả Đạt Được:
- Kích thước mỗi token trong KV Cache giảm đi đúng **50%** (từ 2 bytes xuống 1 byte).
- Dung lượng VRAM dành cho KV Cache tăng gấp đôi khả năng chứa token, triệt tiêu nguy cơ OOM khi phục vụ nhiều người cùng lúc!
