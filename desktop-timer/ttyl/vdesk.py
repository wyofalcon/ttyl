"""Windows 11 virtual desktop COM helpers.

Wraps IVirtualDesktopManager. The public COM interface gives us
what we need: 'is the window on the current desktop?' and 'move
window to current desktop'. Timer pills thus follow the user as
they switch desktops rather than being truly multi-homed - which
is the intended UX.
"""

from __future__ import annotations

import ctypes
from typing import Optional

try:
    import comtypes  # type: ignore
    import comtypes.client  # type: ignore
    from comtypes import GUID, IUnknown  # type: ignore
except ImportError:
    comtypes = None  # type: ignore


CLSID_VirtualDesktopManager = "{aa509086-5ca9-4c25-8f95-589d3c07b48a}"
IID_IVirtualDesktopManager = "{a5cd92ff-29be-454c-8d04-d82879fb3f1b}"


if comtypes:

    class _IVirtualDesktopManager(IUnknown):  # type: ignore[misc]
        _iid_ = GUID(IID_IVirtualDesktopManager)
        _methods_ = [
            comtypes.COMMETHOD([], ctypes.HRESULT, "IsWindowOnCurrentVirtualDesktop",
                (["in"], ctypes.c_void_p, "topLevelWindow"),
                (["out"], ctypes.POINTER(ctypes.c_int), "onCurrentDesktop")),
            comtypes.COMMETHOD([], ctypes.HRESULT, "GetWindowDesktopId",
                (["in"], ctypes.c_void_p, "topLevelWindow"),
                (["out"], ctypes.POINTER(GUID), "desktopId")),
            comtypes.COMMETHOD([], ctypes.HRESULT, "MoveWindowToDesktop",
                (["in"], ctypes.c_void_p, "topLevelWindow"),
                (["in"], ctypes.POINTER(GUID), "desktopId")),
        ]
else:
    _IVirtualDesktopManager = None  # type: ignore[assignment]


_manager_instance = None


def _manager():
    global _manager_instance
    if comtypes is None or _IVirtualDesktopManager is None:
        return None
    if _manager_instance is None:
        try:
            _manager_instance = comtypes.client.CreateObject(
                GUID(CLSID_VirtualDesktopManager),
                interface=_IVirtualDesktopManager,
            )
        except OSError:
            return None
    return _manager_instance


def is_on_current_desktop(hwnd: int) -> bool:
    m = _manager()
    if m is None:
        return True
    try:
        return bool(m.IsWindowOnCurrentVirtualDesktop(hwnd))
    except Exception:
        return True


def move_to_current_desktop(hwnd: int) -> None:
    """Move hwnd to the desktop where the current foreground window lives."""
    m = _manager()
    if m is None:
        return
    try:
        import win32gui  # type: ignore
        fg = win32gui.GetForegroundWindow()
        if not fg:
            return
        desktop_id = m.GetWindowDesktopId(fg)
        m.MoveWindowToDesktop(hwnd, ctypes.byref(desktop_id))
    except Exception:
        pass
