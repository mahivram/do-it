"""Inspect and interact with controls exposed by Windows UI Automation."""

from typing import Any


MAX_VISIBLE_CONTROLS = 150


def accessible_window(hwnd: int) -> Any:
    """Return a UI Automation window for an HWND."""
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise RuntimeError("Windows UI inspection requires pywinauto.") from exc

    window = Desktop(backend="uia").window(handle=hwnd)
    if not window.exists():
        raise ValueError(f"No accessible window found for handle {hwnd}.")
    return window


def visible_controls(window: Any) -> list[Any]:
    """Return visible and enabled descendants exposed by a UIA window."""
    return [
        control
        for control in window.descendants()
        if control.is_visible() and control.is_enabled()
    ]


def control_name(control: Any) -> str:
    """Return the best accessible name for a control."""
    name = str(control.window_text() or "").strip()
    if not name:
        name = str(control.element_info.name or "").strip()
    return name


def inspect_window_controls(window: Any, note: str) -> dict[str, Any]:
    """Return accessible names and types for visible controls in a window."""
    controls = visible_controls(window)
    visible = []
    for index, control in enumerate(controls[:MAX_VISIBLE_CONTROLS]):
        name = control_name(control)
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
        "note": note,
    }


def click_window_control(window: Any, name: str, application: str) -> str:
    """Click one uniquely named visible control in a UIA window."""
    if not name.strip():
        raise ValueError("Control name cannot be empty.")

    controls = visible_controls(window)
    matches = [
        control
        for control in controls
        if control_name(control).casefold() == name.strip().casefold()
    ]
    if not matches:
        raise ValueError(f"No visible {application} control named {name!r} was found.")
    if len(matches) != 1:
        control_types = sorted(
            {str(control.element_info.control_type or "unknown") for control in matches}
        )
        raise ValueError(
            f"{application} exposes {len(matches)} controls named {name!r} "
            f"({', '.join(control_types)}); inspect the window and choose a unique name."
        )

    matches[0].click_input()
    return f"Clicked visible {application} control {name!r}."


def inspect_accessible_window(hwnd: int) -> dict[str, Any]:
    """Inspect accessible controls in any visible Windows application."""
    return inspect_window_controls(
        accessible_window(hwnd),
        "Only controls exposed by Windows accessibility are listed.",
    )


def click_accessible_control(hwnd: int, name: str) -> str:
    """Click one uniquely named visible control in any Windows application."""
    return click_window_control(accessible_window(hwnd), name, "window")
