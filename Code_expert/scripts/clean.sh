#!/bin/bash
# Clean generated outputs while preserving root-level input zips.

set -e

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$AGENT_ROOT/.." && pwd)"

echo "🧹 Cleaning ZipFix Agent outputs..."

# Clean root-level outputs directory
if [ -d "$WORKSPACE_ROOT/outputs" ]; then
    echo "  Removing contents of $WORKSPACE_ROOT/outputs/ ..."
    rm -rf "$WORKSPACE_ROOT"/outputs/*
fi

# Clean legacy agent-local runtime folders from older runs
if [ -d "$AGENT_ROOT/outputs" ]; then
    echo "  Removing legacy contents of $AGENT_ROOT/outputs/ ..."
    rm -rf "$AGENT_ROOT"/outputs/*
fi

if [ -d "$AGENT_ROOT/uploads" ]; then
    echo "  Removing legacy contents of $AGENT_ROOT/uploads/ ..."
    rm -rf "$AGENT_ROOT"/uploads/*
fi

echo "✨ Cleanup complete!"
