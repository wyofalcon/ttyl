#!/usr/bin/env bash
# cache-segment.sh — output a one-line prompt-cache TTL segment for composition
# into a Claude Code statusLine.
#
# Per-session aware: reads ~/.claude/cache-timers/<session-id>.json when a
# session id is available, falling back to the legacy single-file format
# (~/.claude/.cache-timestamp) for back-compat.
#
# Session id resolution (in priority order):
#   1. $CLAUDE_SESSION_ID env var (set by the calling statusline script)
#   2. JSON on stdin (.session_id field) — for direct piping
#   3. Falls back to legacy file
#
# Output is one of:
#   ⚪ no cache          — fresh session, no request sent yet
#   🔄 active            — request in flight; cache is being refreshed
#   🟢 cache M:SS        — idle, >2:00 remaining (healthy)
#   🟡 cache M:SS        — idle, 1:00–2:00 remaining (warn)
#   🔴 cache 0:SS        — idle, <1:00 remaining (act now or lose cache)
#   🔴 cache expired     — idle >5:00; next prompt will be uncached
#
# Environment overrides:
#   CACHE_TTL_SECONDS    — TTL in seconds (default 300, Anthropic's ephemeral cache)
#   CACHE_STATE_FILE     — legacy state file (default ~/.claude/.cache-timestamp)
#   CACHE_TIMERS_DIR     — per-session dir   (default ~/.claude/cache-timers)
#   CLAUDE_SESSION_ID    — session id to render

TTL=${CACHE_TTL_SECONDS:-300}
timers_dir="${CACHE_TIMERS_DIR:-${HOME}/.claude/cache-timers}"
legacy_file="${CACHE_STATE_FILE:-${HOME}/.claude/.cache-timestamp}"

session_id="${CLAUDE_SESSION_ID:-}"
# If no env var, try parsing stdin JSON (only if stdin is a pipe).
if [ -z "$session_id" ] && [ ! -t 0 ]; then
  input=$(cat)
  if command -v jq >/dev/null 2>&1; then
    session_id=$(printf '%s' "$input" | jq -r '.session_id // ""' 2>/dev/null)
  else
    session_id=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)
  fi
fi

state=""
last_ts=""

per_session_file="$timers_dir/${session_id}.json"
if [ -n "$session_id" ] && [ -f "$per_session_file" ]; then
  if command -v jq >/dev/null 2>&1; then
    state=$(jq -r '.state // ""' "$per_session_file" 2>/dev/null)
    last_ts=$(jq -r '.epoch // 0' "$per_session_file" 2>/dev/null)
  else
    state=$(sed -n 's/.*"state"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$per_session_file" | head -n1)
    last_ts=$(sed -n 's/.*"epoch"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$per_session_file" | head -n1)
  fi
fi

if [ -z "$state" ] && [ -f "$legacy_file" ]; then
  legacy=$(cat "$legacy_file" 2>/dev/null)
  case "$legacy" in
    none) state="none" ;;
    active) state="active" ;;
    idle:*)
      state="idle"
      last_ts="${legacy#idle:}"
      ;;
  esac
fi

case "$state" in
  none)
    printf "⚪ no cache"
    ;;
  active)
    printf "🔄 active"
    ;;
  idle)
    if [ -n "$last_ts" ] && [ "$last_ts" -gt 0 ] 2>/dev/null; then
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
    fi
    ;;
esac
