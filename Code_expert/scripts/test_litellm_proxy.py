#!/usr/bin/env python3
"""Test whether the LiteLLM proxy is running and can serve Anthropic-format requests.

Uses only the Python standard library (no ``requests`` / ``openai`` dependency).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ── Load .env from project root ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass  # fallback: rely on env vars being set externally


def main() -> None:
    base_url = os.getenv("ANTHROPIC_BASE_URL", "http://localhost:4000")
    master_key = os.getenv("LITELLM_MASTER_KEY", "sk-local-zipfix-key")
    model = os.getenv("MODEL", "gpt-4o-mini")

    url = f"{base_url}/v1/messages"
    payload = json.dumps({
        "model": model,
        "max_tokens": 512,
        "temperature": 0,
        "messages": [
            {"role": "user", "content": "Reply with exactly: proxy works"}
        ],
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {master_key}",
        "x-api-key": master_key,
        "anthropic-version": "2023-06-01",
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        print(f"FAIL – Could not reach LiteLLM proxy at {base_url}")
        print(f"       {exc}")
        print("       ➜  Start the proxy first:  ./scripts/start_litellm.sh")
        sys.exit(1)
    except Exception as exc:
        print(f"FAIL – Unexpected error: {exc}")
        sys.exit(1)

    # Extract text from Anthropic-format response
    text = ""
    for block in body.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")

    if "proxy works" in text.lower():
        print("PASS ✅  LiteLLM proxy is running and responding correctly.")
        print(f"         Model: {model}")
        print(f"         Response: {text.strip()}")
    else:
        print(f"FAIL ❌  Proxy responded but answer was unexpected:")
        print(f"         {text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
