# TTYL desktop companion

A small, frameless, always-on-top tile that lists every active Claude
Code session with a live prompt-cache countdown. Each row click-focuses
the owning VSCode window. The row whose VSCode is currently in the
foreground shows a yellow border so you can tell at a glance which
session is "the one in front of you."

## What you get

- **One tile, many rows** — one row per active Claude session, stacked
  vertically. Two parallel sessions across two projects show up as two
  rows in the same tile.
- **Live countdown** — each row ticks at 1 Hz, transitioning
  `gray (no cache) → blue (active) → green/yellow/red (idle countdown)`
  as the cache window approaches expiry.
- **Flash on finish** — the row pulses with a soft drop-shadow glow
  when Claude finishes a turn (`active → idle` transition).
- **Click-to-focus VSCode** — left-click any row to bring its owning
  VSCode window to the foreground. Falls back to a project-name title
  match when the process tree is broken (common on Windows / Git Bash
  where `$PPID` returns 1).
- **Yellow "you-are-here" border** — the row whose VSCode is the OS
  foreground window gets a 2px yellow border, making it obvious which
  Claude session corresponds to the editor you're currently in.
- **Drag to move** — drag any row to reposition the whole tile;
  position persists in `%APPDATA%\ttyl\config.json`.
- **Right-click** for `Dismiss` (deletes the per-session state file →
  row vanishes) and `Copy session ID`.
- **Virtual desktop pinning** — the tile follows you across Windows 11
  virtual desktops via `IVirtualDesktopManager`.
- **System tray** — Show / Hide tile, Start on login, Quit.

## Install (development)

Requires Python 3.11+.

```bash
cd desktop-timer
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m ttyl
```

## Install (packaged)

```bash
python build.py
# Produces dist/TTYL.exe — copy anywhere, run once, then enable the
# tray "Start on login" option to launch automatically.
```

## How it works

The desktop app watches `~/.claude/cache-timers/` (the directory the
Claude Code plugin's hooks write to) at 1 Hz. Each `*.json` file there
represents one Claude session. When a file appears the tile adds a
row; when it disappears the row goes away; when its mtime changes the
row re-reads it.

Click-to-focus is handled in `ttyl/vscode_finder.py`:

1. If the recorded `pid` is plausible (>1), walk the process tree up
   to 12 levels looking for `Code.exe` / `Code - Insiders.exe`. If
   found, return the first visible top-level window for that PID.
2. Otherwise, enumerate all visible windows whose title contains
   `"Visual Studio Code"` and try each `cwd` path segment as a needle,
   deepest first. The first match wins.

The PID-walk is the precise path; the title-match fallback handles the
common Windows case where Git Bash hooks see `$PPID = 1` due to POSIX
subsystem indirection.

## Manual test matrix

1. **Single session** — start Claude in VSCode, send a prompt, wait
   for response. Expected: gray "no cache" → blue "active" → flash +
   green countdown.
2. **Two concurrent sessions on two desktops** — both rows visible in
   the single tile, flash independently, click each to focus the
   correct VSCode.
3. **Foreground tracking** — alt-tab between two VSCode windows; the
   yellow border should follow within ~1 s.
4. **Crash mid-session** — kill Claude with Ctrl+C. Expected: row
   stays until 1 h stale, then GC'd by the watcher.
5. **Drag + restart** — drag the tile to a new position, restart.
   Expected: tile reopens at the saved position (`tile_position` in
   `config.json`).
6. **Same-project session restart** — end Claude, start again in the
   same VSCode. Expected: same row keeps its position, no flicker
   (rebinds via `session_replaced`).
7. **Virtual desktop switch** — switch desktops. Expected: within 1 s,
   the tile appears on the new desktop.
8. **Right-click → Dismiss** — row disappears within 1 s, state file
   removed from `~/.claude/cache-timers/`.
9. **Right-click → Copy session ID** — clipboard contains the session
   UUID.
10. **Tray → Start on login** — toggle on, confirm
    `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TTYL.lnk`
    exists; toggle off, confirm it's gone.

## Tests

```bash
.venv\Scripts\activate
pytest tests/ -v
```

The pytest suite covers state computation, the filesystem watcher
(including the deferred-initial-scan regression so consumers see files
that exist before the watcher is constructed), the timer row's render
+ click + flash + foreground-border behavior, the aggregate tile's
add/remove/update/replace + tick + foreground tracking, the VSCode
finder's pid-walk and title-match fallback (including the multi-cwd-
segment search), and the persistent config.

## Architecture

```
~/.claude/cache-timers/<sid>.json   ← written by plugin hooks
        │
        ▼ (poll @ 1 Hz)
CacheTimersWatcher (watcher.py)
        │  emits session_added / updated / removed / replaced
        ▼
TtylApp (__main__.py)
        │  routes signals to:
        ▼
AggregateTile (aggregate_tile.py)
        │  one TimerRow per session
        ▼
TimerRow (timer_row.py)  ─── focus_requested ──▶  vscode_finder
                                                  │
                                                  ▼
                                            SetForegroundWindow(hwnd)
```

`vdesk.py` wraps `IVirtualDesktopManager` via `comtypes` so the tile
follows you across Windows 11 virtual desktops.

`config.py` persists tile position, the flash-on-finish toggle, and
the start-on-login Windows shortcut.

## Platform support

Windows 11 is the primary target. Linux / macOS aren't supported yet;
the foreground-window detection, virtual-desktop pinning, and start-
on-login shortcut all use Windows-only APIs. PRs welcome.
