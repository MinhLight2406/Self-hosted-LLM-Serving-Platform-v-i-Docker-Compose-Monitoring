#!/usr/bin/env python3
"""
Test client to verify LLM inference via LiteLLM Gateway.
Supports both non-streaming and streaming responses.
Pure standard library implementation with zero third-party dependencies.
Secured: Automatically resolves API key from environment or .env file without hardcoding.
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

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

# Nạp .env an toàn
load_env_file()

DEFAULT_GATEWAY_URL = os.environ.get("LITELLM_GATEWAY_URL", "http://localhost:4000/v1/chat/completions")
DEFAULT_API_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
DEFAULT_MODEL = os.environ.get("TARGET_MODEL", "default-llm")

def mask_secret(secret):
    if not secret:
        return "<none>"
    if len(secret) <= 8:
        return "***"
    return secret[:4] + "..." + secret[-4:]

def test_non_streaming(url, api_key, model, prompt):
    print("\n" + "=" * 60)
    print(f"[*] Testing Non-Streaming Inference on '{model}'")
    print(f"[*] Gateway URL : {url}")
    print(f"[*] Auth Token  : {mask_secret(api_key)}")
    print(f"[*] Prompt      : \"{prompt}\"")
    print("=" * 60)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful and concise AI assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 150
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

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            elapsed = time.time() - start_time
            result = json.loads(resp.read().decode("utf-8"))
            answer = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})

            print("\n--- Model Response ---")
            print(answer.strip())
            print("\n--- Performance Stats ---")
            print(f"Total Time: {elapsed:.2f} s")
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                tps = completion_tokens / elapsed if elapsed > 0 else 0
                print(f"Prompt Tokens: {prompt_tokens}")
                print(f"Completion Tokens: {completion_tokens}")
                print(f"Throughput: {tps:.2f} tokens/second")
    except urllib.error.HTTPError as e:
        print(f"[!] HTTP Error {e.code}: {e.read().decode('utf-8', errors='replace')}")
    except Exception as e:
        print(f"[!] Request failed: {e}")

def test_streaming(url, api_key, model, prompt):
    print("\n" + "=" * 60)
    print(f"[*] Testing Streaming Inference on '{model}' (Measuring TTFT)")
    print(f"[*] Gateway URL : {url}")
    print(f"[*] Auth Token  : {mask_secret(api_key)}")
    print(f"[*] Prompt      : \"{prompt}\"")
    print("=" * 60)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful and concise AI assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 150,
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

    start_time = time.time()
    first_token_time = None
    generated_tokens = 0

    print("\n--- Streaming Output ---")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    content_str = line[6:].strip()
                    if content_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(content_str)
                        delta = chunk["choices"][0].get("delta", {})
                        text_piece = delta.get("content", "")
                        if text_piece:
                            if first_token_time is None:
                                first_token_time = time.time()
                            sys.stdout.write(text_piece)
                            sys.stdout.flush()
                            generated_tokens += 1
                    except Exception:
                        pass

        total_time = time.time() - start_time
        ttft = (first_token_time - start_time) if first_token_time else total_time
        decode_time = total_time - ttft
        tpot = (decode_time / generated_tokens * 1000) if generated_tokens > 0 else 0
        tps = (generated_tokens / decode_time) if decode_time > 0 else 0

        print("\n\n--- Streaming Metrics ---")
        print(f"Time To First Token (TTFT): {ttft * 1000:.2f} ms")
        print(f"Generated Tokens: {generated_tokens}")
        print(f"Time Per Output Token (TPOT/ITL): {tpot:.2f} ms/token")
        print(f"Decode Throughput: {tps:.2f} tokens/s")
        print(f"Total Latency: {total_time:.2f} s")
    except urllib.error.HTTPError as e:
        print(f"\n[!] HTTP Error {e.code}: {e.read().decode('utf-8', errors='replace')}")
    except Exception as e:
        print(f"\n[!] Streaming failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Test LLM Serving Endpoint")
    parser.add_argument("--url", default=DEFAULT_GATEWAY_URL, help="Gateway URL")
    parser.add_argument("--key", default=DEFAULT_API_KEY, help="API Key (default: reads from .env or LITELLM_MASTER_KEY)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name")
    parser.add_argument("--prompt", default="Explain the difference between Prefill and Decode phase in LLM inference in 2 short bullet points.", help="Prompt text")
    parser.add_argument("--stream", action="store_true", help="Run streaming test")
    args = parser.parse_args()

    if not args.key:
        print("[!] Canh bao: Khong tim thay API Key! Vui long cung cap --key hoac dat LITELLM_MASTER_KEY trong file .env.")

    if args.stream:
        test_streaming(args.url, args.key, args.model, args.prompt)
    else:
        test_non_streaming(args.url, args.key, args.model, args.prompt)
        test_streaming(args.url, args.key, args.model, args.prompt)

if __name__ == "__main__":
    main()
