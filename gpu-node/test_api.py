#!/usr/bin/env python3
"""
Quick Ollama API smoke-test.
Run this on the MAIN PC to confirm Ollama is accepting connections.
No external dependencies — uses stdlib only.
"""
import json
import sys
import urllib.request
import urllib.error

HOST  = "http://localhost:11434"
MODEL = "qwen2.5:7b"

OK   = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def test_health():
    print(f"[1/2] Checking Ollama at {HOST} ...")
    try:
        with urllib.request.urlopen(f"{HOST}/api/tags", timeout=5) as r:
            data   = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            print(f"  {OK} Online. Models: {models or 'none'}")
            return models
    except urllib.error.URLError as e:
        print(f"  {FAIL} Cannot connect: {e.reason}")
        print("     → Is Ollama running?  ollama serve")
        return None


def test_inference(models):
    print(f"[2/2] Running inference with '{MODEL}' ...")
    if models is None:
        print(f"  {FAIL} Skipped (Ollama not reachable)")
        return
    if MODEL not in models:
        print(f"  {FAIL} Model not found — run: ollama pull {MODEL}")
        return

    payload = json.dumps({
        "model":    MODEL,
        "messages": [{"role": "user", "content": "Reply with exactly: OLLAMA_OK"}],
        "stream":   False,
    }).encode()

    req = urllib.request.Request(
        f"{HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data  = json.loads(r.read())
            reply = data["message"]["content"]
            print(f"  {OK} Got: {reply[:120]!r}")
    except urllib.error.URLError as e:
        print(f"  {FAIL} Request failed: {e}")
    except KeyError:
        print(f"  {FAIL} Unexpected response format")


if __name__ == "__main__":
    print("=" * 48)
    print("  Ollama Local API Test")
    print("=" * 48)
    models = test_health()
    test_inference(models)
    print("=" * 48)
