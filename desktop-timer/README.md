# TTYL desktop companion

Floating pill windows for the TTYL Claude Code plugin. One pill per
active Claude session; flashes when Claude finishes a turn; clicks
jump you back to the owning VSCode instance.

## Install (dev)

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
# Produces dist/TTYL.exe — copy anywhere, run once, then use tray
# "Start on login" to launch automatically.
```

## Manual test matrix

1. **Single session** — Start Claude in VSCode, send prompt, wait for response. Expected: gray "no cache" → blue "active" → flash + green countdown.
2. **Two concurrent sessions on two desktops** — both pills visible, flash independently, click each to focus the correct VSCode.
3. **Crash mid-session** — kill Claude with Ctrl+C. Expected: pill stays until 1 h stale, then GC'd by the watcher.
4. **Drag + restart** — drag pill to a new position, restart the app. Expected: pill reopens at the saved position (when mode is "Remember per project").
5. **Mode toggle** — flip to "Cascade in corner". Expected: new sessions ignore saved positions and stack from the top-right.
6. **Same-project session restart** — end Claude, start again in the same VSCode. Expected: pill keeps its position, no flicker (rebinds via `session_replaced`).
7. **Virtual desktop switch** — switch desktops. Expected: within 1 s, pill appears on the new desktop.
8. **Right-click → Dismiss** — pill disappears within 1 s, state file removed from `~/.claude/cache-timers/`.
9. **Right-click → Copy session ID** — clipboard contains the session UUID.
10. **Tray → Start on login** — toggle on, confirm `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\TTYL.lnk` exists; toggle off, confirm it's gone.

## Tests

```bash
.venv\Scripts\activate
pytest tests/ -v
```
