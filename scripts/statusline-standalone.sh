#!/usr/bin/env bash
# statusline-standalone.sh — minimal drop-in statusLine for users who don't
# already have one. Outputs:   <cache-segment> | <model>   (nothing else).
#
# If you already have a custom statusLine, DO NOT use this. Instead source or
# invoke cache-segment.sh from within your own script and compose it into your
# existing output.

input=$(cat)

# Extract with jq when available, sed as fallback. Without the fallback,
# environments missing jq (notably default Git Bash on Windows) silently
# pass an empty session_id, and cache-segment.sh degrades to the shared
# legacy state file — which is overwritten by every active session and
# makes the indicator appear to "follow" other Claude instances.
extract_str() {
  # $1 = jq path expr; $2 = sed key for fallback
  if command -v jq >/dev/null 2>&1; then
    echo "$input" | jq -r "$1 // \"\""
  else
    echo "$input" | sed -n 's/.*"'"$2"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1
  fi
}

model=$(extract_str '.model.display_name' 'display_name')
[ -z "$model" ] && model=$(extract_str '.model.id' 'id')
session_id=$(extract_str '.session_id' 'session_id')

cache_seg=$(CLAUDE_SESSION_ID="$session_id" bash "$(dirname "$0")/cache-segment.sh")

# Assemble
parts=()
[ -n "$cache_seg" ] && parts+=("$cache_seg")
[ -n "$model" ] && parts+=("$model")

out=""
for p in "${parts[@]}"; do
  if [ -z "$out" ]; then
    out="$p"
  else
    out="$out | $p"
  fi
done

printf "%s" "$out"
