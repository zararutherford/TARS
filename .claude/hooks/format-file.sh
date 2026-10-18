#!/usr/bin/env bash
# PostToolUse hook on Edit|Write: format Python with ruff and Swift with swift format.
set -uo pipefail
file="$(jq -r '.tool_input.file_path // empty')"
[ -z "$file" ] || [ ! -f "$file" ] && exit 0
case "$file" in
  *.py)
    if [ -f "$CLAUDE_PROJECT_DIR/engine/uv.lock" ]; then
      uv run --project "$CLAUDE_PROJECT_DIR/engine" ruff format "$file" >/dev/null 2>&1 \
        && uv run --project "$CLAUDE_PROJECT_DIR/engine" ruff check --fix --quiet "$file" >/dev/null 2>&1
    else
      uvx ruff format "$file" >/dev/null 2>&1 && uvx ruff check --fix --quiet "$file" >/dev/null 2>&1
    fi
    ;;
  *.swift)
    swift format -i "$file" >/dev/null 2>&1
    ;;
esac
exit 0
