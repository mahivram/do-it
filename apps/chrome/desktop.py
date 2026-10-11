"""Read and interact with controls exposed by Chrome's Windows UIA tree."""

from typing import Any


MAX_VISIBLE_CONTROLS = 150


def _chrome_window(hwnd: int) -> Any:
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise RuntimeError("Chrome UI inspection requires pywinauto.") from exc

    window = Desktop(backend="uia").window(handle=hwnd)
    if not window.exists():
        raise ValueError(f"No accessible window found for handle {hwnd}.")
    title = str(window.window_text() or "")
    class_name = str(window.element_info.class_name or "")
    if not class_name.startswith("Chrome_WidgetWin_"):
        raise ValueError(f"Window {hwnd} is not a Chrome window: {title!r}.")
    return window


def _visible_controls(hwnd: int) -> tuple[Any, list[Any]]:
    window = _chrome_window(hwnd)
    controls = [
        control
        for control in window.descendants()
        if control.is_visible() and control.is_enabled()
    ]
    return window, controls


def inspect_chrome_window(hwnd: int) -> dict[str, Any]:
    """Return accessible names and types for visible Chrome controls."""
    window, controls = _visible_controls(hwnd)
    visible = []
    for index, control in enumerate(controls[:MAX_VISIBLE_CONTROLS]):
        name = str(control.window_text() or "").strip()
        if not name:
            name = str(control.element_info.name or "").strip()
        control_type = str(control.element_info.control_type or "")
        if name or control_type:
            visible.append(
                {
                    "index": index,
                    "name": name,
                    "control_type": control_type,
                    "automation_id": str(control.element_info.automation_id or ""),
                }
            )

    return {
        "window": str(window.window_text() or ""),
        "controls": visible,
        "truncated": len(controls) > MAX_VISIBLE_CONTROLS,
        "note": (
            "Only controls exposed by Windows accessibility are listed; "
            "page content may be unavailable."
        ),
    }


def click_chrome_control(hwnd: int, name: str) -> str:
    """Click one uniquely named, enabled Chrome control."""
    if not name.strip():
        raise ValueError("Control name cannot be empty.")

    _, controls = _visible_controls(hwnd)
    matches = []
    for control in controls:
        control_name = str(control.window_text() or "").strip()
        if not control_name:
            control_name = str(control.element_info.name or "").strip()
        if control_name.casefold() == name.strip().casefold():
            matches.append(control)

    if not matches:
        raise ValueError(f"No visible Chrome control named {name!r} was found.")
    if len(matches) != 1:
        control_types = sorted(
            {str(control.element_info.control_type or "unknown") for control in matches}
        )
        raise ValueError(
            f"Chrome exposes {len(matches)} controls named {name!r} "
            f"({', '.join(control_types)}); inspect the window and choose a unique name."
        )

    matches[0].click_input()
    return f"Clicked visible Chrome control {name!r}."
