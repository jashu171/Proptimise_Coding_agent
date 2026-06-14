#!/usr/bin/env python3
"""Diagnose the complete local LLM routing pipeline.

Checks:
1. .env model/proxy settings
2. Ollama model availability
3. Ollama direct chat
4. LiteLLM Anthropic-compatible /v1/messages
5. LiteLLM OpenAI-compatible /v1/chat/completions
6. Claude Agent SDK streaming/result messages
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
OLLAMA_MODEL = "rafw007/gemma4-e2b-claude-coder"


try:
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH)
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _mask(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "<set>"
    return f"{value[:6]}...{value[-4:]}"


def _request_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, raw


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def check_env() -> None:
    _print_header("Environment")
    names = [
        "MODEL",
        "REASONING_MODEL",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "LITELLM_MASTER_KEY",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "CLAUDE_CODE_SUBAGENT_MODEL",
    ]

    print(f".env: {ENV_PATH}")
    for name in names:
        value = _env(name)
        display = value if "KEY" not in name and "TOKEN" not in name else _mask(value)
        print(f"{name}={display}")


def check_ollama_tags() -> bool:
    _print_header("Ollama Model List")
    try:
        status, body = _request_json("http://localhost:11434/api/tags", timeout=10)
    except Exception as exc:
        print(f"FAIL: cannot reach Ollama on localhost:11434: {type(exc).__name__}: {exc}")
        return False

    models = body.get("models", []) if isinstance(body, dict) else []
    names = [m.get("name", "") for m in models if isinstance(m, dict)]
    print(f"HTTP {status}")
    print("Installed models:")
    for name in names:
        print(f"- {name}")

    ok = any(name == OLLAMA_MODEL or name.startswith(f"{OLLAMA_MODEL}:") for name in names)
    print("PASS" if ok else f"FAIL: {OLLAMA_MODEL} not found")
    return ok


def check_ollama_chat() -> bool:
    _print_header("Ollama Direct 2+2")
    started = time.monotonic()
    try:
        status, body = _request_json(
            "http://localhost:11434/api/chat",
            {
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": "What is 2+2? Reply with only 4."}],
                "stream": False,
            },
            timeout=90,
        )
    except Exception as exc:
        print(f"FAIL: Ollama chat error: {type(exc).__name__}: {exc}")
        return False

    elapsed = time.monotonic() - started
    text = ""
    if isinstance(body, dict):
        text = body.get("message", {}).get("content", "")
    print(f"HTTP {status} in {elapsed:.1f}s")
    print(f"Response: {text!r}")
    ok = "4" in text
    print("PASS" if ok else "FAIL: direct Ollama response did not contain 4")
    return ok


def check_litellm_anthropic() -> bool:
    _print_header("LiteLLM Anthropic /v1/messages 2+2")
    base_url = _env("ANTHROPIC_BASE_URL", "http://localhost:4000").rstrip("/")
    master_key = _env("LITELLM_MASTER_KEY", "sk-local-zipfix-key")
    model = _env("MODEL", "local-claude-coder")
    started = time.monotonic()

    try:
        status, body = _request_json(
            f"{base_url}/v1/messages",
            {
                "model": model,
                "max_tokens": 512,
                "temperature": 0,
                "reasoning_effort": "none",
                "messages": [{"role": "user", "content": "What is 2+2? Reply with only 4."}],
            },
            {
                "Authorization": f"Bearer {master_key}",
                "x-api-key": master_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=90,
        )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"FAIL: HTTP {exc.code}: {raw[:1000]}")
        return False
    except Exception as exc:
        print(f"FAIL: LiteLLM Anthropic error: {type(exc).__name__}: {exc}")
        return False

    elapsed = time.monotonic() - started
    text = ""
    if isinstance(body, dict):
        for block in body.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
    print(f"HTTP {status} in {elapsed:.1f}s")
    print(f"Response: {text!r}")
    ok = "4" in text
    print("PASS" if ok else "FAIL: LiteLLM Anthropic response did not contain 4")
    return ok


def check_litellm_openai() -> bool:
    _print_header("LiteLLM OpenAI /v1/chat/completions 2+2")
    base_url = _env("ANTHROPIC_BASE_URL", "http://localhost:4000").rstrip("/")
    master_key = _env("LITELLM_MASTER_KEY", "sk-local-zipfix-key")
    model = _env("MODEL", "local-claude-coder")
    started = time.monotonic()

    try:
        status, body = _request_json(
            f"{base_url}/v1/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": "What is 2+2? Reply with only 4."}],
                "max_tokens": 512,
                "temperature": 0,
                "reasoning_effort": "none",
                "stream": False,
            },
            {"Authorization": f"Bearer {master_key}"},
            timeout=90,
        )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"FAIL: HTTP {exc.code}: {raw[:1000]}")
        return False
    except Exception as exc:
        print(f"FAIL: LiteLLM OpenAI error: {type(exc).__name__}: {exc}")
        return False

    elapsed = time.monotonic() - started
    text = ""
    if isinstance(body, dict):
        choices = body.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "")
    print(f"HTTP {status} in {elapsed:.1f}s")
    print(f"Response: {text!r}")
    ok = "4" in text
    print("PASS" if ok else "FAIL: LiteLLM OpenAI response did not contain 4")
    return ok


async def check_claude_sdk() -> bool:
    _print_header("Claude Agent SDK 2+2")
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except Exception as exc:
        print(f"FAIL: cannot import claude_agent_sdk: {type(exc).__name__}: {exc}")
        return False

    model = _env("MODEL", "local-claude-coder")
    timeout = int(_env("LLM_TEST_TIMEOUT_SECONDS", "120"))
    started = time.monotonic()
    collected: list[str] = []
    result_texts: list[str] = []

    options = ClaudeAgentOptions(
        system_prompt="Answer with only the requested final answer. Do not explain.",
        tools=[],
        max_turns=1,
        allowed_tools=[],
        model=model,
        thinking={"type": "disabled"},
        extra_args={"bare": None},
        include_partial_messages=True,
    )

    async def _run() -> None:
        async for message in query(
            prompt="What is 2+2? Reply with only 4.",
            options=options,
        ):
            msg_type = type(message).__name__
            print(f"SDK message: {msg_type}", flush=True)

            if hasattr(message, "content"):
                for block in getattr(message, "content", []) or []:
                    block_type = type(block).__name__
                    text = getattr(block, "text", None)
                    if text:
                        print(f"  content {block_type}: {text!r}", flush=True)
                        collected.append(text)
                    else:
                        print(f"  content {block_type}", flush=True)

            result = getattr(message, "result", None)
            if result:
                print(f"  result: {str(result)!r}", flush=True)
                if str(result) not in result_texts:
                    result_texts.append(str(result))

    try:
        await asyncio.wait_for(_run(), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"FAIL: SDK timed out after {timeout}s")
        return False
    except Exception as exc:
        print(f"FAIL: SDK error: {type(exc).__name__}: {exc}")
        return False

    elapsed = time.monotonic() - started
    unique_texts: list[str] = []
    for text in [*collected, *result_texts]:
        if text not in unique_texts:
            unique_texts.append(text)
    full = " ".join(unique_texts).strip()
    print(f"SDK completed in {elapsed:.1f}s")
    print(f"Collected: {full!r}")
    ok = "4" in full
    print("PASS" if ok else "FAIL: SDK completed but no usable text was emitted")
    return ok


async def main() -> int:
    check_env()

    results = [
        check_ollama_tags(),
        check_ollama_chat(),
        check_litellm_anthropic(),
        check_litellm_openai(),
        await check_claude_sdk(),
    ]

    _print_header("Summary")
    passed = sum(1 for ok in results if ok)
    print(f"{passed}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
