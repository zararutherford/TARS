#!/usr/bin/env bash
# PreToolUse hook on Edit|Write: refuse content that references a hosted AI endpoint or SDK.
set -euo pipefail
input="$(cat)"
file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
[ -z "$file" ] && exit 0
case "$file" in
  */scripts/check_no_ai_endpoints.sh|*/.claude/*|*/docs/*|*.md) exit 0 ;;
esac
content="$(printf '%s' "$input" | jq -r '.tool_input.content // .tool_input.new_string // empty')"
[ -z "$content" ] && exit 0
if ! printf '%s' "$content" | "$CLAUDE_PROJECT_DIR/scripts/check_no_ai_endpoints.sh" --stdin 2>/tmp/tars-endpoint-check.err; then
  echo "Blocked: $file would reference a hosted AI endpoint or SDK. TARS is local-only. $(cat /tmp/tars-endpoint-check.err)" >&2
  exit 2
fi
