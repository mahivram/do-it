import win32gui
import win32con
import win32api
import subprocess
import time

def open_window(application: str, args: list[str] | None = None):
    """Launches an application by executable name or path."""
    process = subprocess.Popen([application, *(args or [])])
    return f"Started {application} with process ID {process.pid}"

def close_window(hwnd: int):
    """Requests a graceful close of the window identified by its HWND."""
    if not win32gui.IsWindow(hwnd):
        return f"Error: Invalid HWND {hwnd}"

    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    return f"Sent a close request to window handle {hwnd}"

def find_window_by_title(title_substring: str):
    """Finds a window handle (HWND) matching a partial title."""
    matches = []
    def enum_windows_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_substring.lower() in title.lower():
                matches.append((hwnd, title))
    win32gui.EnumWindows(enum_windows_callback, None)
    return matches

def focus_and_bring_to_front(hwnd: int):
    """Brings a window to the front and gives it focus using Win32 API."""
    if not win32gui.IsWindow(hwnd):
        return f"Error: Invalid HWND {hwnd}"

    # Restore window if minimized
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    win32gui.SetForegroundWindow(hwnd)
    return f"Successfully set focus to window handle {hwnd}"

def get_active_windows():
    """Returns a list of visible window titles and their handles."""
    windows = []
    def enum_callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                windows.append({"hwnd": hwnd, "title": title})
    win32gui.EnumWindows(enum_callback, None)
    return windows
