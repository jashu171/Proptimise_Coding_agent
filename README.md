# 🔧 Code Expert Agent

> **AI-powered test-driven code repair** built with **Claude Agent SDK** for the Proptimise AI Agentic Engineer take-home assessment.

---

## What is  Code Expert Agent?

ZipFix Agent is a fully automated repair pipeline that:

1. Accepts a **zipped Python project** containing failing tests.
2. Uses an **AI agent** (powered by Claude Agent SDK) to read files, understand failures, and apply minimal source-code fixes.
3. Iteratively re-runs `pytest` until all tests pass.
4. Produces a **JSON result** and a **Markdown report** summarising what changed.

---

## Why This Satisfies the Proptimise Assessment

| Requirement | How ZipFix Agent Meets It |
|---|---|
| Use Claude Agent SDK as core framework | `claude_agent_sdk.query()` + `ClaudeAgentOptions` are the only agent interface (see `src/zipfix_agent/agent.py`) |
| No direct OpenAI SDK calls in agent code | Agent code imports nothing from `openai` – all LLM traffic routes through Claude Agent SDK |
| No OpenRouter | LiteLLM proxy runs locally – no third-party routing |
| Support OpenAI GPT models | LiteLLM translates Anthropic-format requests into OpenAI API calls |
| Read / Edit / Bash tools | Granted via `allowed_tools=["Bash", "Read", "Edit"]` |
| Iterative repair loop | Up to 3 iterations with early stopping on success |

---

## Architecture

```
┌──────────────────────────┐
│  Claude Agent SDK        │
│  (query / stream)        │
└───────────┬──────────────┘
            │  ANTHROPIC_BASE_URL
            ▼
┌──────────────────────────┐
│  http://localhost:4000   │
│  LiteLLM Proxy           │
│  (Anthropic-compatible)  │
└───────────┬──────────────┘
            │  OPENAI_API_KEY
            ▼
┌──────────────────────────┐
│  OpenAI GPT Model        │
│  (gpt-4o-mini / gpt-4o)  │
└──────────────────────────┘
```

**Key routing mechanism:**

- `ANTHROPIC_BASE_URL=http://localhost:4000` tells Claude Agent SDK to send requests to LiteLLM instead of `api.anthropic.com`.
- `ANTHROPIC_API_KEY=""` (blank) prevents any fallback to Anthropic's real API.
- `ANTHROPIC_AUTH_TOKEN=sk-local-zipfix-key` authenticates with LiteLLM using its master key.
- LiteLLM is configured (via `litellm_config.yaml`) to forward all inference to OpenAI using `OPENAI_API_KEY`.

---

## Project Structure

```
zipfix-agent/
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── litellm_config.yaml
│
├── prompts/
│   └── system_prompt.txt
│
├── src/
│   └── zipfix_agent/
│       ├── __init__.py
│       ├── agent.py            # Claude Agent SDK wrapper
│       ├── config.py           # Centralised env-var config
│       ├── repair_loop.py      # Orchestration pipeline
│       ├── schemas.py          # Pydantic data models
│       ├── checks.py           # pytest + compile checks
│       ├── unzipper.py         # Safe zip extraction
│       ├── scoring.py          # Quality scoring
│       ├── tools.py            # File hashing / diff helpers
│       └── readme_writer.py    # Markdown report generator
│
├── scripts/
│   ├── start_litellm.sh        # Start the LiteLLM proxy
│   ├── test_litellm_proxy.py   # Health-check the proxy
│   ├── test_claude_agent_sdk.py# End-to-end SDK routing test
│   └── run_agent.py            # CLI entry point
│
├── dataset/
│   └── cases/                  # Place your zipped test cases here
│
└── outputs/
    ├── repaired_projects/      # Extracted + repaired projects
    ├── json_results/           # Per-project JSON results
    └── reports/                # Markdown reports
```

---

## Setup

### 1. Clone & create virtual environment

```bash
cd zipfix-agent
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -e .
pip install "litellm[proxy]"
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your real **OpenAI API key**:

```
OPENAI_API_KEY=sk-your-real-openai-key
```

> **Important:** Leave `ANTHROPIC_API_KEY=""` blank – this ensures Claude Agent SDK routes through the local proxy and never hits Anthropic directly.

---

## Running

### Step 1 — Start LiteLLM proxy

```bash
chmod +x scripts/start_litellm.sh
./scripts/start_litellm.sh
```

You should see:

```
🚀  Starting LiteLLM proxy on http://localhost:4000
```

> Keep this terminal running.

### Step 2 — Test the proxy (new terminal)

```bash
source .venv/bin/activate
python scripts/test_litellm_proxy.py
```

Expected output:

```
PASS ✅  LiteLLM proxy is running and responding correctly.
```

### Step 3 — Test Claude Agent SDK routing

```bash
python scripts/test_claude_agent_sdk.py
```

Expected output:

```
PASS ✅  Claude Agent SDK → LiteLLM → OpenAI pipeline works.
```

### Step 4 — Run the repair agent

```bash
python scripts/run_agent.py ./dataset/cases/case_01_wrong_operator/input_project.zip
```

Or run interactively:

```bash
python scripts/run_agent.py
# Enter zip file path: ./dataset/cases/case_01/input_project.zip
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` on localhost:4000 | Start the LiteLLM proxy first (`./scripts/start_litellm.sh`) |
| `401 Unauthorized` | Ensure `LITELLM_MASTER_KEY` and `ANTHROPIC_AUTH_TOKEN` match in `.env` |
| `Model not found` | Check that `MODEL` in `.env` matches a `model_name` in `litellm_config.yaml` |
| Claude SDK hits Anthropic directly | Confirm `ANTHROPIC_BASE_URL=http://localhost:4000` is loaded and `ANTHROPIC_API_KEY=""` is blank |
| Output token / credit errors | Lower `CLAUDE_CODE_MAX_OUTPUT_TOKENS` in `.env` |
| `ModuleNotFoundError: claude_agent_sdk` | Run `pip install -e .` to install the project and its dependencies |
| `litellm: command not found` | Run `pip install "litellm[proxy]"` |

---

## How It Works (Repair Loop)

```
1. Unzip  →  Extract the project safely
2. Check  →  Run pytest + compile check (baseline score)
3. Agent  →  Claude Agent SDK reads code, diagnoses bugs, applies fixes
4. Verify →  Re-run pytest + compile check
5. Loop   →  Repeat up to 3 times if tests still fail
6. Report →  Save JSON result + Markdown report
```

The agent follows strict rules (see `prompts/system_prompt.txt`):

- Never edit test files
- Prefer small diffs
- Fix root causes, not symptoms
- Re-run tests after every edit

---

## License

MIT — built for the Proptimise AI Agentic Engineer assessment.
