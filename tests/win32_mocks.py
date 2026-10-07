import sys
import types


def install_win32_mocks():
    con = types.ModuleType("win32con")
    constants = {
        "VK_BACK": 8,
        "VK_DELETE": 46,
        "VK_DOWN": 40,
        "VK_END": 35,
        "VK_RETURN": 13,
        "VK_ESCAPE": 27,
        "VK_HOME": 36,
        "VK_LEFT": 37,
        "VK_NEXT": 34,
        "VK_PRIOR": 33,
        "VK_RIGHT": 39,
        "VK_SPACE": 32,
        "VK_TAB": 9,
        "VK_UP": 38,
        "VK_CONTROL": 17,
        "VK_MENU": 18,
        "VK_SHIFT": 16,
        "VK_LWIN": 91,
        "VK_F1": 112,
        "MOUSEEVENTF_LEFTDOWN": 2,
        "MOUSEEVENTF_LEFTUP": 4,
        "MOUSEEVENTF_RIGHTDOWN": 8,
        "MOUSEEVENTF_RIGHTUP": 16,
        "MOUSEEVENTF_MIDDLEDOWN": 32,
        "MOUSEEVENTF_MIDDLEUP": 64,
        "MOUSEEVENTF_WHEEL": 2048,
        "WM_CLOSE": 16,
        "SW_RESTORE": 9,
        "SW_SHOW": 5,
        "SWP_NOZORDER": 4,
        "SWP_NOACTIVATE": 16,
    }
    for name, value in constants.items():
        setattr(con, name, value)

    api = types.ModuleType("win32api")
    api.key_events = []
    api.mouse_events = []
    api.cursor_positions = []
    api.keybd_event = lambda *args: api.key_events.append(args)
    api.mouse_event = lambda *args: api.mouse_events.append(args)
    api.SetCursorPos = lambda pos: api.cursor_positions.append(pos)

    gui = types.ModuleType("win32gui")
    gui.windows = {123: True}
    gui.visible_windows = {123: "Example window", 456: ""}
    gui.window_calls = []
    gui.IsWindow = lambda hwnd: hwnd in gui.windows
    gui.IsWindowVisible = lambda hwnd: hwnd in gui.visible_windows
    gui.GetWindowText = lambda hwnd: gui.visible_windows.get(hwnd, "")
    gui.IsIconic = lambda hwnd: False
    gui.ShowWindow = lambda *args: gui.window_calls.append(("show", *args))
    gui.SetForegroundWindow = lambda *args: gui.window_calls.append(("foreground", *args))
    gui.PostMessage = lambda *args: gui.window_calls.append(("post", *args))
    gui.SetWindowPos = lambda *args: gui.window_calls.append(("bounds", *args))
    gui.EnumWindows = lambda callback, extra: [
        callback(hwnd, extra) for hwnd in gui.visible_windows
    ]

    sys.modules.update({"win32con": con, "win32api": api, "win32gui": gui})
    return api, con, gui


win32api, win32con, win32gui = install_win32_mocks()
