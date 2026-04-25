# TTYL

**Talk To You Later** — know when Claude is done and never lose your prompt cache.

A small personal tool I built to keep myself on task while waiting for long Claude runs to finish across multiple parallel sessions. Two parts, in order of importance:

- **A floating Windows desktop tile** *(Windows 10/11 only — the primary feature)*. One always-on-top tile that lists every active Claude Code session as a row, flashes the row when Claude finishes a turn, shows a yellow "you-are-here" border on the row whose VSCode is currently focused, and **click-focuses the owning VSCode window** — the fastest way to jump back to whichever project Claude just finished thinking about.
- **A Claude Code status-line segment** *(any platform that runs bash — only useful if you use the `claude` CLI)*. Renders the cache TTL into Claude Code's status line. The Claude AI VSCode extension chat panel doesn't render Claude Code's `statusLine` at all, so this segment is invisible from there — the floating tile is what surfaces the cache state in that workflow.

Both parts read from the same per-session JSON state files written by the plugin's lifecycle hooks, so they work alongside each other (or independently). Works fine with the Claude AI VSCode extension; works fine with the `claude` CLI; works fine with both running in parallel.

Status-line segment when you do see it (CLI):
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

### Wire up your status line *(skip if you only use the VSCode extension)*

The Claude AI VSCode extension chat panel doesn't render Claude Code's `statusLine`, so there's nothing to wire up if that's your only interface — the floating tile is your indicator. This section is for users who run the `claude` CLI in a terminal.

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

## Desktop tile (Windows 10/11)

The primary feature. A floating always-on-top tile with one row per active Claude Code session — left-click any row to bring its VSCode window to the foreground, drag any row to move the whole tile, right-click for dismiss / copy session ID. The row whose VSCode is in the OS foreground gets a yellow border so you can tell at a glance which session corresponds to the editor in front of you.

Install instructions, manual test matrix, and the full feature list are in [`desktop-timer/README.md`](desktop-timer/README.md).

The desktop tile honors `TTYL_TTL_SECONDS` (default `300`, set to `3600` for the 1-hour cache beta) — the same role `CACHE_TTL_SECONDS` plays for the status-line segment.

> **Why Windows-only?** The tile relies on `SetForegroundWindow`, `IVirtualDesktopManager` (for following you across virtual desktops), and a Startup-folder `.lnk` shortcut. None of those have direct equivalents on macOS/Linux, and porting wasn't on my critical path. The plugin hooks and status-line segment are cross-platform — only the floating tile is Windows-only.

## Limitations and caveats

This is a personal tool, not a polished product — built quickly to scratch my own itch around running multiple parallel Claude sessions across virtual desktops. Sharing in case it's useful.

- **Floating tile is the reliable indicator; status-line segment is the rougher one.** The tile reads per-session JSONs directly and ticks at 1 Hz on its own clock. The status line goes through Claude Code's `refreshInterval` and emoji rendering varies by terminal — I've seen mis-aligned glyphs in some Git Bash + Windows Terminal combos. If the segment looks weird, trust the tile.
- **Status-line segment is invisible from the Claude AI VSCode extension.** The extension chat panel doesn't render Claude Code's `statusLine`. Not a TTYL bug — it's a Claude Code surface limitation. Use the floating tile in that workflow.
- **Approximation, not truth.** Anthropic doesn't publish the cache-expiry timestamp to the client. The countdown starts when the local `Stop` hook fires, which is ~milliseconds after the actual cache refresh. Close enough for practical use, not exact.
- **Floating tile is Windows 10/11 only** — see the [Desktop tile](#desktop-tile-windows-1011) section above. The plugin hooks and status-line script are cross-platform (anywhere bash runs).
- **Hooks require bash.** Hooks rely on `date +%s`, `echo`, and file redirection. Claude Code's default hook shell on Windows is Git Bash, which has these. Native PowerShell hooks aren't supported (PRs welcome).
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
