#!/usr/bin/env bash
# Fails if TARS code references a hosted AI endpoint or depends on a hosted AI SDK.
# Usage: scripts/check_no_ai_endpoints.sh            scan engine/ swift/ scripts/ and engine/uv.lock
#        scripts/check_no_ai_endpoints.sh --stdin    scan stdin (used by the Claude Code hook)
#        scripts/check_no_ai_endpoints.sh FILE...    scan the given files
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
hosts='api\.openai\.com|api\.anthropic\.com|api\.typesafe\.ai|generativelanguage\.googleapis\.com|openrouter\.ai|api\.mistral\.ai|api\.cohere\.ai|api\.groq\.com|api\.together\.xyz'
sdks='^(openai|anthropic|google-generativeai|cohere|mistralai|litellm|langchain[a-z0-9_-]*)$'
status=0

if [ "${1:-}" = "--stdin" ]; then
  if hit="$(grep -nE "$hosts" || true)" && [ -n "$hit" ]; then
    echo "hosted AI host referenced: $hit" >&2; status=1
  fi
  exit $status
fi

if [ $# -gt 0 ]; then targets=("$@"); else targets=("$root/engine" "$root/swift" "$root/scripts"); fi
for t in "${targets[@]}"; do
  [ -e "$t" ] || continue
  if hit="$(grep -rnE "$hosts" "$t" --exclude='check_no_ai_endpoints.sh' --exclude-dir='.venv' --exclude-dir='.build' || true)" && [ -n "$hit" ]; then
    echo "hosted AI host referenced:"; echo "$hit"; status=1
  fi
done

lock="$root/engine/uv.lock"
if [ -f "$lock" ]; then
  bad="$(grep -E '^name = "' "$lock" | sed -E 's/^name = "([^"]+)"/\1/' | grep -E "$sdks" || true)"
  if [ -n "$bad" ]; then echo "hosted AI SDK in uv.lock: $bad"; status=1; fi
fi
exit $status
