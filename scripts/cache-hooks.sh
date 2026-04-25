#!/usr/bin/env bash
# cache-hooks.sh — single entry point for TTYL's SessionStart /
# UserPromptSubmit / Stop hooks. Reads the hook JSON from stdin,
# writes both the legacy single-file state AND a per-session JSON
# under ~/.claude/cache-timers/. Fails silently — must never
# disrupt a Claude session.
#
# Stdin (from Claude Code):
#   { "session_id": "...", "cwd": "...", "hook_event_name": "...", ... }
#
# PPID_OVERRIDE env var (test-only) forces the recorded pid.

set +e

timers_dir="${HOME}/.claude/cache-timers"
legacy_file="${HOME}/.claude/.cache-timestamp"
mkdir -p "$timers_dir" 2>/dev/null
mkdir -p "$(dirname "$legacy_file")" 2>/dev/null

input=$(cat)

extract() {
  local k="$1"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$input" | jq -r --arg k "$k" '.[$k] // ""'
  else
    printf '%s' "$input" | sed -n 's/.*"'"$k"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1
  fi
}

session_id=$(extract session_id)
cwd=$(extract cwd)
event=$(extract hook_event_name)

now=$(date +%s)
pid="${PPID_OVERRIDE:-$PPID}"
project_name=$(basename "$cwd" 2>/dev/null)

case "$event" in
  SessionStart) legacy_val="none" ; state="none"  ;;
  UserPromptSubmit|PreCompact) legacy_val="active" ; state="active" ;;
  Stop) legacy_val="idle:${now}" ; state="idle" ;;
  SessionEnd)
    # Claude session is shutting down: drop the per-session file so the
    # desktop tile removes its row. Leave the legacy single-file state
    # alone — other sessions may still be relying on it.
    [ -n "$session_id" ] && rm -f "$timers_dir/${session_id}.json" 2>/dev/null
    exit 0
    ;;
  *) exit 0 ;;
esac

printf '%s' "$legacy_val" > "$legacy_file" 2>/dev/null

[ -z "$session_id" ] && exit 0

if [ "$event" = "SessionStart" ] && [ -n "$cwd" ]; then
  for f in "$timers_dir"/*.json; do
    [ -f "$f" ] || continue
    if grep -qF "\"cwd\":\"${cwd}\"" "$f" 2>/dev/null; then
      case "$f" in *"/${session_id}.json") ;; *) rm -f "$f" ;; esac
    fi
  done
fi

started_at="$now"
existing="$timers_dir/${session_id}.json"
if [ -f "$existing" ] && command -v jq >/dev/null 2>&1; then
  prev=$(jq -r '.started_at // empty' "$existing" 2>/dev/null)
  [ -n "$prev" ] && started_at="$prev"
fi

{
  printf '{'
  printf '"session_id":"%s",' "$session_id"
  printf '"state":"%s",' "$state"
  printf '"epoch":%s,' "$now"
  printf '"cwd":"%s",' "$cwd"
  printf '"project_name":"%s",' "$project_name"
  printf '"pid":%s,' "$pid"
  printf '"started_at":%s,' "$started_at"
  printf '"last_update":%s,' "$now"
  printf '"hook_event":"%s"' "$event"
  printf '}'
} > "$timers_dir/${session_id}.json.tmp" 2>/dev/null \
  && mv "$timers_dir/${session_id}.json.tmp" "$timers_dir/${session_id}.json" 2>/dev/null

find "$timers_dir" -maxdepth 1 -name '*.json' -mmin +1440 -delete 2>/dev/null || true

exit 0
