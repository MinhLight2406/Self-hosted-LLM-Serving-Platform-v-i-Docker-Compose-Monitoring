#!/usr/bin/env python3
"""
Healthcheck utility for the Self-hosted LLM Serving Platform.
Checks liveness, readiness, and latency for all microservices in the stack.
Runs with pure standard library (no extra pip install required).
"""

import sys
import json
import time
import urllib.request
import urllib.error

SERVICES = [
    {
        "name": "LiteLLM Gateway (Unified Proxy)",
        "url": "http://localhost:4000/health/ready",
        "alt_url": "http://localhost:4000/v1/models",
        "expected_code": 200,
        "role": "API Gateway / Smart Router",
    },
    {
        "name": "vLLM Inference Engine",
        "url": "http://localhost:8000/health",
        "alt_url": "http://localhost:8000/v1/models",
        "expected_code": 200,
        "role": "High-throughput serving (PagedAttention)",
    },
    {
        "name": "Ollama Serving Engine",
        "url": "http://localhost:11434/api/tags",
        "alt_url": None,
        "expected_code": 200,
        "role": "Lightweight / CPU / Fallback serving",
    },
    {
        "name": "Prometheus Monitoring",
        "url": "http://localhost:9090/-/ready",
        "alt_url": "http://localhost:9090/api/v1/status/runtimeinfo",
        "expected_code": 200,
        "role": "Time-Series Metrics Scraper",
    },
    {
        "name": "Grafana Visual Dashboard",
        "url": "http://localhost:3000/api/health",
        "alt_url": None,
        "expected_code": 200,
        "role": "Dashboards & Alerting UI",
    },
    {
        "name": "NVIDIA DCGM Exporter",
        "url": "http://localhost:9400/metrics",
        "alt_url": None,
        "expected_code": 200,
        "role": "GPU VRAM & Telemetry Exporter",
    },
    {
        "name": "cAdvisor Container Telemetry",
        "url": "http://localhost:8080/containers/",
        "alt_url": "http://localhost:8080/metrics",
        "expected_code": 200,
        "role": "Docker Container Resource Metrics",
    },
]

def check_endpoint(url, timeout=3.0):
    start = time.time()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "LLM-Platform-HealthCheck/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency_ms = (time.time() - start) * 1000
            return response.getcode(), latency_ms, "OK"
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - start) * 1000
        return e.code, latency_ms, f"HTTP Error {e.code}"
    except urllib.error.URLError as e:
        latency_ms = (time.time() - start) * 1000
        return None, latency_ms, str(e.reason)
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return None, latency_ms, str(e)

def main():
    print("=" * 85)
    print("  SELF-HOSTED LLM SERVING PLATFORM - STACK HEALTHCHECK")
    print("=" * 85)
    print(f"{'SERVICE':<32} | {'STATUS':<10} | {'LATENCY':<10} | {'DETAILS'}")
    print("-" * 85)

    all_healthy = True

    for svc in SERVICES:
        name = svc["name"]
        url = svc["url"]
        code, latency, msg = check_endpoint(url)

        # Fallback to alt_url if primary returned error
        if (code is None or code >= 400) and svc.get("alt_url"):
            code, latency, msg = check_endpoint(svc["alt_url"])

        if code == 200:
            status_text = "[UP]"
            latency_str = f"{latency:.1f} ms"
            detail = f"Healthy ({svc['role']})"
        else:
            all_healthy = False
            status_text = "[DOWN]"
            latency_str = "---"
            detail = f"{msg} ({url})"

        print(f"{name:<32} | {status_text:<10} | {latency_str:<10} | {detail}")

    print("=" * 85)
    if all_healthy:
        print("[SUCCESS] All core services are healthy and ready to serve traffic!")
        return 0
    else:
        print("[WARNING] Some services are not running. Run 'docker compose logs <service>' to investigate.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
