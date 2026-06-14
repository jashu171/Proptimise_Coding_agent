#!/usr/bin/env python3
"""Quick LLM smoke test: ask gpt-4o-mini what 2+2 is via Claude Agent SDK → LiteLLM."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# ── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from claude_agent_sdk import ClaudeAgentOptions, query  # noqa: E402


async def _run_query(model: str) -> str:
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful math assistant. Answer concisely.",
        tools=[],
        max_turns=1,
        allowed_tools=[],
        model=model,
        thinking={"type": "disabled"},
        extra_args={"bare": None},
    )

    collected: list[str] = []

    async for message in query(
        prompt="What is 2+2? Reply with just the number.",
        options=options,
    ):
        if hasattr(message, "content"):
            for block in message.content:
                if hasattr(block, "text"):
                    collected.append(block.text)
        result = getattr(message, "result", None)
        if result and str(result) not in collected:
            collected.append(str(result))

    return " ".join(collected).strip()


async def _test() -> bool:
    model = os.getenv("MODEL", "gpt-4o-mini")
    timeout_seconds = int(os.getenv("LLM_TEST_TIMEOUT_SECONDS", "90"))

    print(f"Testing Claude SDK route with model={model} timeout={timeout_seconds}s ...", flush=True)

    try:
        full = await asyncio.wait_for(_run_query(model), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print(f"FAIL ❌  LLM call timed out after {timeout_seconds}s")
        print("         LiteLLM/Ollama is reachable, but the model did not finish in time.")
        return False
    except Exception as exc:
        print(f"FAIL ❌  LLM call raised an error:")
        print(f"         {type(exc).__name__}: {exc}")
        return False

    if full.strip() == "4":
        print(f"PASS ✅  LLM responded correctly to 2+2")
        print(f"         Model: {model}")
        print(f"         Response: {full}")
        return True
    else:
        print(f"FAIL ❌  Unexpected response:")
        print(f"         {full}")
        return False


def main() -> None:
    ok = asyncio.run(_test())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
