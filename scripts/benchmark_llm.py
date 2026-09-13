#!/usr/bin/env python3
"""
Benchmark & Load Testing Tool for LLM Serving Stack.
Measures:
  - Time To First Token (TTFT): min, median (p50), p95, p99, max
  - Time Per Output Token (TPOT / Inter-Token Latency)
  - End-to-End Latency
  - Token Generation Throughput (tokens/second)
  - Success / Error Rate under concurrency

Runs using Python standard library (no extra pip packages needed).
Secured: Dynamically loads master key from environment or .env without hardcoding plain-text secrets.
"""

import os
import sys
import json
import time
import math
import argparse
import statistics
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_env_file():
    """Tự động đọc file .env ở thư mục gốc nếu biến môi trường chưa được set"""
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    ]
    for p in env_paths:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass
            break

load_env_file()

PROMPT_BANK = [
    "What is the mathematical formulation of self-attention in Transformers?",
    "Explain how continuous batching improves GPU utilization in LLM serving.",
    "Describe the difference between PagedAttention and traditional virtual memory paging.",
    "Why is LLM decoding memory-bandwidth bound rather than compute bound?",
    "How does 4-bit AWQ quantization maintain perplexity while reducing VRAM footprint?",
]

def mask_secret(secret):
    if not secret:
        return "<none>"
    if len(secret) <= 8:
        return "***"
    return secret[:4] + "..." + secret[-4:]

def percentile(data, p):
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1

def send_streaming_request(req_id, url, api_key, model, prompt, max_tokens):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise expert engineer."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "stream": True
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    t_start = time.time()
    t_first_token = None
    tokens_generated = 0
    error = None

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    chunk_str = line[6:].strip()
                    if chunk_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_str)
                        delta = chunk["choices"][0].get("delta", {})
                        if delta.get("content"):
                            if t_first_token is None:
                                t_first_token = time.time()
                            tokens_generated += 1
                    except Exception:
                        pass
        t_end = time.time()
    except Exception as e:
        t_end = time.time()
        error = str(e)

    total_latency = t_end - t_start
    ttft = (t_first_token - t_start) if t_first_token else total_latency
    decode_time = max(t_end - (t_first_token or t_end), 0.001)
    tpot = (decode_time / tokens_generated) if tokens_generated > 0 else 0

    return {
        "req_id": req_id,
        "success": error is None and tokens_generated > 0,
        "total_latency": total_latency,
        "ttft": ttft,
        "decode_time": decode_time,
        "tokens": tokens_generated,
        "tpot": tpot,
        "error": error
    }

def run_benchmark(url, api_key, model, total_requests, concurrency, max_tokens):
    print("=" * 70)
    print("  LLM SERVING BENCHMARK & STRESS TEST")
    print("=" * 70)
    print(f"Target URL       : {url}")
    print(f"Target Model     : {model}")
    print(f"Auth Token       : {mask_secret(api_key)}")
    print(f"Total Requests   : {total_requests}")
    print(f"Concurrency      : {concurrency}")
    print(f"Max Output Tokens: {max_tokens}")
    print("-" * 70)
    print("Starting load test...")

    bench_start = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for i in range(total_requests):
            prompt = PROMPT_BANK[i % len(PROMPT_BANK)]
            futures.append(executor.submit(send_streaming_request, i, url, api_key, model, prompt, max_tokens))

        completed = 0
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            completed += 1
            status_char = "." if res["success"] else "X"
            sys.stdout.write(status_char)
            sys.stdout.flush()
            if completed % 50 == 0:
                print(f" [{completed}/{total_requests}]")

    bench_duration = time.time() - bench_start
    print("\n" + "-" * 70)

    success_results = [r for r in results if r["success"]]
    failed_results = [r for r in results if not r["success"]]

    if not success_results:
        print("[!] All requests failed. Please check endpoint connectivity and API keys.")
        for f in failed_results[:3]:
            print(f"    Error sample: {f['error']}")
        return

    ttft_list = [r["ttft"] * 1000 for r in success_results] # ms
    tpot_list = [r["tpot"] * 1000 for r in success_results] # ms
    latency_list = [r["total_latency"] for r in success_results] # s
    total_tokens = sum(r["tokens"] for r in success_results)
    gen_throughput = total_tokens / bench_duration if bench_duration > 0 else 0

    print("                 BENCHMARK RESULTS REPORT")
    print("=" * 70)
    print(f"Total Test Duration      : {bench_duration:.2f} seconds")
    print(f"Completed Requests       : {len(results)} (Success: {len(success_results)}, Failed: {len(failed_results)})")
    print(f"Success Rate             : {(len(success_results) / len(results)) * 100:.1f} %")
    print(f"Total Generated Tokens   : {total_tokens} tokens")
    print(f"System Output Throughput : {gen_throughput:.2f} tokens/second")
    print("-" * 70)
    print("TIME TO FIRST TOKEN (TTFT - Prefill Latency):")
    print(f"  Min   : {min(ttft_list):.1f} ms")
    print(f"  Mean  : {statistics.mean(ttft_list):.1f} ms")
    print(f"  p50   : {percentile(ttft_list, 50):.1f} ms")
    print(f"  p95   : {percentile(ttft_list, 95):.1f} ms")
    print(f"  p99   : {percentile(ttft_list, 99):.1f} ms")
    print(f"  Max   : {max(ttft_list):.1f} ms")
    print("-" * 70)
    print("TIME PER OUTPUT TOKEN (TPOT - Inter-Token Latency):")
    print(f"  Mean  : {statistics.mean(tpot_list):.2f} ms/token")
    print(f"  p50   : {percentile(tpot_list, 50):.2f} ms/token")
    print(f"  p95   : {percentile(tpot_list, 95):.2f} ms/token")
    print("-" * 70)
    print("END-TO-END REQUEST DURATION:")
    print(f"  Mean  : {statistics.mean(latency_list):.2f} s")
    print(f"  p95   : {percentile(latency_list, 95):.2f} s")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="LLM Inference Load Benchmark")
    parser.add_argument("--url", default=os.environ.get("LITELLM_GATEWAY_URL", "http://localhost:4000/v1/chat/completions"))
    parser.add_argument("--key", default=os.environ.get("LITELLM_MASTER_KEY", ""), help="API Key (reads from .env or LITELLM_MASTER_KEY)")
    parser.add_argument("--model", default=os.environ.get("TARGET_MODEL", "default-llm"))
    parser.add_argument("--requests", type=int, default=20, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=4, help="Number of concurrent client workers")
    parser.add_argument("--tokens", type=int, default=100, help="Max tokens to generate per request")
    args = parser.parse_args()

    if not args.key:
        print("[!] Canh bao: Khong tim thay API Key! Vui long cung cap --key hoac dat LITELLM_MASTER_KEY trong file .env.")

    run_benchmark(args.url, args.key, args.model, args.requests, args.concurrency, args.tokens)

if __name__ == "__main__":
    main()
