#!/usr/bin/env python3
"""Verify that Claude Agent SDK can route through the local LiteLLM proxy.

Imports:
    claude_agent_sdk.query
    claude_agent_sdk.ClaudeAgentOptions

The SDK honours ``ANTHROPIC_BASE_URL`` so traffic goes to LiteLLM → OpenAI.
"""

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


async def _test() -> bool:
    model = os.getenv("MODEL", "gpt-4o-mini")

    options = ClaudeAgentOptions(
        system_prompt="You are a test assistant. Reply only with the requested exact phrase.",
        max_turns=1,
        allowed_tools=[],
        thinking={"type": "disabled"},
    )

    collected: list[str] = []

    try:
        async for message in query(
            prompt="Reply with exactly: sdk proxy works",
            options=options,
        ):
            if hasattr(message, "content"):
                for block in message.content:
                    if hasattr(block, "text"):
                        collected.append(block.text)
    except Exception as exc:
        print(f"FAIL ❌  Claude Agent SDK raised an error:")
        print(f"         {type(exc).__name__}: {exc}")
        return False

    full = " ".join(collected).lower()
    if "sdk proxy works" in full:
        print("PASS ✅  Claude Agent SDK → LiteLLM → OpenAI pipeline works.")
        print(f"         Model: {model}")
        print(f"         Response: {' '.join(collected).strip()}")
        return True
    else:
        print(f"FAIL ❌  Response did not contain expected phrase:")
        print(f"         {' '.join(collected)}")
        return False


def main() -> None:
    ok = asyncio.run(_test())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
