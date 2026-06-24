#!/usr/bin/env python3
"""
Run this ON THE LENOVO to verify connectivity to the GPU node (main PC).
Usage: python test_connection.py
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from config import GPU_NODE_HOST, GPU_NODE_PORT, OLLAMA_MODEL

URL = f"http://{GPU_NODE_HOST}:{GPU_NODE_PORT}"

OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def test_health():
    print(f"[1/3] Reaching GPU node at {URL} ...")
    try:
        r = httpx.get(f"{URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"  {OK} Node online. Models available: {models or 'none'}")
        return models
    except httpx.ConnectError:
        print(f"  {FAIL} Cannot connect to {URL}")
        print("     → Verify OLLAMA_HOST=0.0.0.0:11434 on the main PC")
        print("     → Check firewall rules on the main PC (port 11434 TCP)")
        return None
    except Exception as e:
        print(f"  {FAIL} Unexpected error: {e}")
        return None


def test_model(models: list):
    print(f"[2/3] Checking model '{OLLAMA_MODEL}' ...")
    if models is None:
        print(f"  {FAIL} Skipped (node unreachable)")
        return False
    if OLLAMA_MODEL not in models:
        print(f"  {FAIL} Model not found on GPU node")
        print(f"     → Pull it on the main PC: ollama pull {OLLAMA_MODEL}")
        return False
    print(f"  {OK} Model present")
    return True


def test_inference():
    print(f"[3/3] Running test inference ...")
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": "Reply with exactly: PING_OK"}],
        "stream": False,
    }
    try:
        r = httpx.post(f"{URL}/api/chat", json=payload, timeout=90)
        r.raise_for_status()
        reply = r.json()["message"]["content"]
        print(f"  {OK} Inference works. Got: {reply[:120]!r}")
        return True
    except httpx.TimeoutException:
        print(f"  {FAIL} Timed out — model might still be loading, try again in 30s")
        return False
    except Exception as e:
        print(f"  {FAIL} Failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 52)
    print("  Hermes — GPU Node Connectivity Test")
    print("=" * 52)
    models = test_health()
    model_ok = test_model(models or [])
    if models and model_ok:
        test_inference()
    print("=" * 52)
