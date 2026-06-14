### Note: To review the code, please open the **Code_expert** folder

# 🔧 Code Expert Agent

> **AI-powered, test-driven Python repair agent** built with **Claude Agent SDK + LiteLLM + Ollama** for the Proptimise AI Agentic Engineer take-home assessment.

---

## What is Code Expert Agent?

Code Expert Agent is a fully automated, test-driven Python repair pipeline. It accepts a zipped Python project with failing tests, uses an AI agent to diagnose and fix bugs, re-runs the tests after each fix, and produces a JSON result and a Markdown report.

---

## The Journey — Honest Account of What Happened

> I never stepped back. Every blocked path led to a new solution.

### Attempt 1 — Anthropic API (Claude hosted)

I tried to claim the **$5 Anthropic credit** to run Claude directly. The credit claim was **not successful**. Without API credits, calling `api.anthropic.com` was not an option.

### Attempt 2 — OpenRouter as base URL

I configured LiteLLM to route through **OpenRouter** as the backend so Claude Agent SDK could still be used. This hit **API rate limits** almost immediately, making the repair workflow unreliable and unusable for a multi-iteration agent loop.

### Final Solution — LiteLLM Proxy + Ollama (local)

I refused to stop. Instead of relying on any third-party cloud API:

- Installed **Ollama** locally and pulled `qwen2.5-coder:3b` — a capable local coding model.
- Ran **LiteLLM** as a local proxy on `http://localhost:4000`, exposing an Anthropic-compatible API surface.
- Pointed **Claude Agent SDK** at the local LiteLLM proxy via `ANTHROPIC_BASE_URL=http://localhost:4000`.

**The elegant part:** Claude Agent SDK has no idea it is talking to an Ollama model. It only sees the configured model alias `local-claude-coder`. LiteLLM owns the provider mapping and silently forwards that alias to `ollama_chat/qwen2.5-coder:3b`. The entire Claude Agent SDK control flow — tools, streaming, retry logic — works unchanged.

---

## Architecture

```
Claude Agent SDK
  │
  │  ANTHROPIC_BASE_URL=http://localhost:4000
  ▼
LiteLLM Proxy  (localhost:4000)
  │  model alias: local-claude-coder
  │  maps to → ollama_chat/qwen2.5-coder:3b
  ▼
Ollama  (localhost:11434)
  │
  ▼
qwen2.5-coder:3b  (runs 100% locally, no cloud calls)
```

**Key points:**
- `ANTHROPIC_BASE_URL=http://localhost:4000` — redirects Claude SDK to LiteLLM.
- `ANTHROPIC_API_KEY=""` — blank, prevents any fallback to real Anthropic.
- `ANTHROPIC_AUTH_TOKEN=sk-local-zipfix-key` — authenticates with LiteLLM master key.
- Claude Agent SDK never calls `api.anthropic.com` or OpenRouter.

---

## Assessment Fit

| Requirement | Implementation |
|---|---|
| Claude Agent SDK as agent framework | `claude_agent_sdk.query()` + `ClaudeAgentOptions` in `src/zipfix_agent/agent.py` |
| No direct OpenAI SDK in agent code | All LLM traffic routes through Claude Agent SDK → LiteLLM |
| No OpenRouter dependency at runtime | OpenRouter was tried and removed; final stack is fully local |
| Local model support | LiteLLM maps `local-claude-coder` → Ollama `qwen2.5-coder:3b` |
| Test-driven repair | Baseline + final `pytest` + compile checks every iteration |
| Iterative loop | Up to 3 repair iterations with early stopping on success |
| Reports | `result.json` + `README_REPORT.md` saved under `../outputs/<project>/` |

---

## Project Structure

```
Protomise-assesment/
├── inputs/                          # Zipped projects to repair
├── outputs/                         # Generated repair outputs
└── Code_expert/
    ├── README.md
    ├── pyproject.toml
    ├── litellm_config.yaml
    ├── prompts/
    │   ├── system_prompt.txt
    │   └── planner_prompt.txt
    ├── scripts/
    │   ├── start_litellm.sh         # Start LiteLLM proxy
    │   ├── run_agent.py             # CLI entry point
    │   ├── test_litellm_proxy.py    # Health-check the proxy
    │   ├── test_claude_agent_sdk.py # End-to-end SDK routing test
    │   ├── test_llm_2plus2.py       # Basic LLM sanity check
    │   ├── diagnose_llm_pipeline.py # Pipeline diagnostics
    │   └── clean.sh                 # Clear generated outputs
    └── src/
        └── zipfix_agent/
            ├── agent.py             # Claude Agent SDK wrapper
            ├── config.py            # Env-var configuration
            ├── repair_loop.py       # Main orchestration pipeline
            ├── schemas.py           # Pydantic data models
            ├── checks.py            # pytest + compile checks
            ├── unzipper.py          # Safe zip extraction
            ├── scoring.py           # Quality scoring
            ├── tools.py             # File hashing / diff helpers
            ├── skill_builder.py     # Prompt skill utilities
            └── readme_writer.py     # Markdown report generator
```

