# 📚 Hệ Thống Tài Liệu Học Tập & Rèn Luyện Kỹ Năng: Self-hosted LLM Serving & MLOps

Chào mừng bạn đến với mô-đun **Learning** của đồ án **Self-hosted LLM Serving Platform with Docker Compose & Monitoring**.

Thư mục này được thiết kế như một **khóa huấn luyện thực chiến chuyên sâu (Hands-on MLOps & LLM Systems Engineering)**. Không chỉ dừng lại ở việc cung cấp mã nguồn để chạy lệnh, tài liệu tại đây tập trung trả lời 3 câu hỏi lớn mà mọi AI Engineer / MLOps Engineer cần phải thành thạo:
1. **Bản chất kỹ thuật (Deep Mechanics)**: LLM vận hành dưới phần cứng GPU như thế nào? Tại sao lại tốn VRAM? Bộ nhớ KV Cache và cơ chế PagedAttention giải quyết vấn đề gì?
2. **Kinh nghiệm kiến trúc (Architectural Evolution & Diff Reasoning)**: Tại sao hệ thống lại tiến hóa từ v1 đến v4? Khi nâng cấp, **tại sao lại phải thêm dòng này, sửa cờ kia, xóa cấu hình cũ?**
3. **Đánh đổi kỹ thuật (Trade-offs & Decision Matrices)**: Tại sao phương án này tối ưu trong kịch bản này nhưng lại tệ ở kịch bản khác? Khi nào dùng vLLM, khi nào dùng Ollama, TGI, SGLang hay TensorRT-LLM? Khi nào dùng Docker Compose, khi nào bắt buộc lên Kubernetes?

---

## 🗺️ Lộ Trình Học Tập (Curriculum Roadmap)

```
[Phase 1: Nền tảng cốt lõi]
      │
      ├── 01. Cơ chế sinh chữ LLM (Prefill vs Decode, Memory-Bound)
      ├── 02. KV Cache & Thuật toán PagedAttention
      ├── 03. Công thức tính toán chính xác VRAM GPU
      ├── 04. Container hóa GPU với Docker & NVIDIA Toolkit
      └── 05. Bốn chỉ số vàng đo lường LLM Serving (TTFT, TPOT, Throughput, Cache)
      │
[Phase 2: Tiến hóa kiến trúc & Thực hành Thêm-Xóa-Sửa]
      │
      ├── 01. Nhật ký tiến hóa kiến trúc v1 ➔ v4
      ├── 02. Cẩm nang "Tại sao phải Thêm - Xóa - Sửa" (Code & Config Diff)
      ├── 03. Quy trình đổi Model mới (AWQ, GGUF, Unsloth, HuggingFace)
      └── 04. Mở rộng phần cứng: Scale Multi-GPU với Tensor Parallelism
      │
[Phase 3: Ma trận đánh đổi & Quyết định công nghệ]
      │
      ├── 01. So sánh chi tiết: vLLM vs Ollama vs TGI vs TensorRT-LLM vs SGLang
      ├── 02. Docker Compose vs Kubernetes: Khi nào nên chuyển đổi?
      ├── 03. Toàn cảnh Quantization: AWQ vs GPTQ vs GGUF vs FP8 vs BF16
      └── 04. Tại sao LiteLLM tối ưu hơn tự viết API Gateway?
      │
[Phase 4: Thực chiến Runbook & Xử lý sự cố]
      │
      ├── 01. Sổ tay gỡ lỗi triệt để CUDA Out Of Memory (OOM)
      ├── 02. Chẩn đoán nghẽn cổ chai hiệu năng (TTFT cao, Queue đầy, ITL giật)
      └── 03. Các cạm bẫy triển khai thường gặp & cách khắc phục
```

---

## 📂 Cấu Trúc Chi Tiết Các Chuyên Mục

