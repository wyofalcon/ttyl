#!/usr/bin/env bash
# statusline-standalone.sh — minimal drop-in statusLine for users who don't
# already have one. Outputs:   <cache-segment> | <model>   (nothing else).
#
# If you already have a custom statusLine, DO NOT use this. Instead source or
# invoke cache-segment.sh from within your own script and compose it into your
# existing output.

input=$(cat)

# Try to extract model via jq; fall back to empty if jq unavailable.
model=""
if command -v jq >/dev/null 2>&1; then
  model=$(echo "$input" | jq -r '.model.display_name // .model.id // ""')
fi

cache_seg=$(bash "$(dirname "$0")/cache-segment.sh")

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
