# TTYL

**Talk To You Later** — a Claude Code plugin + desktop companion that tells you when Claude is done working.

A small floating pill hovers on every virtual desktop, showing live prompt-cache TTL for each active Claude session. When Claude finishes a turn, the pill flashes so you notice from across the room. Click it to jump straight back to the owning VSCode window.

Also ships a minimal statusline segment for users who just want the cache countdown.

```
🟢 cache 4:32 | Opus 4.7 | my-project | main
🟡 cache 1:47 | Opus 4.7 | my-project | main
🔴 cache 0:28 | Opus 4.7 | my-project | main
🔴 cache expired | Opus 4.7 | my-project | main
🔄 active | Opus 4.7 | my-project | main       ← while Claude is thinking
```

## Why this exists

Anthropic's prompt cache has a 5-minute TTL. Every request within that window refreshes it; a gap of 5+ minutes makes your next prompt uncached — slower *and* more expensive (cache reads are 10% of input-token cost).

Claude Code doesn't expose a cache expiry field to the status line, so nobody can display the "real" countdown. This plugin approximates it client-side by tracking lifecycle events (`SessionStart`, `UserPromptSubmit`, `Stop`) and running a countdown only when Claude is idle — never while it's actively sending requests (which would be misleading, since those requests are *refreshing* the cache).

## How it works

Three hooks write a tiny state marker to `~/.claude/.cache-timestamp`:

| Event | Writes | Meaning |
|---|---|---|
| `SessionStart` | `none` | Fresh session, no request yet |
| `UserPromptSubmit` | `active` | Request in flight, cache refreshing |
| `Stop` | `idle:<epoch>` | Turn ended, countdown starts from `<epoch>` |

A helper script (`cache-segment.sh`) reads that state and prints the appropriate segment. You compose it into your own `statusLine`, or use the included standalone script if you don't have one.

## Install

### Option 1 — via a local marketplace entry

Add this to your `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "local-ttyl": {
      "source": {
        "source": "directory",
        "path": "/absolute/path/to/ttyl"
      }
    }
  },
  "enabledPlugins": {
    "ttyl@local-ttyl": true
  }
}
```

### Option 2 — via GitHub once published

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

## Configure the status line

You need **both** a `statusLine` and `refreshInterval: 1` — the interval is what makes the countdown tick every second.

### A — You don't have a custom status line yet

Use the bundled standalone. It shows `cache | model` and nothing else.

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/statusline-standalone.sh\"",
    "refreshInterval": 1
  }
}
```

### B — You already have a custom status line

Invoke `cache-segment.sh` from inside your own script and compose its output into your existing line. Example:

```bash
# somewhere in your existing statusline.sh:
cache_seg=$(bash "${CLAUDE_CACHE_TTL_ROOT:-$HOME/.claude/plugins/cache-ttl}/scripts/cache-segment.sh")
[ -n "$cache_seg" ] && parts+=("$cache_seg")
```

Then in settings:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ~/.claude/my-statusline.sh",
    "refreshInterval": 1
  }
}
```

> **Note:** `${CLAUDE_PLUGIN_ROOT}` is only set when the status line command itself is declared by the plugin. If you're calling the segment from a non-plugin script, resolve the path manually (see the `CLAUDE_CACHE_TTL_ROOT` fallback above).

## Tuning

The segment script honors two environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `CACHE_TTL_SECONDS` | `300` | Window length. Set to `3600` if you're using the 1-hour cache beta. |
| `CACHE_STATE_FILE` | `~/.claude/.cache-timestamp` | Where the hooks write state. Move it if you have multiple Claude installs that shouldn't share state. |

## Desktop companion app (optional)

For the full "Talk To You Later" experience — floating pill, flash on
finish, click-to-focus VSCode — install the desktop companion from
`desktop-timer/`. See `desktop-timer/README.md` for details.

The statusline segment works standalone without the desktop app.

## Limitations / caveats

- **Approximation, not truth.** Anthropic doesn't publish cache expiry to the client. The countdown starts from when your local `Stop` hook fired, which is seconds after the *actual* cache-refresh (close enough for practical use, but not exact).
- **Same state file across projects.** All your Claude Code projects share `~/.claude/.cache-timestamp`. If you run two sessions in parallel, they'll overwrite each other's state. In practice you only have one active session at a time, so this is usually fine.
- **Requires bash.** Hooks use `date +%s`, `echo`, file redirection. On Windows, Claude Code's default hook shell is Git Bash, which provides these. Native PowerShell is not supported — PRs welcome.
- **No Anthropic-side verification.** If Anthropic changes the TTL or cache refresh semantics, this plugin won't know. Check [Anthropic's prompt cache docs](https://docs.claude.com/en/docs/build-with-claude/prompt-caching) if behavior seems off.

## Uninstall

Remove the `enabledPlugins` entry from settings, and optionally clean up the state file:

```bash
rm ~/.claude/.cache-timestamp
```

## License

MIT — see [LICENSE](LICENSE).
