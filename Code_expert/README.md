# ZipFix Agent

AI-powered test-driven Python repair agent built for the Proptimise AI Agentic Engineer assessment.

ZipFix Agent accepts a zipped Python project, runs baseline checks, uses Claude Agent SDK to perform repair work, reruns tests, scores the result, and writes a JSON result plus a Markdown repair report.

## Current Architecture

The final working setup uses a local Ollama model through LiteLLM:

```text
Claude Agent SDK
  |
  | ANTHROPIC_BASE_URL=http://localhost:4000
  v
LiteLLM Proxy
  |
  | model alias: local-claude-coder
  v
Ollama Local Runtime
  |
  | qwen2.5-coder:3b
  v
Local coding LLM
```

Important detail: Claude Agent SDK does not know this is an Ollama model. It only sees the configured model name `local-claude-coder`. LiteLLM owns the provider mapping and forwards that alias to `ollama_chat/qwen2.5-coder:3b`.

## Why This Route

The first plan was to use a hosted model through Anthropic/OpenAI-style routing. That was blocked by practical limits:

- Anthropic credit path: the attempted $5 credit claim was not successful.
- OpenRouter base URL path: API rate limits made the workflow unreliable.
- Cloud Ollama path: rate limits were also a concern.

I did not stop there. The final path uses LiteLLM as a local proxy and Ollama as a local model runtime, so the project can keep the Claude Agent SDK interface while running inference locally.

## What It Does

1. Accepts a zipped Python project from the workspace-root `inputs/` folder.
2. Extracts the zip safely into the workspace-root `outputs/` folder.
3. Runs `pytest` and Python compile checks.
4. Scores the project before repair.
5. Calls the fixer agent through Claude Agent SDK.
6. Applies source-code fixes only.
7. Re-runs checks after each attempt.
8. Repeats up to 3 iterations or stops early when all checks pass.
9. Saves `result.json` and `README_REPORT.md`.

## Assessment Fit

| Requirement | Implementation |
|---|---|
| Claude Agent SDK as agent framework | `claude_agent_sdk.query()` and `ClaudeAgentOptions` in `src/zipfix_agent/agent.py` |
| No direct OpenAI SDK dependency in agent code | LLM traffic routes through Claude Agent SDK -> LiteLLM |
| No OpenRouter dependency in final runtime | OpenRouter was tried but removed due to rate limits |
| Local model support | LiteLLM maps `local-claude-coder` to Ollama `qwen2.5-coder:3b` |
| Test-driven repair | Baseline and final `pytest` plus compile checks |
| Iteration | Up to 3 repair iterations with score tracking |
| Reports | JSON result and Markdown report under `../outputs/<project>/` |

## Project Layout

```text
Protomise-assesment/
├── inputs/                         # Zipped projects to repair
├── outputs/                        # Generated repair outputs
└── Code_expert/
    ├── README.md
    ├── pyproject.toml
    ├── litellm_config.yaml
    ├── prompts/
    │   ├── system_prompt.txt
    │   └── planner_prompt.txt
    ├── scripts/
    │   ├── start_litellm.sh
    │   ├── run_agent.py
    │   ├── test_litellm_proxy.py
    │   ├── test_llm_2plus2.py
    │   ├── test_claude_agent_sdk.py
    │   ├── diagnose_llm_pipeline.py
    │   └── clean.sh
    └── src/
        └── zipfix_agent/
            ├── agent.py
            ├── checks.py
            ├── config.py
            ├── repair_loop.py
            ├── schemas.py
            ├── scoring.py
            ├── skill_builder.py
            ├── tools.py
            ├── unzipper.py
            └── readme_writer.py
```

The agent code stays isolated in `Code_expert/`. Runtime inputs and outputs live outside it:

```text
../inputs/
../outputs/
```

## Setup

From `Code_expert/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install "litellm[proxy]"
```

Install and prepare Ollama:

