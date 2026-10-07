import subprocess

import win32con
import win32gui


def open_window(application: str, args: list[str] | None = None) -> str:
    """Launch an application by executable name or path."""
    process = subprocess.Popen([application, *(args or [])])
    return f"Started {application} with process ID {process.pid}"


def close_window(hwnd: int) -> str:
    """Request a graceful close of the window identified by its HWND."""
    if not win32gui.IsWindow(hwnd):
        return f"Error: Invalid HWND {hwnd}"

    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    return f"Sent a close request to window handle {hwnd}"


def find_window_by_title(title_substring: str) -> list[tuple[int, str]]:
    """Find visible windows whose titles contain the given text."""
    matches: list[tuple[int, str]] = []

    def enum_windows_callback(hwnd: int, _extra: object) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_substring.lower() in title.lower():
                matches.append((hwnd, title))

    win32gui.EnumWindows(enum_windows_callback, None)
    return matches


def focus_and_bring_to_front(hwnd: int) -> str:
    """Restore and focus the window identified by its HWND."""
    if not win32gui.IsWindow(hwnd):
        return f"Error: Invalid HWND {hwnd}"

    show_command = win32con.SW_RESTORE if win32gui.IsIconic(hwnd) else win32con.SW_SHOW
    win32gui.ShowWindow(hwnd, show_command)
    win32gui.SetForegroundWindow(hwnd)
    return f"Successfully set focus to window handle {hwnd}"


def get_active_windows() -> list[dict[str, int | str]]:
    """Return visible windows with titles and HWNDs."""
    windows: list[dict[str, int | str]] = []

    def enum_callback(hwnd: int, _extra: object) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                windows.append({"hwnd": hwnd, "title": title})

    win32gui.EnumWindows(enum_callback, None)
    return windows


def set_window_bounds(hwnd: int, x: int, y: int, w: int, h: int) -> str:
    """Set a window's position and size without changing focus or z-order."""
    if not win32gui.IsWindow(hwnd):
        raise ValueError(f"Invalid HWND: {hwnd}")
    if w <= 0 or h <= 0:
        raise ValueError("Window width and height must be positive")

    flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(hwnd, 0, x, y, w, h, flags)
    return f"Set window {hwnd} bounds to ({x}, {y}, {w}, {h})"
