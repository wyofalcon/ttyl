# TTYL

**Talk To You Later** — know when Claude is done and never lose your prompt cache.

TTYL is a [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) plugin that ships two things:

- **A status line segment** showing live prompt-cache TTL — per Claude session, so two terminals don't share a single countdown.
- **An optional Windows desktop companion** that floats a single always-on-top tile listing every active Claude session, flashes the row when Claude finishes a turn, and click-focuses the owning VSCode window.

```
🟢 cache 4:32 | Opus 4.7 | my-project | main
🟡 cache 1:47 | Opus 4.7 | my-project | main
🔴 cache 0:28 | Opus 4.7 | my-project | main
🔴 cache expired | Opus 4.7 | my-project | main
🔄 active | Opus 4.7 | my-project | main       ← while Claude is thinking
```

## Why

Anthropic's prompt cache has a 5-minute TTL. Every request inside that window refreshes it; let it lapse and the next prompt re-pays full input-token cost (cache reads are 10% of input cost — a real savings on long Claude Code sessions).

Claude Code doesn't expose a cache expiry field to the status line, so nobody can render the "real" countdown. TTYL approximates it client-side from lifecycle hooks (`SessionStart`, `UserPromptSubmit`, `Stop`) — the countdown ticks only while Claude is idle, never while it's mid-request, since active requests are *refreshing* the cache.

## How it works

Five hooks route through one bash script that writes per-session state to `~/.claude/cache-timers/<session-id>.json` (and a legacy single-file mirror at `~/.claude/.cache-timestamp` for back-compat):

| Event | State written | Meaning |
|---|---|---|
| `SessionStart` | `none` | Fresh session, no request yet |
| `UserPromptSubmit` | `active` | Request in flight, cache refreshing |
| `PreCompact` | `active` | `/compact` in flight — treated as a refresh, since compaction sends a real request |
| `Stop` | `idle` (with epoch) | Turn ended, countdown starts |
| `SessionEnd` | (file deleted) | Session shut down — desktop tile removes the row |

The status line script reads the per-session file keyed by the `session_id` that Claude Code passes to it on stdin. Each terminal sees its own cache state.

If Claude is hard-killed (terminal closed, process crash) the `SessionEnd` hook can't fire. The desktop watcher catches that case by checking whether the recorded `pid` is still alive on each scan and evicting the row when the owning process is gone.

## Install

### As a Claude Code plugin (recommended)

Add to your `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "ttyl": {
      "source": {
        "source": "github",
        "repo": "wyofalcon/ttyl"
      }
    }
  },
  "enabledPlugins": {
    "ttyl@ttyl": true
  }
}
```

Or, for local development against a clone:

```json
{
  "extraKnownMarketplaces": {
    "local-ttyl": {
      "source": {
        "source": "directory",
        "path": "/absolute/path/to/your/ttyl/clone"
      }
    }
  },
  "enabledPlugins": {
    "ttyl@local-ttyl": true
  }
}
```

### Wire up your status line

You need both a `statusLine` command and `refreshInterval: 1` — the interval is what makes the countdown tick.

#### A — You don't have a custom status line

Use the bundled standalone. It renders `cache | model` and nothing else.

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/statusline-standalone.sh\"",
    "refreshInterval": 1
  }
}
```

#### B — You already have a custom status line

Invoke `cache-segment.sh` from your script and compose its output. Pass the session id along so the segment knows which file to read:

```bash
# inside your existing statusline.sh
input=$(cat)
session_id=$(echo "$input" | jq -r '.session_id // ""')
cache_seg=$(CLAUDE_SESSION_ID="$session_id" \
  bash "${CLAUDE_TTYL_ROOT}/scripts/cache-segment.sh")
[ -n "$cache_seg" ] && parts+=("$cache_seg")
```

Then in settings:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/my-statusline.sh",
    "refreshInterval": 1,
    "env": {
      "CLAUDE_TTYL_ROOT": "/absolute/path/to/the/installed/plugin"
    }
  }
}
```

> **Note:** Claude Code only sets `${CLAUDE_PLUGIN_ROOT}` when the status-line command is itself declared by the plugin. From your own statusline script, set `CLAUDE_TTYL_ROOT` explicitly — the marketplace install path includes a version segment (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>`) that changes on every plugin update, so a hardcoded fallback would break on upgrade.

## Tuning

The segment script honors:

| Variable | Default | Purpose |
|---|---|---|
| `CACHE_TTL_SECONDS` | `300` | Window length. Set to `3600` for the 1-hour cache beta. |
| `CACHE_TIMERS_DIR` | `~/.claude/cache-timers` | Per-session JSONs live here. |
| `CACHE_STATE_FILE` | `~/.claude/.cache-timestamp` | Legacy single-file fallback. |
| `CLAUDE_SESSION_ID` | (from stdin) | Override which session's state to render. |

## Desktop companion (optional, Windows)

For the full "Talk To You Later" experience — a floating aggregate tile with one row per active Claude session, flash on Claude-is-done, click-to-focus VSCode, and a yellow border on the row whose VSCode is currently focused — install the desktop companion from `desktop-timer/`. See [`desktop-timer/README.md`](desktop-timer/README.md).

The desktop tile honors `TTYL_TTL_SECONDS` (default `300`, set to `3600` for the 1-hour cache beta) — the same role `CACHE_TTL_SECONDS` plays for the status-line segment.

The status-line segment works standalone without the desktop app.

## Limitations and caveats

- **Approximation, not truth.** Anthropic doesn't publish the cache-expiry timestamp to the client. The countdown starts when your local `Stop` hook fires, which is ~milliseconds after the actual cache refresh. Close enough for practical use, not exact.
- **Requires bash.** Hooks rely on `date +%s`, `echo`, and file redirection. Claude Code's default hook shell on Windows is Git Bash, which has these. Native PowerShell hooks aren't supported (PRs welcome).
- **Optional `jq`.** The scripts use `jq` for JSON parsing when available and fall back to `sed` patterns otherwise. Install `jq` if you can — the fallback works but is more brittle on unusual whitespace.
- **No Anthropic-side verification.** If Anthropic changes the TTL or cache semantics, TTYL won't know. Sanity-check against the [prompt caching docs](https://docs.claude.com/en/docs/build-with-claude/prompt-caching) if behavior seems off.

## Uninstall

Remove the `enabledPlugins` entry from settings, then optionally clean up state:

```bash
rm -rf ~/.claude/cache-timers
rm -f ~/.claude/.cache-timestamp
```

## License

MIT — see [LICENSE](LICENSE).
