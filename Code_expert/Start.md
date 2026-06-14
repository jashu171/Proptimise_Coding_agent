# 🚀 Getting Started with Code Expert Agent

Welcome to **Code Expert Agent**! This guide walks you through setting up the full local stack — Ollama + LiteLLM + Claude Agent SDK — and running the repair pipeline on a buggy Python project.

---

## Stack Overview

```
Claude Agent SDK
  │  ANTHROPIC_BASE_URL=http://localhost:4000
  ▼
LiteLLM Proxy  (localhost:4000)
  │  model alias: local-claude-coder → ollama_chat/qwen2.5-coder:3b
  ▼
Ollama  (localhost:11434)
  │
  ▼
qwen2.5-coder:3b  (100% local, no cloud calls)
```

Claude Agent SDK never knows it is talking to an Ollama model. LiteLLM owns the alias mapping transparently.

---

## 🛠️ Step 1: Install Dependencies

```bash
# From Code_expert/
python -m venv .venv
source .venv/bin/activate

pip install -e .
pip install "litellm[proxy]"
```

---

## 🤖 Step 2: Install Ollama and Pull the Model

1. Download and install Ollama from [https://ollama.com](https://ollama.com)

2. Pull the coding model:
   ```bash
   ollama pull qwen2.5-coder:3b
   ```

3. Ollama runs automatically in the background after install. You can verify it is up:
   ```bash
   ollama list
   ```

---

## ⚙️ Step 3: Configure Environment

Create a `.env` file inside `Code_expert/`:

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

> **Important:** `ANTHROPIC_API_KEY` must be blank. This prevents Claude Agent SDK from ever calling `api.anthropic.com`.

---

## 🔗 Step 4: Start the LiteLLM Proxy

In a **dedicated terminal** (keep it running):

```bash
cd "/Users/jashu/Desktop/Master /Protomise-assesment/Code_expert"
source .venv/bin/activate
./scripts/start_litellm.sh
```

---

## ✅ Step 5: Verify the Full Pipeline

In a **new terminal**:

```bash
source .venv/bin/activate

# Sanity check — does LiteLLM respond?
python scripts/test_litellm_proxy.py

# Basic LLM check — does the model answer 2+2?
python scripts/test_llm_2plus2.py

# End-to-end check — does Claude Agent SDK route through LiteLLM to Ollama?
python scripts/test_claude_agent_sdk.py
```

All three should output `PASS ✅` before continuing.

---

## 📦 Step 6: Prepare a Buggy Zip Project

Place any zipped Python project with failing `pytest` tests into `../inputs/`.

To create a quick example:

```bash
mkdir -p example_project/tests

# Buggy source
cat > example_project/calc.py << 'EOF'
def add(a, b):
    return a - b  # bug: should be +
EOF

# Test
cat > example_project/tests/test_calc.py << 'EOF'
from calc import add

def test_add():
    assert add(2, 3) == 5
EOF

zip -r ../inputs/buggy_calc.zip example_project
rm -rf example_project
```

---

## 🏎️ Step 7: Run the Agent

```bash
python scripts/run_agent.py ../inputs/buggy_calc.zip
```

Or interactive mode (lists all zips from `../inputs/`):

```bash
python scripts/run_agent.py
```

### Expected output

```text
Found zip files in ../inputs:
  [1] buggy_calc.zip

Enter number, or input path to another zip file: 1
🚀 Code Expert Agent – buggy_calc.zip
...
[Agent extracts, runs tests, finds the bug, edits calc.py, re-runs pytest]
...
📋 Final Result
  Success: ✅
  Score:   0% → 100%
  Iterations: 1
```

---

## 📊 Step 8: Check the Results

```
../outputs/buggy_calc/
├── scratch_project/       # Extracted + repaired source
├── result.json            # Machine-readable score & diff summary
└── README_REPORT.md       # Human-readable repair report
```

---

## 🧹 Cleanup

```bash
./scripts/clean.sh
```

Clears all generated outputs while preserving input zip files.
