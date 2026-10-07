"""Compatibility imports for existing scripts using win32_helper."""

from automation.input import (
    click_mouse,
    move_mouse,
    press_key,
    scroll_mouse,
    type_text,
)
from automation.windows import (
    close_window,
    find_window_by_title,
    focus_and_bring_to_front,
    get_active_windows,
    open_window,
    set_window_bounds,
)

__all__ = [
    "click_mouse",
    "close_window",
    "find_window_by_title",
    "focus_and_bring_to_front",
    "get_active_windows",
    "move_mouse",
    "open_window",
    "press_key",
    "scroll_mouse",
    "set_window_bounds",
    "type_text",
]
