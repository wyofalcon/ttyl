#!/usr/bin/env bash
# cache-segment.sh — output a one-line prompt-cache TTL segment for composition
# into a Claude Code statusLine.
#
# Reads the lifecycle state written by the plugin's hooks from
# ~/.claude/.cache-timestamp, then prints ONE of:
#   ⚪ no cache          — fresh session, no request sent yet
#   🔄 active            — request in flight; cache is being refreshed
#   🟢 cache M:SS        — idle, >2:00 remaining (healthy)
#   🟡 cache M:SS        — idle, 1:00–2:00 remaining (warn)
#   🔴 cache 0:SS        — idle, <1:00 remaining (act now or lose cache)
#   🔴 cache expired     — idle >5:00; next prompt will be uncached
#
# Environment overrides:
#   CACHE_TTL_SECONDS  — TTL in seconds (default 300, Anthropic's ephemeral cache)
#   CACHE_STATE_FILE   — path to the state file (default ~/.claude/.cache-timestamp)
#
# Prints nothing and exits 0 if the state file is missing — lets callers safely
# compose the segment without guarding.

TTL=${CACHE_TTL_SECONDS:-300}
state_file=${CACHE_STATE_FILE:-${HOME}/.claude/.cache-timestamp}

[ -f "$state_file" ] || exit 0

state=$(cat "$state_file" 2>/dev/null)
case "$state" in
  none)
    printf "⚪ no cache"
    ;;
  active)
    printf "🔄 active"
    ;;
  idle:*)
    last_ts=${state#idle:}
    now_ts=$(date +%s)
    rem=$((TTL - (now_ts - last_ts)))
    if [ "$rem" -le 0 ]; then
      printf "🔴 cache expired"
    elif [ "$rem" -lt 60 ]; then
      printf "🔴 cache 0:%02d" "$rem"
    elif [ "$rem" -lt 120 ]; then
      mins=$((rem / 60)); secs=$((rem % 60))
      printf "🟡 cache %d:%02d" "$mins" "$secs"
    else
      mins=$((rem / 60)); secs=$((rem % 60))
      printf "🟢 cache %d:%02d" "$mins" "$secs"
    fi
    ;;
esac
