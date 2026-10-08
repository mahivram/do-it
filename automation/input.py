import win32api
import win32con


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
_KEYS.update({chr(code).lower(): code for code in range(ord("A"), ord("Z") + 1)})
_KEYS.update({str(digit): ord(str(digit)) for digit in range(10)})
_KEYS.update({f"f{number}": win32con.VK_F1 + number - 1 for number in range(1, 13)})
_VK_PACKET = 0xE7
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002
_MOUSE_BUTTONS = {
    "left": (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP),
    "right": (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
    "middle": (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
}


def type_text(text: str) -> str:
    """Type Unicode text into the currently focused application."""
    if len(text) > 5000:
        raise ValueError("Text is limited to 5000 characters per call")

    encoded_text = text.encode("utf-16-le")
    for index in range(0, len(encoded_text), 2):
        unit = int.from_bytes(encoded_text[index : index + 2], byteorder="little")
        win32api.keybd_event(_VK_PACKET, unit, _KEYEVENTF_UNICODE, 0)
        win32api.keybd_event(
            _VK_PACKET,
            unit,
            _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP,
            0,
        )
    return f"Typed {len(text)} characters"


def press_key(key: str, modifiers: list[str] | None = None) -> str:
    """Press and release a named key, optionally with modifier keys."""
    key_name = key.lower()
    modifier_names = [modifier.lower() for modifier in (modifiers or [])]
    if key_name not in _KEYS:
        raise ValueError(f"Unsupported key: {key}")
    if any(name not in {"ctrl", "control", "alt", "shift", "win"} for name in modifier_names):
        raise ValueError("Modifiers must be ctrl, alt, shift, or win")

    modifier_codes = [_KEYS[name] for name in modifier_names]
    pressed: list[int] = []
    try:
        for code in [*modifier_codes, _KEYS[key_name]]:
            win32api.keybd_event(code, 0, 0, 0)
            pressed.append(code)
    finally:
        for code in reversed(pressed):
            win32api.keybd_event(code, 0, _KEYEVENTF_KEYUP, 0)
    return f"Pressed {'+'.join([*modifier_names, key_name])}"


def move_mouse(x: int, y: int) -> str:
    """Move the mouse pointer to absolute screen coordinates."""
    win32api.SetCursorPos((x, y))
    return f"Moved mouse to ({x}, {y})"


def click_mouse(button: str = "left", clicks: int = 1) -> str:
    """Click a mouse button at the current pointer position."""
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


def scroll_mouse(delta: int) -> str:
    """Scroll the mouse wheel; positive values scroll up, negative down."""
    if delta == 0:
        raise ValueError("Scroll delta must not be zero")
    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
    return f"Scrolled mouse wheel by {delta}"
