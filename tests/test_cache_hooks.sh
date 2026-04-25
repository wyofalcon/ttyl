#!/usr/bin/env bash
# Tests for cache-hooks.sh. Runs each hook event against the script and
# asserts correct legacy + per-session state. Uses a tmpdir as fake HOME.

set -u

script="$(dirname "$0")/../scripts/cache-hooks.sh"
tmp=$(mktemp -d)
export HOME="$tmp"
mkdir -p "$HOME/.claude"

fail=0
pass() { printf "PASS: %s\n" "$1"; }
fail() { printf "FAIL: %s\n  %s\n" "$1" "$2"; fail=$((fail + 1)); }

# --- SessionStart ---
echo '{"session_id":"abc","cwd":"/c/Users/w/projects/demo","hook_event_name":"SessionStart"}' \
  | PPID_OVERRIDE=9999 bash "$script"

[ "$(cat "$HOME/.claude/.cache-timestamp")" = "none" ] \
  && pass "SessionStart writes legacy 'none'" \
  || fail "SessionStart legacy" "got '$(cat "$HOME/.claude/.cache-timestamp")'"

[ -f "$HOME/.claude/cache-timers/abc.json" ] \
  && pass "SessionStart writes per-session file" \
  || fail "SessionStart per-session file missing" "ls: $(ls "$HOME/.claude/cache-timers/" 2>&1)"

grep -q '"state":"none"' "$HOME/.claude/cache-timers/abc.json" \
  && pass "SessionStart per-session state=none" \
  || fail "SessionStart state" "content: $(cat "$HOME/.claude/cache-timers/abc.json")"

grep -q '"pid":9999' "$HOME/.claude/cache-timers/abc.json" \
  && pass "SessionStart records PPID as pid" \
  || fail "SessionStart pid" "content: $(cat "$HOME/.claude/cache-timers/abc.json")"

# --- UserPromptSubmit ---
echo '{"session_id":"abc","cwd":"/c/Users/w/projects/demo","hook_event_name":"UserPromptSubmit"}' \
  | PPID_OVERRIDE=9999 bash "$script"

[ "$(cat "$HOME/.claude/.cache-timestamp")" = "active" ] \
  && pass "UserPromptSubmit writes legacy 'active'" \
  || fail "UserPromptSubmit legacy" "got '$(cat "$HOME/.claude/.cache-timestamp")'"

grep -q '"state":"active"' "$HOME/.claude/cache-timers/abc.json" \
  && pass "UserPromptSubmit per-session active" \
  || fail "UserPromptSubmit state" "content: $(cat "$HOME/.claude/cache-timers/abc.json")"

# --- Stop ---
echo '{"session_id":"abc","cwd":"/c/Users/w/projects/demo","hook_event_name":"Stop"}' \
  | PPID_OVERRIDE=9999 bash "$script"

legacy=$(cat "$HOME/.claude/.cache-timestamp")
[[ "$legacy" =~ ^idle:[0-9]+$ ]] \
  && pass "Stop writes legacy 'idle:<epoch>'" \
  || fail "Stop legacy format" "got '$legacy'"

grep -q '"state":"idle"' "$HOME/.claude/cache-timers/abc.json" \
  && pass "Stop per-session state=idle" \
  || fail "Stop state" "content: $(cat "$HOME/.claude/cache-timers/abc.json")"

grep -qE '"epoch":[0-9]+' "$HOME/.claude/cache-timers/abc.json" \
  && pass "Stop records epoch" \
  || fail "Stop epoch" "content: $(cat "$HOME/.claude/cache-timers/abc.json")"

# --- Same cwd, new session_id removes stale sibling ---
echo '{"session_id":"new","cwd":"/c/Users/w/projects/demo","hook_event_name":"SessionStart"}' \
  | PPID_OVERRIDE=9999 bash "$script"

[ ! -f "$HOME/.claude/cache-timers/abc.json" ] \
  && pass "SessionStart removes stale sibling for same cwd" \
  || fail "stale sibling" "abc.json still exists"

[ -f "$HOME/.claude/cache-timers/new.json" ] \
  && pass "SessionStart writes new session file" \
  || fail "new session file" "missing"

rm -rf "$tmp"
[ "$fail" -eq 0 ] && { printf "\nAll tests passed\n"; exit 0; } || { printf "\n%d failures\n" "$fail"; exit 1; }
