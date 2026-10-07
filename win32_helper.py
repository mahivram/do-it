import win32gui
import win32con
import win32api
import subprocess
import time


_KEYS = {
    "backspace": win32con.VK_BACK,
    "delete": win32con.VK_DELETE,
    "down": win32con.VK_DOWN,
    "end": win32con.VK_END,
    "enter": win32con.VK_RETURN,
    "esc": win32con.VK_ESCAPE,
    "escape": win32con.VK_ESCAPE,
    "home": win32con.VK_HOME,
    "left": win32con.VK_LEFT,
    "page_down": win32con.VK_NEXT,
    "page_up": win32con.VK_PRIOR,
    "right": win32con.VK_RIGHT,
    "space": win32con.VK_SPACE,
    "tab": win32con.VK_TAB,
    "up": win32con.VK_UP,
    "ctrl": win32con.VK_CONTROL,
    "control": win32con.VK_CONTROL,
    "alt": win32con.VK_MENU,
    "shift": win32con.VK_SHIFT,
    "win": win32con.VK_LWIN,
}
_KEYS.update({f"f{number}": win32con.VK_F1 + number - 1 for number in range(1, 13)})
_VK_PACKET = 0xE7
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002
_MOUSE_BUTTONS = {
    "left": (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP),
    "right": (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
    "middle": (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
}


def type_text(text: str):
    """Types Unicode text into the currently focused application."""
    if len(text) > 5000:
        raise ValueError("Text is limited to 5000 characters per call")

    encoded_text = text.encode("utf-16-le")
    for index in range(0, len(encoded_text), 2):
        unit = int.from_bytes(encoded_text[index:index + 2], byteorder="little")
        win32api.keybd_event(_VK_PACKET, unit, _KEYEVENTF_UNICODE, 0)
        win32api.keybd_event(
            _VK_PACKET,
            unit,
            _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP,
            0,
        )
    return f"Typed {len(text)} characters"


def press_key(key: str, modifiers: list[str] | None = None):
    """Presses and releases a named key, optionally with modifier keys."""
    key_name = key.lower()
    modifier_names = [modifier.lower() for modifier in (modifiers or [])]
    if key_name not in _KEYS:
        raise ValueError(f"Unsupported key: {key}")
    if any(name not in {"ctrl", "control", "alt", "shift", "win"} for name in modifier_names):
        raise ValueError("Modifiers must be ctrl, alt, shift, or win")

    modifier_codes = [_KEYS[name] for name in modifier_names]
    key_code = _KEYS[key_name]
    pressed: list[int] = []
    try:
        for code in [*modifier_codes, key_code]:
            win32api.keybd_event(code, 0, 0, 0)
            pressed.append(code)
    finally:
        for code in reversed(pressed):
            win32api.keybd_event(code, 0, _KEYEVENTF_KEYUP, 0)
    return f"Pressed { '+'.join([*modifier_names, key_name]) }"


def move_mouse(x: int, y: int):
    """Moves the mouse pointer to absolute screen coordinates."""
    win32api.SetCursorPos((x, y))
    return f"Moved mouse to ({x}, {y})"


def click_mouse(button: str = "left", clicks: int = 1):
    """Clicks a mouse button at the current pointer position."""
    button_name = button.lower()
    if button_name not in _MOUSE_BUTTONS:
        raise ValueError("Button must be left, right, or middle")
    if not 1 <= clicks <= 10:
        raise ValueError("Click count must be between 1 and 10")

    down_flag, up_flag = _MOUSE_BUTTONS[button_name]
    for _ in range(clicks):
        win32api.mouse_event(down_flag, 0, 0, 0, 0)
        win32api.mouse_event(up_flag, 0, 0, 0, 0)
    return f"Clicked {button_name} mouse button {clicks} time(s)"


def scroll_mouse(delta: int):
    """Scrolls the mouse wheel; positive values scroll up, negative down."""
    if delta == 0:
        raise ValueError("Scroll delta must not be zero")
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
    return f"Scrolled mouse wheel by {delta}"


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
