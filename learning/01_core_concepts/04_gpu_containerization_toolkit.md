# 04. Đóng Gói GPU Với Docker & NVIDIA Container Toolkit

Để chạy mô hình AI bên trong Docker container, container không chỉ cần CPU và RAM ảo hóa thông thường mà cần quyền truy cập trực tiếp vào phần cứng card đồ họa NVIDIA. Kiến trúc này hoạt động như thế nào và tại sao cần cấu hình đặc thù?

---

## 1. Vấn Đề Khi Đóng Gói Ứng Dụng GPU Trong Container

Container theo tiêu chuẩn OCI (Open Container Initiative) có cơ chế cô lập triệt để:
- Chỉ nhìn thấy CPU và RAM do Linux cgroups cấp.
- Không thể tự ý nhìn thấy hoặc gọi trực tiếp tập lệnh vào các thanh ghi phần cứng trên bo mạch PCIe của card đồ họa.
- Nếu bạn chỉ cài CUDA Toolkit bên trong Dockerfile thông thường mà không có cầu nối phần cứng, câu lệnh `torch.cuda.is_available()` sẽ luôn trả về `False`.

---

## 2. Kiến Trúc Của NVIDIA Container Toolkit

NVIDIA không ảo hóa toàn bộ card đồ họa vào container (vì sẽ làm giảm hiệu năng trầm trọng). Thay vào đó, họ thiết kế mô hình **Passthrough Driver Libraries**:

```
┌─────────────────────────────────────────────────────────────┐
│ Docker Container (vLLM / PyTorch / CUDA Runtime App)        │
│ - PyTorch / vLLM App                                        │
│ - libcudart.so, libcublas.so (CUDA User-space libraries)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Gọi hàm CUDA API
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ NVIDIA Container Runtime (libnvidia-container)              │
│ - Tự động mount động các file thư viện driver (.so) từ host │
│   vào thư mục /usr/lib/x86_64-linux-gnu/ của Container      │
│ - Thiết lập quyền truy cập thiết bị /dev/nvidia*            │
└──────────────────────────────┬──────────────────────────────┘
                               │ IOCTL & UVM syscalls
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Host Kernel & Hardware                                      │
│ - Host NVIDIA Kernel Driver (nvidia.ko, nvidia-uvm.ko)      │
│ - Phần cứng vật lý NVIDIA GPU (RTX / A100 / H100)           │
└─────────────────────────────────────────────────────────────┘
```

### 3 Thành Phần Cơ Bản:
1. **Host Kernel Driver**: Driver NVIDIA chính cài trên máy chủ (Host OS). Cung cấp `nvidia-smi` và các kernel module (`nvidia.ko`, `nvidia-uvm.ko`).
2. **NVIDIA Container Toolkit (`nvidia-ctk`)**: Tiện ích cấu hình Docker daemon (`/etc/docker/daemon.json`) để Docker nhận diện runtime `nvidia`.
3. **libnvidia-container**: Thư viện C chịu trách nhiệm tiêm (inject) các file thiết bị `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm` vào namespace của container khi container khởi chạy.

---

## 3. Cấu Hình Chuẩn Trong `docker-compose.yml`

Trong `docker-compose.yml` của dự án, bạn sẽ thấy đoạn khai báo:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

### Ý Nghĩa Kỹ Thuật:
- `driver: nvidia`: Báo cho Docker Engine sử dụng runtime hook của NVIDIA thay vì runc mặc định.
- `count: all`: Cấp phép cho container nhìn thấy toàn bộ GPU có trên máy. Nếu chỉ muốn cấp card số 0, ta đổi thành `device_ids: ['0']`.
- `capabilities: [gpu]`: Cho phép container sử dụng cả nhân tính toán (compute) và tiện ích driver (utility - để đọc số đo nhiệt độ, bộ nhớ qua `nvidia-smi`).

---

## 4. Cạm Bẫy Sống Còn: Bộ Nhớ Chia Sẻ (`ipc: host` hoặc `shm_size`)

Khi chạy vLLM hoặc các mô hình song song đa tiến trình (Multi-GPU hoặc Multi-worker), lỗi phổ biến nhất là:

```text
RuntimeError: DataLoader worker (pid 123) is killed by signal: Bus error (core dumped).
NCCL error: unhandled system error / broken pipe.
```

### Nguyên Nhân:
- Mặc định, Docker cấp phát vùng nhớ dùng chung **POSIX Shared Memory (`/dev/shm`)** cho mỗi container chỉ vỏn vẹn **64 MB**!
- PyTorch và các thư viện giao tiếp liên tiến trình (NCCL, PyTorch multiprocessing) sử dụng `/dev/shm` để truyền các tensor trọng số khổng lồ giữa CPU và GPU. 64 MB là quá nhỏ, dẫn đến tràn bộ nhớ và kernel lập tức bắn tín hiệu `SIGBUS`.

### Giải Pháp Triệt Để:
Trong `docker-compose.yml` của chúng ta, cấu hình sau đã được thiết lập:

```yaml
services:
  vllm-engine:
    ...
    ipc: host # Sử dụng trực tiếp Shared Memory của hệ điều hành host
```

> **Ghi chú**: Nếu trong môi trường bảo mật nghiêm ngặt không cho phép dùng `ipc: host`, giải pháp thay thế là cấu hình dung lượng cụ thể: `shm_size: '16gb'`.
