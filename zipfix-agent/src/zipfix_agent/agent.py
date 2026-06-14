"""Core agent wrapper – routes requests through Claude Agent SDK.

The SDK respects ``ANTHROPIC_BASE_URL`` so all traffic flows through the
local LiteLLM proxy at ``http://localhost:4000`` and from there to
OpenAI GPT models.  **No OpenAI SDK calls are made here.**

All agent actions (tool calls, reads, edits, bash commands) are logged
to the terminal in real time so the user can see what the AI is doing.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from zipfix_agent.config import MAX_TURNS, MODEL

console = Console()


# ── Real-time logging helpers ────────────────────────────────────────────────


def _log_tool_use(block: ToolUseBlock, agent_label: str) -> None:
    """Log a tool invocation to the terminal with rich formatting."""
    name = block.name
    inp = block.input or {}

    if name == "Bash":
        cmd = inp.get("command", "(unknown command)")
        # Truncate very long commands
        if len(cmd) > 200:
            cmd = cmd[:200] + "..."
        console.print(f"  [bold yellow]⚙ {agent_label}[/] → [cyan]Bash[/]: [dim]{cmd}[/dim]")

    elif name == "Read":
        file_path = inp.get("file_path", inp.get("path", "(unknown file)"))
        console.print(f"  [bold yellow]⚙ {agent_label}[/] → [blue]Read[/]: [dim]{file_path}[/dim]")

    elif name == "Edit":
        file_path = inp.get("file_path", inp.get("path", "(unknown file)"))
        console.print(f"  [bold yellow]⚙ {agent_label}[/] → [green]Edit[/]: [dim]{file_path}[/dim]")

    elif name == "Write":
        file_path = inp.get("file_path", inp.get("path", "(unknown file)"))
        console.print(f"  [bold yellow]⚙ {agent_label}[/] → [magenta]Write[/]: [dim]{file_path}[/dim]")

    else:
        # Any other tool
        console.print(f"  [bold yellow]⚙ {agent_label}[/] → [white]{name}[/]: [dim]{inp}[/dim]")


def _log_tool_result(block: ToolResultBlock, agent_label: str) -> None:
    """Log a tool result – show errors, truncate long output."""
    if block.is_error:
        content = str(block.content or "")[:300]
        console.print(f"  [bold red]✖ {agent_label}[/] ← [red]Error[/]: [dim]{content}[/dim]")
    else:
        # Show a brief snippet of the result
        content = str(block.content or "")
        if len(content) > 150:
            content = content[:150] + "..."
        if content:
            console.print(f"  [dim]  ← Result: {content}[/dim]")


def _log_text(block: TextBlock, agent_label: str) -> None:
    """Log agent text output – truncate long responses."""
    text = block.text.strip()
    if not text:
        return
    # Show first 300 chars of agent thinking/response
    display = text[:300] + ("..." if len(text) > 300 else "")
    console.print(f"  [bold white]💬 {agent_label}[/]: [dim]{display}[/dim]")


def _process_message(message: object, agent_label: str, collected_text: list[str]) -> None:
    """Process a single streamed message and log its contents."""
    # ── AssistantMessage: has content blocks ──
    if hasattr(message, "content") and isinstance(getattr(message, "content", None), list):
        for block in message.content:
            # Text block
            if hasattr(block, "text") and isinstance(block, TextBlock):
                collected_text.append(block.text)
                _log_text(block, agent_label)

            # Tool use block (Bash, Read, Edit, Write)
            elif hasattr(block, "name") and hasattr(block, "input"):
                _log_tool_use(block, agent_label)

            # Tool result block
            elif hasattr(block, "tool_use_id") and hasattr(block, "is_error"):
                _log_tool_result(block, agent_label)

    # ── ResultMessage: final result ──
    if hasattr(message, "result"):
        result_text = str(getattr(message, "result", ""))
        if result_text:
            console.print(f"  [bold green]✔ {agent_label} result[/]: [dim]{result_text[:200]}[/dim]")


# ── Agent runners ────────────────────────────────────────────────────────────


async def run_repair_agent(
    workspace_path: Path,
    prompt: str,
    system_prompt: str,
) -> str:
    """Send *prompt* to the fixer agent and return the full text response.

    The fixer agent is configured with Bash, Read, Edit, and Write tools
    so it can inspect the project, run pytest, apply fixes, and create files.
    All tool actions are logged to the terminal in real time.
    """
    model = os.getenv("MODEL", MODEL)
    max_turns = int(os.getenv("CLAUDE_CODE_MAX_TURNS", str(MAX_TURNS)))

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=["Bash", "Read", "Edit", "Write"],
        max_turns=max_turns,
        cwd=str(workspace_path),
        thinking={"type": "disabled"},
    )

    console.print()
    console.print(Panel(
        f"[bold cyan]⚡ Fixer Agent[/]\n"
        f"  Model: {model}\n"
        f"  Tools: Bash, Read, Edit, Write\n"
        f"  Max turns: {max_turns}\n"
        f"  Working dir: {workspace_path}",
        border_style="cyan",
    ))

    collected_text: list[str] = []
    agent_label = "Fixer"

    try:
        async for message in query(prompt=prompt, options=options):
            _process_message(message, agent_label, collected_text)
    except Exception as exc:
        console.print(f"  [bold red]✖ Fixer Agent error:[/] {exc}")
        raise

    full_response = "\n".join(collected_text)
    console.print(f"\n  [bold green]✔ Fixer Agent finished[/]  ({len(full_response)} chars)")
    return full_response


async def run_planner_agent(
    workspace_path: Path,
    prompt: str,
    system_prompt: str,
) -> str:
    """Send *prompt* to the planner subagent and return the full text response.

    The planner only gets Read + Bash tools – it analyses but never edits.
    All tool actions are logged to the terminal in real time.
    """
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=["Bash", "Read"],
        max_turns=6,
        cwd=str(workspace_path),
        thinking={"type": "disabled"},
    )

    console.print()
    console.print(Panel(
        f"[bold magenta]🔍 Planner Agent (subagent)[/]\n"
        f"  Tools: Bash, Read\n"
        f"  Max turns: 3\n"
        f"  Working dir: {workspace_path}",
        border_style="magenta",
    ))

    collected_text: list[str] = []
    agent_label = "Planner"

    try:
        async for message in query(prompt=prompt, options=options):
            _process_message(message, agent_label, collected_text)
    except Exception as exc:
        console.print(f"  [bold red]✖ Planner Agent error:[/] {exc}")
        raise

    full_response = "\n".join(collected_text)
    console.print(f"\n  [bold green]✔ Planner Agent finished[/]  ({len(full_response)} chars)")
    return full_response