---

## Setup

### 1. Create virtual environment

```bash
cd "/Users/jashu/Desktop/Master /Protomise-assesment/Code_expert"
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -e .
pip install "litellm[proxy]"
```

### 3. Install and prepare Ollama

```bash
# Install Ollama from https://ollama.com
ollama pull qwen2.5-coder:3b
```

### 4. Configure environment

Create a `.env` file in `Code_expert/`:

```env
LITELLM_MASTER_KEY=sk-local-zipfix-key
ANTHROPIC_BASE_URL=http://localhost:4000
ANTHROPIC_AUTH_TOKEN=sk-local-zipfix-key
ANTHROPIC_API_KEY=""

MODEL=local-claude-coder
REASONING_MODEL=local-claude-coder
ANTHROPIC_DEFAULT_SONNET_MODEL=local-claude-coder
ANTHROPIC_DEFAULT_OPUS_MODEL=local-claude-coder
ANTHROPIC_DEFAULT_HAIKU_MODEL=local-claude-coder

CLAUDE_CODE_MAX_OUTPUT_TOKENS=100000
ZIPFIX_MAX_FILE_CHARS=100000
```

> `ANTHROPIC_API_KEY` must be blank — this forces Claude Agent SDK to route through LiteLLM and never call `api.anthropic.com`.

### 5. LiteLLM config (`litellm_config.yaml`)

```yaml
model_list:
  - model_name: local-claude-coder
    litellm_params:
      model: ollama_chat/qwen2.5-coder:3b
      api_base: http://localhost:11434
      keep_alive: "30m"
      num_ctx: 32768
      num_predict: 100000
      temperature: 0
```

---

## Running

**Terminal 1 — Start Ollama**

```bash
ollama serve
```

**Terminal 2 — Start LiteLLM proxy**

```bash
cd "/Users/jashu/Desktop/Master /Protomise-assesment/Code_expert"
source .venv/bin/activate
./scripts/start_litellm.sh
```

**Terminal 3 — Verify routing**

```bash
source .venv/bin/activate
python scripts/test_llm_2plus2.py
python scripts/test_claude_agent_sdk.py
```

**Terminal 3 — Run the repair agent**

```bash
python scripts/run_agent.py ../inputs/calculator_project.zip
```

Or interactive mode:

```bash
python scripts/run_agent.py
```

---

## Repair Loop

```
1. Unzip          →  Safely extract the zipped project
2. Baseline check →  Run pytest + compile check, record score
3. Agent run      →  Claude Agent SDK reads code, diagnoses bugs, applies fixes
4. Verify         →  Re-run pytest + compile check
5. Iterate        →  Repeat up to 3 times, stop early on success
6. Report         →  Write result.json + README_REPORT.md
```

The agent uses `Bash`, `Read`, and `Edit` tools. It never edits test files and always prefers minimal, targeted fixes.

For smaller local models that return tool-call-shaped JSON as plain text (which `qwen2.5-coder:3b` sometimes does), the repair loop includes a validated text-edit fallback that still runs tests before accepting any change.

---

## Output

For input `../inputs/calculator_project.zip`:

```
../outputs/calculator_project/
├── scratch_project/       # Extracted + repaired source
├── result.json            # Machine-readable score & diff summary
└── README_REPORT.md       # Human-readable repair report
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` on `localhost:4000` | Start LiteLLM: `./scripts/start_litellm.sh` |
| `401 Unauthorized` | Ensure `LITELLM_MASTER_KEY` and `ANTHROPIC_AUTH_TOKEN` match |
| `Model not found` | Ensure `MODEL=local-claude-coder` matches `model_name` in `litellm_config.yaml` |
| Ollama model missing | Run `ollama pull qwen2.5-coder:3b` |
| Claude SDK calls Anthropic directly | Confirm `ANTHROPIC_BASE_URL=http://localhost:4000` and `ANTHROPIC_API_KEY=""` |
| Fake tool-call JSON in output | The repair loop has a validated text-edit fallback for this |
| Slow responses | `qwen2.5-coder:3b` is the recommended size; larger models are slower |

---

## Cleanup

```bash
./scripts/clean.sh
```

Clears generated outputs while preserving input zip files.

---

## License

MIT — built for the Proptimise AI Agentic Engineer assessment.
