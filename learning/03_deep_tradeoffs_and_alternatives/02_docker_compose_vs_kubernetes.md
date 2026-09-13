# 02. Docker Compose vs Kubernetes: Khi Nào Nên Sử Dụng Công Cụ Nào?

Một câu hỏi phỏng vấn kinh điển cho vị trí Senior MLOps Engineer: **"Tại sao đồ án này lại dùng Docker Compose mà không dựng ngay trên Kubernetes (K8s)?"**

Tài liệu này phân tích góc nhìn thực tế về chi phí, độ phức tạp và lộ trình nâng cấp hạ tầng.

---

## 1. Lý Do Chọn Docker Compose Trong Giai Đoạn Này

Rất nhiều dự án thất bại vì bệnh "Kỹ thuật hóa quá đà" (Over-engineering) khi cố gắng dựng Kubernetes ngay từ khi chỉ có 1 đến 2 máy chủ GPU.

### 4 Lợi Ích Vượt Trội Của Docker Compose:
1. **Thời gian khởi tạo tính bằng giây**: Chỉ cần `docker compose up -d`, toàn bộ hệ thống gồm Serving, Gateway, Metrics, Dashboards đều chạy trơn tru mà không cần cấu hình Ingress, PV/PVC, CNI hay Device Plugin.
2. **Loại bỏ gánh nặng Control Plane**: Một cụm K8s tiêu tốn tài nguyên đáng kể cho `kube-apiserver`, `etcd`, `kube-controller`, `kubelet`... Trên máy chủ GPU, mỗi giọt RAM và CPU đều nên dành trọn vẹn cho việc truyền dữ liệu tensor.
3. **Tránh lỗi NVIDIA Device Plugin**: Quản lý GPU passthrough trên Docker cực kỳ đơn giản và ổn định (`driver: nvidia`). Trên Kubernetes, bạn phải cấu hình Helm chart cho `k8s-device-plugin`, thường xuyên gặp lỗi Pod không nhận diện được GPU sau khi node khởi động lại.
4. **Cực kỳ tối ưu cho máy trạm On-Premise hoặc Cloud GPU đơn lẻ**: Các máy chủ cloud GPU phổ biến hiện nay (AWS EC2 g5.12xlarge, Lambda Labs, RunPod, Vast.ai) thường cấp phát theo từng Node đơn lẻ có từ 1 đến 8 GPU. Docker Compose quản lý 8 GPU trên 1 node hoàn toàn mượt mà!

---

## 2. Khi Nào BẮT BUỘC Phải Chuyển Lên Kubernetes?

Bạn chỉ nên đầu tư công sức chuyển đổi hệ thống sang Kubernetes khi xuất hiện các điều kiện sau:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Hệ thống vượt ngưỡng 1 Node (Multi-node GPU Cluster)                    │
│    - Bạn cần gom 10 máy chủ GPU khác nhau thành 1 cụm thống nhất.           │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. Cần Autoscaling tự động theo hàng đợi tải thực tế                        │
│    - Ban ngày có 10,000 nhân viên sử dụng ➔ Tự động scale lên 10 GPU pods. │
│    - Ban đêm ít người dùng ➔ Tự động thu gọn về 1 pod để tiết kiệm tiền.   │
│    - Sử dụng công cụ KEDA (Kubernetes Event-driven Autoscaling) kích hoạt    │
│      dựa trên metric PromQL `vllm:num_requests_waiting > 5`.               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. Triển khai Zero-Downtime Rolling Update quy mô lớn                       │
│    - Cập nhật model mới mà không rớt dù chỉ 1 request của người dùng        │
│      thông qua Kubernetes Readiness Probes và RollingUpdate strategy.       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Bảng So Sánh Quyết Định Hạ Tầng

| Khía cạnh | Docker Compose (Hiện Tại) | Kubernetes / KServe (Tương Lai) |
| :--- | :--- | :--- |
| **Quy mô máy chủ** | 1 Node (từ 1 đến 8 GPU cắm chung mainboard) | Cụm nhiều Node (Hàng chục, hàng trăm GPU) |
| **Độ phức tạp bảo trì** | Rất thấp (1 file YAML, kỹ sư AI tự vận hành được) | Cao (Cần đội ngũ DevOps/Platform riêng) |
| **Chi phí hạ tầng** | 0$ phí vận hành control plane | Tốn chi phí quản lý cụm (EKS/GKE control plane) |
| **Khả năng tự hồi phục** | `restart: unless-stopped` (Cấp độ tiến trình) | Tự động dời Pod sang Node khác khi hỏng phần cứng |
| **Chiến lược mở rộng** | Scale dọc (Vertical - Nâng cấp GPU mạnh hơn) | Scale ngang (Horizontal - Bổ sung thêm nhiều Node) |

---

## 4. Lộ Trình Chuyển Đổi Mượt Mà (Migration Path)

Nếu sau này công ty bạn yêu cầu đưa lên K8s, toàn bộ công sức bạn làm trong đồ án này **không hề bị bỏ phí**, vì:
- Các Container Image (`vllm/vllm-openai`, `ghcr.io/berriai/litellm`) hoàn toàn tái sử dụng 100%.
- Cấu hình `config/litellm/config.yaml` và `prometheus.yml` chỉ cần chuyển đổi thành Kubernetes `ConfigMap`.
- Dashboards Grafana JSON được nạp vào K8s qua Grafana Operator.
- Tư duy về đo lường TTFT, TPOT và tối ưu VRAM vẫn giữ nguyên giá trị cốt lõi.
