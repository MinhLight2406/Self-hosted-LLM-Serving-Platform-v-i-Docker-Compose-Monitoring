# ==============================================================================
# Makefile - Self-hosted LLM Serving Platform Control & Operations
# ==============================================================================

.PHONY: help up up-cpu down logs ps pull-model test bench healthcheck clean

help:
	@echo "======================================================================"
	@echo "  Self-hosted LLM Serving Platform - Command CheatSheet"
	@echo "======================================================================"
	@echo "  make up          : Khởi động toàn bộ stack GPU (vLLM + Ollama + Gateway + Monitoring)"
	@echo "  make up-cpu      : Khởi động stack CPU (Ollama + Gateway + Prometheus + Grafana)"
	@echo "  make down        : Tắt và xóa toàn bộ containers"
	@echo "  make logs        : Xem live log của toàn bộ hệ thống"
	@echo "  make ps          : Kiểm tra trạng thái các containers"
	@echo "  make pull-model  : Tải model mẫu vào Ollama (mặc định llama3.2:3b)"
	@echo "  make healthcheck : Chạy script kiểm tra liveness/readiness của từng service"
	@echo "  make test        : Gửi request thử nghiệm (streaming & non-streaming)"
	@echo "  make bench       : Chạy stress-test benchmark đo TTFT và Throughput"
	@echo "  make clean       : Xóa dữ liệu volume và cache rác"
	@echo "======================================================================"

up:
	docker compose up -d

up-cpu:
	docker compose -f docker-compose.cpu.yml up -d

down:
	docker compose down --remove-orphans

down-cpu:
	docker compose -f docker-compose.cpu.yml down --remove-orphans

logs:
	docker compose logs -f

logs-vllm:
	docker compose logs -f vllm-engine

logs-gateway:
	docker compose logs -f litellm-gateway

ps:
	docker compose ps

pull-model:
	docker exec -it llm-serving-ollama ollama pull llama3.2:3b

healthcheck:
	python scripts/healthcheck.py

test:
	python scripts/test_request.py

bench:
	python scripts/benchmark_llm.py --concurrency 4 --requests 20

clean:
	docker compose down -v
