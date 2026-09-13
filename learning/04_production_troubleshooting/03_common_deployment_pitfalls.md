# 03. Các Cạm Bẫy Triển Khai Thực Tế & Cách Phòng Tránh (Deployment Pitfalls)

Khi đưa một hệ thống AI vào môi trường chạy thực tế, 90% thời gian của kỹ sư thường bị tiêu tốn vào các lỗi cơ bản về môi trường, cổng mạng và xung đột driver.

Dưới đây là 5 cạm bẫy kinh điển và cách giải quyết trong 30 giây.

---

## ⚠️ Cạm Bẫy 1: Xung Đột Phiên Bản NVIDIA Driver & CUDA Runtime

### Lỗi hiển thị trong log container:
```text
RuntimeError: The NVIDIA driver on your system is too old (found version 11080).
Please update your GPU driver to support CUDA 12.4.
```

### Nguyên Nhân:
Image Docker `vllm/vllm-openai` được biên dịch với CUDA Toolkit 12.x mới nhất. Phiên bản này đòi hỏi NVIDIA Driver trên máy chủ (Host OS) phải đạt phiên bản tối thiểu tương ứng:
- **CUDA 12.1**: Yêu cầu Driver $\ge 525.60.13$.
- **CUDA 12.4**: Yêu cầu Driver $\ge 550.54.14$.

### Cách Khắc Phục:
1. Chạy `nvidia-smi` trên máy chủ để xem phiên bản Driver hiện tại.
2. Nâng cấp driver máy chủ lên bản mới nhất của NVIDIA:
   ```bash
   # Trên Ubuntu / Debian:
   sudo apt update && sudo apt install -y nvidia-driver-550
   sudo reboot
   ```

---

## ⚠️ Cạm Bẫy 2: Lỗi 401 Unauthorized Hoặc Repo Không Tồn Tại Trên Hugging Face

### Lỗi hiển thị:
```text
OSError: You are trying to access a gated repo.
Make sure to have access to it at https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct
and pass your token with `huggingface-cli login`.
```

### Cách Khắc Phục:
1. Truy cập trang mô hình trên HuggingFace và bấm nút **"Agree and access repository"** để được duyệt quyền tải.
2. Tạo Access Token (quyền `Read`) tại: `https://huggingface.co/settings/tokens`.
3. Điền token vào file `.env`:
   ```bash
   HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
4. Khởi động lại container vLLM.

---

## ⚠️ Cạm Bẫy 3: Xung Đột Cổng Mạng (Port Conflict)

### Hiện tượng:
Chạy `docker compose up -d` báo lỗi:
```text
Error response from daemon: driver failed programming external connectivity on endpoint llm-serving-ollama: Bind for 0.0.0.0:11434 failed: port is already allocated
```

### Nguyên Nhân:
Máy của bạn trước đó đã cài sẵn phần mềm Ollama chạy nền trực tiếp trên Windows/Linux, chiếm dụng mất cổng `11434`.

### Cách Khắc Phục:
- **Cách 1**: Tắt service Ollama trên máy host (`taskkill /F /IM ollama.exe` trên Windows hoặc `systemctl stop ollama` trên Linux).
- **Cách 2**: Đổi cổng ngoài trong file `.env`:
  ```bash
  OLLAMA_PORT=11435 # Ánh xạ cổng host sang 11435, trong container vẫn là 11434
  ```

---

## ⚠️ Cạm Bẫy 4: Tràn Đĩa Cứng Do Cache File Trọng Số (Disk Full)

### Nguyên Nhân:
Mỗi mô hình LLM khi tải về máy sẽ sinh ra hàng chục file `.safetensors` nặng từ 5GB đến 40GB. Nếu bạn để Docker ghi vào phân vùng root `/` mặc định, ổ đĩa sẽ bị đầy 100%, làm toàn bộ hệ điều hành bị treo.

### Giải Pháp Đã Được Thiết Lập Trong Dự Án Này:
Trong `docker-compose.yml`, chúng ta tách riêng thư mục cache ra biến môi trường:
```yaml
volumes:
  - ${HF_CACHE_DIR:-./huggingface_cache}:/root/.cache/huggingface
```
Nếu máy bạn có ổ cứng phụ dung lượng lớn (ví dụ gắn ở `/mnt/data`), chỉ cần sửa trong `.env`:
```bash
HF_CACHE_DIR=/mnt/data/huggingface_cache
```

---

## ⚠️ Cạm Bẫy 5: Giới Hạn RAM & Swap Trong Môi Trường WSL2 (Windows)

### Hiện tượng:
Khi chạy Docker Desktop trên Windows qua WSL2, container vLLM vừa khởi động thì tự động biến mất (`exited with code 137` - tín hiệu OOMKilled của Linux Kernel).

### Nguyên Nhân:
Mặc định WSL2 chỉ cấp tối đa 50% dung lượng RAM vật lý của máy tính Windows cho môi trường ảo Linux. Khi vLLM nạp model lớn, Linux hết RAM trước khi kịp nạp lên GPU!

### Cách Khắc Phục:
Tạo hoặc sửa file `C:\Users\<Tên_Bạn>\.wslconfig`:
```ini
[wsl2]
memory=24GB      # Nâng giới hạn RAM cho WSL2
processors=8     # Số nhân CPU
swap=16GB        # Dung lượng bộ nhớ ảo swap
```
Sau đó mở PowerShell và chạy:
```powershell
wsl --shutdown
```
Khởi động lại Docker Desktop, hệ thống sẽ nhận đủ tài nguyên để vận hành mượt mà!
