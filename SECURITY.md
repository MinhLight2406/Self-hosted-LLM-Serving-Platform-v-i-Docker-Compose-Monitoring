# 🛡️ Chính Sách Bảo Mật & Quyền Riêng Tư (Security & Privacy Policy)

Tài liệu này quy định các tiêu chuẩn bảo mật kiến trúc và hướng dẫn vận hành nhằm bảo vệ tối đa các thông tin nhạy cảm: **API Keys**, **thông tin đăng nhập quản trị (Admin Credentials)**, và **tài nguyên tính toán phần cứng GPU**.

---

## 1. Nguyên Tắc Bảo Vệ Dữ Liệu Nhạy Cảm (Zero-Leak Policy)

### 1.1. Cách Ly Hoàn Toàn File Bí Mật (`.env`)
- Toàn bộ thông tin nhạy cảm (bao gồm `HF_TOKEN`, `LITELLM_MASTER_KEY`, `GRAFANA_ADMIN_PASSWORD`) **bắt buộc phải nằm trong file `.env`**.
- File `.gitignore` của dự án đã được thiết lập để **chặn vĩnh viễn** việc commit file `.env`, `*.key`, `*.pem`, `*.env.local` lên Git.
- Dự án chỉ lưu giữ file mẫu `.env.example` chứa các placeholder mô tả, tuyệt đối không chứa mật khẩu hay API Key thực tế.

### 1.2. Loại Bỏ Mật Khẩu Mặc Định (No Insecure Defaults)
- Trong `docker-compose.yml`, các biến nhạy cảm được khai báo theo cú pháp bắt buộc:
  ```yaml
  LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:?Error: LITELLM_MASTER_KEY phai duoc thiet lap trong .env}
  GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:?Error: GRAFANA_ADMIN_PASSWORD phai duoc thiet lap trong .env}
  ```
- Nếu người vận hành chưa cấu hình file `.env`, Docker Compose sẽ từ chối khởi động thay vì chạy với mật khẩu mặc định yếu (`admin/admin` hoặc dummy keys).

---

## 2. Kiến Trúc Cô Lập Mạng (Network Isolation & Port Hardening)

Một trong những lỗ hổng nghiêm trọng nhất khi triển khai LLM là **lộ cổng suy luận thô (Raw Inference Port) ra Internet**, khiến kẻ xấu có thể gửi request trực tiếp đến vLLM mà không cần xác thực, chiếm dụng 100% tài nguyên GPU (GPU Hijacking).

Dự án này áp dụng mô hình **Phòng Thủ Đa Tầng (Defense-in-Depth)**:

```
                            INTERNET / CLIENTS
                                     │
                 ┌───────────────────┴───────────────────┐
                 │ Cổng Công Khai (Public Ports)         │
                 │ • Cổng 4000: LiteLLM Gateway (Có Auth)│
                 │ • Cổng 3000: Grafana Dashboard (Auth) │
                 └───────────────────┬───────────────────┘
                                     │ (Docker Network Nội Bộ)
  ═══════════════════════════════════╪═══════════════════════════════════
  RÀO CHẮN AN TOÀN: CÁC DỊCH VỤ NỘI BỘ CHỈ LẮNG NGHE TẠI 127.0.0.1
  ═══════════════════════════════════╪═══════════════════════════════════
                 ┌───────────────────┴───────────────────┐
                 │ Cổng Nội Bộ (Localhost Only 127.0.0.1)│
                 │ • 127.0.0.1:8000   -> vLLM Engine     │
                 │ • 127.0.0.1:11434  -> Ollama Engine   │
                 │ • 127.0.0.1:9090   -> Prometheus TSDB │
                 │ • 127.0.0.1:9400   -> DCGM Exporter   │
                 │ • 127.0.0.1:8080   -> cAdvisor        │
                 └───────────────────────────────────────┘
```

### Tại sao phải bind vào `127.0.0.1`?
- **Chống vượt mặt Gateway (Bypass Prevention)**: Kẻ tấn công từ mạng ngoài không thể gọi thẳng tới `http://<IP_Server>:8000/v1/completions` để trốn tránh Rate Limit và API Key.
- **Chống lộ thông số nhạy cảm**: Số liệu phần cứng, nhật ký sử dụng và cấu hình container trong Prometheus/cAdvisor không bị quét trúng bởi các công cụ tìm kiếm lỗ hổng như Shodan hay Censys.

---

## 3. Hướng Dẫn Thiết Lập Khóa Bí Mật Chuẩn Doanh Nghiệp

Trước khi triển khai lên máy chủ thật, hãy tạo các chuỗi khóa ngẫu nhiên có độ dài tối thiểu 32 ký tự:

### Tạo Khóa Master Key Cho LiteLLM:
- **Trên Linux / macOS**:
  ```bash
  openssl rand -hex 32
  ```
- **Trên Windows PowerShell**:
  ```powershell
  -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
  ```

### Điền vào file `.env`:
```bash
LITELLM_MASTER_KEY=sk-f83a9e01b72c4d5e9f8a12bc34de56fa78bc90de12fa34bc56de78fa90bc12de
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=K9#mX$8vL!2pQ@zW4yT&7rE^5tU*3oI
```

---

## 4. Cơ Chế Masking Trong Tooling & Scripts
- Mọi script kiểm thử và benchmark trong thư mục `scripts/` (`test_request.py`, `benchmark_llm.py`) đều được tích hợp hàm che giấu token (`mask_secret`):
  - Chỉ hiển thị 4 ký tự đầu và 4 ký tự cuối (ví dụ: `sk-f...12de`), ngăn chặn việc vô tình quay màn hình hoặc chụp ảnh log làm lộ API key.
- Các script tự động dò tìm file `.env` ở thư mục hiện tại để nạp biến môi trường an toàn mà không yêu cầu người dùng phải gõ API key bằng tay trên command line (tránh bị lưu trong lịch sử `bash_history` hoặc PowerShell history).
