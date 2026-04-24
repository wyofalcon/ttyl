# Floating Cache Timer — Design

**Date:** 2026-04-24
**Plugin:** `claude-cache-ttl`
**Author:** wyofalcon
**Status:** Draft, awaiting user approval

## Problem

The `claude-cache-ttl` plugin exposes cache TTL in the Claude Code statusline — but only in the terminal running Claude. When the user runs several Claude sessions in parallel across separate VSCode instances on separate Windows 11 virtual desktops, they cannot see cache state for a session without switching to its desktop.

The user previously built an external floating-window timer keyed to a VSCode instance, clickable to focus that instance. It worked but was inaccurate (it didn't hook into Claude Code lifecycle events). This spec describes rebuilding it on top of the plugin's accurate lifecycle hooks.

## Goals

- One always-on-top, clickable timer per active Claude session, visible on every virtual desktop.
- Clicking a timer brings its VSCode instance to the foreground (across virtual desktops).
- Timer stays visible after a session ends as a "resume — cache cold" launcher until the session restarts.
- Plugin remains a drop-in for users of just the statusline — nothing breaks if the desktop app is not installed.

## Non-goals

- Supporting editors other than VSCode.
- Supporting operating systems other than Windows 11. (Windows 10 works if `IVirtualDesktopManager` behaves; macOS/Linux not in scope.)
- Tracking cache state for Claude sessions that were not started from a VSCode integrated terminal (best-effort only — see fallback in *VSCode correlation*).
- A full configuration UI. All prefs live in a small JSON file plus the tray menu.

## Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code hooks (existing, rewritten)                     │
│                                                              │
│   SessionStart ─┐                                            │
│   UserPrompt  ──┼──► cache-hooks.sh ──► writes TWO files:   │
│   Stop        ──┘                                            │
│                                                              │
│                          │                                   │
│                          ├──► ~/.claude/.cache-timestamp    │
│                          │        (legacy, shared, unchanged)│
│                          │        → statusline segment       │
│                          │                                   │
│                          └──► ~/.claude/cache-timers/        │
│                                 <session-id>.json            │
│                                 (new, per-session)            │
│                                 → desktop app                 │
└─────────────────────────────────────────────────────────────┘
                                 │
                                 │  ~1 Hz poll
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Desktop tray app (new, Python + PyQt6)                      │
│                                                              │
│   QSystemTrayIcon ── right-click menu                        │
│                                                              │
│   watcher.py ── scans cache-timers/, emits Qt signals        │
│       │                                                      │
│       ├── on new session ─► spawn timer_window               │
│       ├── on state change ─► update existing timer_window    │
│       └── on stale/deleted ─► switch to "cache cold" mode    │
│                                                              │
│   timer_window.py ── frameless pill, 160×34px                │
│       ├── draws MM:SS + project name, colored                │
│       ├── click ─► vscode_finder.focus(session)              │
│       └── drag ─► updates config.py (per-project position)   │
│                                                              │
│   vdesk.py ── IVirtualDesktopManager COM wrapper             │
│   vscode_finder.py ── PID-walk + title-match                 │
└─────────────────────────────────────────────────────────────┘
```

## Plugin-side changes

### Hook rewrite

Current `hooks/hooks.json` contains inline `echo` commands. Replace with three calls to a single new script `scripts/cache-hooks.sh`, which:

1. Reads the hook input JSON from stdin (Claude Code sends `{session_id, cwd, hook_event_name, ...}`).
2. Writes the **legacy** shared file `~/.claude/.cache-timestamp` so the existing statusline segment continues to work exactly as before.
3. Writes a **per-session** JSON to `~/.claude/cache-timers/<session-id>.json`:

   ```json
   {
     "session_id": "abc123",
     "state": "idle",
     "epoch": 1745510400,
     "cwd": "/c/Users/Wyofa/projects/claude-cache-ttl",
     "project_name": "claude-cache-ttl",
     "pid": 12345,
     "started_at": 1745510100,
     "last_update": 1745510400,
     "hook_event": "Stop"
   }
   ```

   `pid` is the hook's **parent PID** (`$PPID` in bash) — this is the Claude Code process itself, which lives for the whole session. The hook script's own PID would be dead by the time the tray reads the file, so recording `$PPID` is required for `vscode_finder.py`'s PID-walk to have a valid starting point.

4. On `SessionStart` with a fresh `session_id`, removes any stale file for the same `cwd` (previous session of the same project).

The script is idempotent and fails silently — hooks should never disrupt a Claude session. If `jq` is not available, the script falls back to `sed`/`grep` extraction; if that fails, it writes minimal JSON and skips per-session tracking.

### Plugin manifest

`.claude-plugin/plugin.json` gets a version bump `0.1.0 → 0.2.0` and a note in `description` that the plugin also emits per-session state for external tools.

### Backward compatibility

- Existing users see no change: legacy state file is still written, `cache-segment.sh` unchanged.
- Users who don't install the desktop app: new per-session files accumulate but are garbage-collected by the desktop app; without it, the `cache-timers/` dir grows slowly. Mitigation: `cache-hooks.sh` also prunes any file in `cache-timers/` older than 24 h on each write.

## Desktop app

### Stack

- **Language:** Python 3.11+
- **UI:** PyQt6 (`QSystemTrayIcon`, `QWidget` with `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`)
- **Win32 interop:** `pywin32` (window enumeration, `SetForegroundWindow`), `comtypes` (virtual desktop COM), `psutil` (PID tree walking)
- **Packaging:** PyInstaller onefile (~30 MB) plus a raw `pip install -e .` path for users who have Python.

### Module layout

| Module | Responsibility |
|---|---|
| `__main__.py` | Entry point. Creates `QApplication`, tray icon, watcher. Runs Qt event loop. |
| `tray.py` | `QSystemTrayIcon` + menu ("Show all / Hide all / Position: remember per-project / Position: cascade / Start on login / Quit"). |
| `watcher.py` | `QFileSystemWatcher` + 1 Hz `QTimer` polling `~/.claude/cache-timers/`. Emits `session_added(path)`, `session_updated(path)`, `session_removed(path)`. Garbage-collects stale files (>1 h since `last_update`). |
| `timer_window.py` | Single frameless pill window. Draws `MM:SS · project-name` with color tied to state. Owns its HWND, drag behavior, click handling, and "cache cold" transition. |
| `vscode_finder.py` | Given a session's `pid` and `cwd`, returns the HWND of its VSCode window. Strategy: PID walk (psutil `parents()`) up to an `.exe` whose name contains `Code.exe`; if that fails, enumerate top-level windows and title-match `project_name`. |
| `vdesk.py` | Thin `comtypes` wrapper for `IVirtualDesktopManager`: `is_on_current_desktop(hwnd)`, `move_to_current_desktop(hwnd)`. Used to pin timer windows to whatever desktop the user is on. |
| `state.py` | Reads one session JSON, computes `(remaining_seconds, color, label)` tuples. No UI dependencies — unit-testable. |
| `config.py` | Reads/writes `%APPDATA%/claude-cache-timer/config.json`: per-project window positions, position-mode toggle, start-on-login flag. |

### Window behavior

A timer window is a 160×34 frameless translucent pill:

- **State → color** (matches statusline semantics):
  - `none` → gray "no cache"
  - `active` → blue "active"
  - `idle` + remaining >120s → green
  - `idle` + remaining 60–120s → yellow
  - `idle` + remaining <60s → red
  - `idle` + remaining ≤0 → red "cache cold" (clickable launcher mode)
- **Text:** `MM:SS · project-name`, truncated with ellipsis at 18 chars of project name.
- **Click:** Calls `vscode_finder.focus(session)` which:
  1. Looks up the cached HWND (recomputes every 30 s).
  2. Calls `SetForegroundWindow(hwnd)`. On Win11 this automatically switches virtual desktop if needed.
  3. If HWND is stale (window closed), falls back to title-match; if still nothing, shows a 2 s toast "VSCode window not found".
- **Drag:** Left-drag moves the pill. On mouse-up, `config.save_position(cwd, x, y)` if position-mode is "remember per-project".
- **Right-click:** Context menu — "Hide this timer" (for this session), "Copy session ID", "Dismiss (delete state file)".

### Position modes (toggle)

Tray menu has two radio items:
- **Remember per-project** (default): window spawns at the last saved position for its `cwd`. First-seen project defaults to top-right corner cascaded by index.
- **Cascade in corner**: window always spawns at top-right, offset by `(index * 38 px)` vertically. Dragging doesn't persist in this mode.

Toggle is read on every `session_added` event; existing windows don't move when the toggle flips.

### "Cache cold" mode

When a session's remaining time reaches 0:
- Pill stays visible but switches to red "cache cold · project-name".
- Click behavior is unchanged (still focuses VSCode).
- The window persists until either:
  - The same session's state file is updated (e.g., user sends a prompt → state becomes `active` → pill returns to normal).
  - A new `SessionStart` fires for the same `cwd` with a different `session_id`. In this case the watcher emits `session_replaced(old_id, new_id)`; the existing `TimerWindow` rebinds to the new JSON path and keeps its screen position. This avoids flicker when the user restarts a Claude session in the same project.
  - The user right-clicks → "Dismiss", which deletes the per-session state file.
  - The session file is >1 h stale → watcher garbage-collects it → window closes.

### Virtual-desktop handling

Windows 11 doesn't expose a public "show on all desktops" API. Our approach:

- On every `QTimer` tick (1 Hz), each timer window checks `vdesk.is_on_current_desktop(hwnd)`. If not, call `vdesk.move_to_current_desktop(hwnd)`.
- This means a timer follows the user across desktops rather than truly appearing on all of them — which matches the user's actual goal ("I want to see all timers wherever I am").

If the public COM API proves insufficient in practice (e.g., 1 Hz flicker on desktop switch), we can fall back to the undocumented `IVirtualDesktopManagerInternal::PinView` approach used by PowerToys. Not implemented initially.

### Start on login

Tray menu "Start on login" toggle writes/removes a `.lnk` shortcut in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` pointing at the installed executable. Implemented in `config.py` using `win32com.shell`.

## Data flow: full session example

1. User opens VSCode on virtual desktop 2, runs `claude` in integrated terminal.
2. `SessionStart` hook → `cache-hooks.sh` writes `~/.claude/cache-timers/abc123.json` with `state: "none"`, `cwd`, `pid`.
3. Tray's `watcher.py` sees new file → spawns `TimerWindow` for session `abc123`.
4. `TimerWindow` calls `vscode_finder.find(pid=..., cwd=...)` → walks PID tree → finds `Code.exe` → enumerates its windows → returns HWND of the VSCode window whose title contains `claude-cache-ttl`.
5. Pill appears top-right with text "no cache · claude-cache-ttl", gray. User's desktop is 1 → `vdesk.move_to_current_desktop(pill_hwnd)`.
6. User sends prompt. `UserPromptSubmit` hook → state file now `state: "active"` → pill turns blue, shows "active · claude-cache-ttl".
7. Claude responds. `Stop` hook → state file now `state: "idle", epoch: T` → pill starts counting down `5:00`, `4:59`, … green.
8. At `1:59`, pill turns yellow; at `0:59`, red.
9. User switches to virtual desktop 2. On next 1 Hz tick, pill's HWND moves to desktop 2.
10. User clicks pill → `SetForegroundWindow` on VSCode HWND → focus jumps to VSCode, virtual desktop switches if needed.
11. Counter hits 0 → pill becomes "cache cold · claude-cache-ttl", stays as launcher.
12. User sends new prompt → state returns to `active` → pill resumes normal behavior.
13. User closes Claude session cleanly → no `Stop` cleanup exists today (nothing to do). Eventually state file goes stale (>1 h) → watcher GCs → pill closes.

## Testing strategy

- **`state.py`:** Pure-function unit tests against frozen JSON fixtures.
- **`watcher.py`:** Integration tests using a `tmp_path` directory instead of `~/.claude/cache-timers/`; fake file creation/mutation and assert emitted signals.
- **`vscode_finder.py`:** Mock `psutil` and `win32gui.EnumWindows`; test PID-walk, title-match, and fallback paths.
- **`timer_window.py`:** `QTest` interactions — feed synthetic state transitions, assert color, text, and click routing.
- **Hook scripts:** Run `cache-hooks.sh` with piped JSON, assert file contents. Cross-check that legacy `.cache-timestamp` matches pre-change behavior byte-for-byte.
- **Manual test matrix** (documented in `desktop-timer/README.md`):
  - 1 session, 1 project.
  - 2 concurrent sessions, 2 projects on 2 desktops.
  - Session crashes (state file goes stale).
  - User drags a pill, restarts app, pill restores to saved position.
  - Toggle position modes and verify behavior.

## Risks & open questions

1. **`IVirtualDesktopManager` stability** — Microsoft breaks this COM interface between Windows builds. Mitigation: version-detect the interface UUID; ship with known UUIDs for Win11 22H2 / 23H2 / 24H2. Re-evaluate on Win12.
2. **PID walking fragility** — if the user starts `claude` from a standalone terminal (not VSCode), PID walk finds no VSCode parent. Mitigation: title-match fallback. If that also fails, the timer still works as a pure indicator — click just shows "VSCode window not found".
3. **Same project opened twice in VSCode** — title-match returns the first HWND. Accept as a known limitation; PID walk (when it works) resolves the ambiguity by construction.
4. **Windows Defender / SmartScreen on first run of the PyInstaller exe** — unsigned. Mitigation: document in README. Signing is out of scope for v0.1.
5. **Multiple monitors** — `TimerWindow` clamps positions to available screen geometry on each spawn; positions saved off-screen get re-clamped.

## Build order

1. Plugin: rewrite `hooks/hooks.json` + new `scripts/cache-hooks.sh`. Verify legacy statusline still works.
2. Desktop app scaffold: `pyproject.toml`, `__main__.py`, tray icon with static "Quit" menu.
3. `state.py` + unit tests (pure logic).
4. `watcher.py` + integration tests.
5. `timer_window.py` — non-interactive first (fixed position, no click).
6. `vscode_finder.py` — PID walk + title-match, mocked tests, then live smoke test.
7. `vdesk.py` — virtual desktop tracking, live smoke test.
8. Wire click → `vscode_finder.focus()`.
9. Drag + position persistence + mode toggle.
10. "Cache cold" mode + GC.
11. Start-on-login.
12. README, manual test matrix, PyInstaller build.

Each step commits independently so the project is usable at any point.
