"""Read and interact with controls exposed by Chrome's Windows UIA tree."""

from typing import Any

from automation.accessibility import (
    accessible_window,
    click_window_control,
    inspect_window_controls,
)


def _chrome_window(hwnd: int) -> Any:
    window = accessible_window(hwnd)
    title = str(window.window_text() or "")
    class_name = str(window.element_info.class_name or "")
    if not class_name.startswith("Chrome_WidgetWin_"):
        raise ValueError(f"Window {hwnd} is not a Chrome window: {title!r}.")
    return window


def inspect_chrome_window(hwnd: int) -> dict[str, Any]:
    """Return accessible names and types for visible Chrome controls."""
    window = _chrome_window(hwnd)
    return inspect_window_controls(
        window,
        (
            "Only controls exposed by Windows accessibility are listed; "
            "page content may be unavailable."
        ),
    )


def click_chrome_control(hwnd: int, name: str) -> str:
    """Click one uniquely named, enabled Chrome control."""
    if not name.strip():
        raise ValueError("Control name cannot be empty.")

    return click_window_control(_chrome_window(hwnd), name, "Chrome")
