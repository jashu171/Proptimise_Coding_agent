# 🚀 Getting Started with ZipFix Agent

Welcome to **ZipFix Agent**! This guide will walk you through setting up the agent, preparing an example buggy project zip file, and running the repair pipeline.

---

## 🛠️ Step 1: Quick Setup

First, initialize your virtual environment and install the package along with its dependencies:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install ZipFix Agent in editable mode along with LiteLLM proxy
pip install -e .
pip install "litellm[proxy]"

# 3. Create your .env file
cp .env.example .env
```

Open the newly created `.env` file and set your **OpenAI API Key**:
```env
OPENAI_API_KEY=sk-proj-... # Your real OpenAI API Key
```

---

## 🔗 Step 2: Start and Verify the Proxy

The agent routes all of its API calls through a local LiteLLM proxy to translate Anthropic-format requests to OpenAI GPT models.

1. **Start the Proxy** (in a dedicated terminal):
   ```bash
   chmod +x scripts/start_litellm.sh
   ./scripts/start_litellm.sh
   ```

2. **Verify connection** (in a new terminal):
   ```bash
   source .venv/bin/activate
   
   # Check LiteLLM is responding
   python scripts/test_litellm_proxy.py
   
   # Check Claude Agent SDK routes correctly
   python scripts/test_claude_agent_sdk.py
   ```
   > [!TIP]
   > Make sure both verification commands output `PASS ✅` before moving to the next step.

---

## 📦 Step 3: Preparing an Example Buggy Zip File

To run the agent, you need a zipped project containing a Python source file with a bug and a corresponding `pytest` test file. Here is how to create a simple calculator example:

1. **Create the directory structure:**
   ```bash
   mkdir -p example_project/tests
   ```

2. **Create the buggy source file** (`example_project/calc.py`):
   ```python
   # example_project/calc.py
   def add(a, b):
       # Bug: uses subtraction instead of addition
       return a - b
   ```

3. **Create the test file** (`example_project/tests/test_calc.py`):
   ```python
   # example_project/tests/test_calc.py
   from calc import add

   def test_add():
       assert add(2, 3) == 5
   ```

4. **Zip the folder:**
   ```bash
   # Package the project folder into a zip file
   zip -r buggy_calc.zip example_project
   ```

5. **Clean up the folder** (leaving only the zip file):
   ```bash
   rm -rf example_project
   ```

Move the zip file to the workspace-root `inputs/` folder:
```bash
mkdir -p ../inputs
mv buggy_calc.zip ../inputs/
```

---

## 🏎️ Step 4: Run the Agent

Now run the repair pipeline on your newly packaged `buggy_calc.zip`:

```bash
python scripts/run_agent.py ../inputs/buggy_calc.zip
```

Alternatively, you can run in **interactive mode** to select from any zip files placed in the workspace-root `inputs/` folder:
```bash
python scripts/run_agent.py
```

### 📋 Expected Console Output:
```text
Found zip files in ../inputs:
  [1] buggy_calc.zip

Enter number, or input path to another zip file: 1
🚀 ZipFix Agent – buggy_calc.zip
...
[Agent extracts, runs tests, finds the bug, edits calc.py, and re-runs pytest]
...
📋 Final Result
  Success: ✅
  Score:   0% → 100%
  Iterations: 1
```

---

## 📊 Step 5: Check the Repair Results

Once the agent completes the repair:
- **Run Output:** Inspect the repaired project and reports inside `../outputs/buggy_calc/`.