### 🔹 Phần 1: Kiến Thức Cốt Lõi Vận Hành & Triển Khai (`01_core_concepts/`)
Nắm vững bản chất vật lý và thuật toán của việc suy luận mô hình ngôn ngữ lớn:
- [01. Cơ chế sinh chữ LLM: Prefill vs Decode Phase](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/01_core_concepts/01_llm_inference_mechanics.md)
- [02. Bản chất KV Cache & Thuật toán PagedAttention](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/01_core_concepts/02_kv_cache_and_paged_attention.md)
- [03. Công thức tính toán chi tiết VRAM GPU](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/01_core_concepts/03_vram_estimation_formula.md)
- [04. GPU Containerization: Docker & NVIDIA Container Toolkit](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/01_core_concepts/04_gpu_containerization_toolkit.md)
- [05. Bốn chỉ số giám sát vàng (Golden Metrics)](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/01_core_concepts/05_golden_monitoring_metrics.md)

### 🔹 Phần 2: Thêm - Xóa - Sửa & Tiến Hóa Kiến Trúc (`02_architectural_evolution/`)
Học cách tư duy của một Kiến trúc sư Hệ thống (Systems Architect) khi phát triển dự án từ sơ khai đến production:
- [01. Nhật ký tiến hóa hệ thống từ v1 đến v4](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/02_architectural_evolution/01_evolution_roadmap_v1_to_v4.md)
- [02. Giải thích chi tiết Thêm - Xóa - Sửa qua từng phiên bản](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/02_architectural_evolution/02_why_add_modify_delete_guide.md)
- [03. Hướng dẫn thêm/thay đổi Model mới](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/02_architectural_evolution/03_how_to_change_models.md)
- [04. Nâng cấp hệ thống lên Multi-GPU với Tensor Parallelism](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/02_architectural_evolution/04_scaling_to_multi_gpu.md)

### 🔹 Phần 3: Phân Tích Tối Ưu & Đánh Đổi Kỹ Thuật (`03_deep_tradeoffs_and_alternatives/`)
Hiểu rõ ranh giới áp dụng của từng công nghệ, tránh việc dùng sai công cụ gây lãng phí tài nguyên:
- [01. Ma trận so sánh vLLM vs Ollama vs TGI vs TensorRT-LLM vs SGLang](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/03_deep_tradeoffs_and_alternatives/01_engine_comparison_matrix.md)
- [02. Khi nào dùng Docker Compose? Khi nào bắt buộc lên Kubernetes?](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/03_deep_tradeoffs_and_alternatives/02_docker_compose_vs_kubernetes.md)
- [03. Toàn cảnh Quantization: AWQ vs GPTQ vs GGUF vs FP8 vs BF16](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/03_deep_tradeoffs_and_alternatives/03_quantization_landscape.md)
- [04. Tại sao chọn LiteLLM Proxy làm API Gateway tập trung?](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/03_deep_tradeoffs_and_alternatives/04_gateway_selection_litellm.md)

### 🔹 Phần 4: Sổ Tay Xử Lý Sự Cố Thực Chiến (`04_production_troubleshooting/`)
Giải quyết các lỗi thường gặp trong môi trường vận hành thực tế:
- [01. Quy trình xử lý lỗi CUDA Out Of Memory (OOM)](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/04_production_troubleshooting/01_cuda_oom_debugging.md)
- [02. Điều tra & gỡ nghẽn hiệu năng (Performance Bottlenecks)](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/04_production_troubleshooting/02_performance_bottlenecks.md)
- [03. Các cạm bẫy triển khai kinh điển (Docker IPC, Driver Mismatch, Rate Limit)](file:///c:/Users/nhatm/Downloads/Projects/Self-hosted-LLM-Serving-Platform-v-i-Docker-Compose-Monitoring/learning/04_production_troubleshooting/03_common_deployment_pitfalls.md)

---

## 💡 Phương Pháp Học Hiệu Quả
1. **Đọc hiểu nguyên lý trước**: Đọc mục `01_core_concepts` để hiểu dòng chảy dữ liệu từ RAM lên VRAM GPU.
2. **Đối chiếu với Code thực tế**: Mở song song `docker-compose.yml` và `config/` để kiểm chứng các giải thích trong mục `02_architectural_evolution`.
3. **Thực hành đo lường**: Chạy `python scripts/test_request.py` và `python scripts/benchmark_llm.py`, đồng thời mở Grafana tại `http://localhost:3000` để quan sát trực tiếp các biểu đồ biến thiên theo thời gian thực.
