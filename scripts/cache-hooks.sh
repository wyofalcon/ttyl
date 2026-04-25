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

# Escape \ and " so a value can be safely embedded in a JSON string.
# Defense in depth: even if upstream session_id/cwd/etc are well-formed today,
# a future input with a literal backslash or quote would otherwise produce
# invalid JSON or break the same-cwd grep cleanup below.
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '%s' "$s"
}

session_id=$(extract session_id)
# session_id is used as a filename; reject anything outside [A-Za-z0-9_-] to
# block path traversal (e.g. session_id="../../.ssh/authorized_keys" would
# otherwise be written and rm'd on SessionEnd). Treat invalid as "missing"
# so the legacy-file write still happens but the per-session paths are skipped.
case "$session_id" in
  *[!a-zA-Z0-9_-]*) session_id="" ;;
esac
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
    if grep -qF "\"cwd\":\"$(json_escape "$cwd")\"" "$f" 2>/dev/null; then
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
  printf '"session_id":"%s",' "$(json_escape "$session_id")"
  printf '"state":"%s",' "$state"
  printf '"epoch":%s,' "$now"
  printf '"cwd":"%s",' "$(json_escape "$cwd")"
  printf '"project_name":"%s",' "$(json_escape "$project_name")"
  printf '"pid":%s,' "$pid"
  printf '"started_at":%s,' "$started_at"
  printf '"last_update":%s,' "$now"
  printf '"hook_event":"%s"' "$(json_escape "$event")"
  printf '}'
} > "$timers_dir/${session_id}.json.tmp" 2>/dev/null \
  && mv "$timers_dir/${session_id}.json.tmp" "$timers_dir/${session_id}.json" 2>/dev/null

find "$timers_dir" -maxdepth 1 -name '*.json' -mmin +1440 -delete 2>/dev/null || true

exit 0