```bash
ollama pull qwen2.5-coder:3b
```

The LiteLLM config maps the local alias:

```yaml
model_list:
  - model_name: local-claude-coder
    litellm_params:
      model: ollama_chat/qwen2.5-coder:3b
      api_base: http://localhost:11434
      keep_alive: "30m"
      think: false
      num_ctx: 32768
      num_predict: 100000
      temperature: 0
```

## Environment

`.env` should point Claude Agent SDK to LiteLLM:

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
CLAUDE_CODE_SUBAGENT_MODEL=local-claude-coder

CLAUDE_CODE_MAX_OUTPUT_TOKENS=100000
BASH_MAX_OUTPUT_LENGTH=100000
ZIPFIX_MAX_FILE_CHARS=100000
```

Note on tokens: the project no longer applies small local truncation limits to reports or repair context. The actual usable context is still bounded by the selected local model and Ollama runtime.

## Run

Terminal 1, start LiteLLM:

```bash
cd "/Users/jashu/Desktop/Master /Protomise-assesment/Code_expert"
source .venv/bin/activate
./scripts/start_litellm.sh
```

Terminal 2, verify routing:

```bash
cd "/Users/jashu/Desktop/Master /Protomise-assesment/Code_expert"
source .venv/bin/activate
python scripts/test_llm_2plus2.py
python scripts/test_claude_agent_sdk.py
```

Run the repair agent:

```bash
python scripts/run_agent.py ../inputs/calculator_project.zip
```

Or interactive mode:

```bash
python scripts/run_agent.py
```

Interactive mode lists zip files from:

```text
../inputs/
```

## Repair Loop

The repair loop is in `src/zipfix_agent/repair_loop.py`.

```text
1. Safe unzip
2. Baseline pytest and compile checks
3. Score before repair
4. Run fixer agent
5. Apply SDK tool edits when available
6. Apply local text-edit fallback for models that return JSON text instead of real tool calls
7. Apply validated full-file fallback only if pytest/compile score improves
8. Roll back non-improving edits
9. Stop on success or after 3 iterations
10. Write JSON and Markdown reports
```

The validated fallback exists because smaller local models can return tool-call-shaped JSON as plain text. The fallback keeps the project practical with local Qwen while still checking every proposed change with tests before accepting it.

## Output

For an input zip:

```text
../inputs/calculator_project.zip
```

The run creates:

```text
../outputs/calculator_project/
├── calculator_project.zip
├── scratch_project/
├── result.json
└── README_REPORT.md
```

`result.json` contains the machine-readable score, iterations, changed files, and success flag.

`README_REPORT.md` contains the human-readable repair report.

## Cleanup

From `Code_expert/`:

```bash
./scripts/clean.sh
```

This clears generated outputs while preserving root-level input zip files.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` on `localhost:4000` | Start LiteLLM with `./scripts/start_litellm.sh` |
| `401 Unauthorized` | Ensure `LITELLM_MASTER_KEY` and `ANTHROPIC_AUTH_TOKEN` match |
| `Model not found` | Ensure `MODEL=local-claude-coder` and `litellm_config.yaml` has the same `model_name` |
| Ollama model missing | Run `ollama pull qwen2.5-coder:3b` |
| Claude SDK tries hosted Anthropic | Confirm `ANTHROPIC_BASE_URL=http://localhost:4000` and `ANTHROPIC_API_KEY=""` |
| Local model returns fake tool JSON | The repair loop has text-edit and validated full-file fallbacks |
| Slow responses | Use smaller local models or keep `qwen2.5-coder:3b`; larger local coder models are slower |

## Status

The current project is configured for:

```text
Claude Agent SDK -> LiteLLM Proxy -> Ollama -> qwen2.5-coder:3b
```

The goal is not to pretend local Qwen is Claude. The goal is to keep the Claude Agent SDK control flow while using LiteLLM to bridge that SDK to a local coding model.
