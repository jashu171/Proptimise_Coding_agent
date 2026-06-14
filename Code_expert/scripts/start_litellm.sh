#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Start the LiteLLM proxy for ZipFix Agent
# ──────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if [ ! -f ".env" ]; then
    echo "❌  Missing .env file."
    echo "    Copy .env.example to .env and add your OPENAI_API_KEY."
    exit 1
fi

# Export all env vars from .env
set -a
# shellcheck disable=SC1091
source .env
set +a

echo "🚀  Starting LiteLLM proxy on http://localhost:4000"
echo "    Config : litellm_config.yaml"
echo "    Master key : ${LITELLM_MASTER_KEY:0:12}..."
echo ""
litellm --config litellm_config.yaml --port 4000
