# 03. Quy Trình Thêm & Thay Đổi Model Mới (Hands-on Model Migration)

Khi vận hành một nền tảng LLM serving thực tế, bạn sẽ thường xuyên phải cập nhật model (ví dụ: chuyển từ `Qwen2.5-7B` sang `Llama-3.1-8B`, hoặc triển khai model reasoning mới như `DeepSeek-R1-Distill-Qwen-7B`). 

Tài liệu này hướng dẫn quy trình 5 bước chuẩn mực để thay đổi model mà không gây lỗi hệ thống.

---

## Bước 1: Tính Toán & Đánh Giá Tương Thích VRAM
Trước khi thay đổi bất kỳ file cấu hình nào, hãy áp dụng công thức từ bài học `03_vram_estimation_formula.md`:
- Xác định số lượng tham số ($P$) và định dạng Quantization (AWQ 4-bit, FP8 hay BF16).
- Kiểm tra dung lượng VRAM thực tế trên máy chủ.
- **Quy tắc an toàn**: $\text{Dung lượng file weights} + 4\text{ GB} \le \text{VRAM vật lý của GPU}$.

---

## Bước 2: Cập Nhật Biến Môi Trường Trong `.env`

Mở file `.env` và sửa dòng `VLLM_MODEL`:

```bash
# Ví dụ 1: Chuyển sang mô hình Llama-3.1-8B-Instruct nén AWQ
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-8B-Instruct-quantized.w4a16

# Ví dụ 2: Chuyển sang mô hình DeepSeek R1 Distill Qwen 7B AWQ
# VLLM_MODEL=casperhansen/deepseek-r1-distill-qwen-7b-awq

# Đảm bảo context length phù hợp với VRAM
VLLM_MAX_MODEL_LEN=4096
```

> **Lưu ý với Gated Models**: Nếu bạn dùng các model của Meta (Llama-3/3.1) hoặc Google (Gemma-2), bạn bắt buộc phải điền `HF_TOKEN` đã được cấp quyền truy cập trên trang chủ Hugging Face.

---

## Bước 3: Cập Nhật Định Tuyến Trong `config/litellm/config.yaml`

Khai báo model mới vào danh sách `model_list`:

```yaml
model_list:
  - model_name: default-llm
    litellm_params:
      model: openai/neuralmagic/Meta-Llama-3.1-8B-Instruct-quantized.w4a16
      api_base: http://vllm-engine:8000/v1
      api_key: "none"
      rpm: 1000
      timeout: 120
```

> **Tại sao không đổi `model_name` của client?**: Bằng cách giữ nguyên định danh alias `default-llm` cho người dùng bên ngoài, toàn bộ các ứng dụng Frontend, Chatbot, Agent của công ty vẫn hoạt động bình thường mà không cần lập trình viên ứng dụng phải sửa lại mã nguồn!

---

## Bước 4: Hiểu Về Chat Template & Tokenizer Special Tokens

Một trong những lỗi nguy hiểm nhất khi đổi model là câu trả lời bị lặp từ hoặc xuất hiện các ký tự lạ như `<|im_start|>` hay `<|start_header_id|>`.
- **Nguyên nhân**: Mỗi dòng họ mô hình có một khuôn mẫu hội thoại (Chat Template) riêng:
  - **Qwen family**: Dùng chuẩn ChatML (`<|im_start|>system...<|im_end|>`).
  - **Llama 3 family**: Dùng chuẩn Llama-3 (`<|begin_of_text|><|start_header_id|>user<|end_header_id|>...<|eot_id|>`).
- **Cách xử lý trong vLLM**: vLLM tự động đọc file `tokenizer_config.json` và `chat_template.json` tải từ HuggingFace repo để áp dụng đúng template qua nhân Jinja2. Bạn không cần phải ghép chuỗi (string concatenation) thủ công!

---

## Bước 5: Khởi Động Lại Service & Xác Minh

Chạy các lệnh sau:

```bash
# 1. Tải lại cấu hình và khởi động lại container vLLM & Gateway
docker compose up -d --force-recreate vllm-engine litellm-gateway

# 2. Theo dõi tiến trình tải weights mô hình vào VRAM
docker compose logs -f vllm-engine

# 3. Khi vLLM báo "Application startup complete", chạy script kiểm thử
python scripts/test_request.py
```
