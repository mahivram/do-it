"""Telegram Desktop automation using its visible Windows UI Automation tree."""

import csv
import io
import os
import subprocess
import time
from typing import Any

from automation.input import press_key, type_text


class TelegramDesktopError(RuntimeError):
    """Raised when Telegram Desktop's visible UI cannot complete an action."""


class TelegramNotRunningError(TelegramDesktopError):
    """Raised when Telegram Desktop has no visible window yet."""


def _telegram_process_ids() -> set[int]:
    result = subprocess.run(
        ["tasklist.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise TelegramDesktopError(
            detail or f"Could not inspect running processes (exit {result.returncode})"
        )

    process_ids = set()
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and os.path.splitext(row[0])[0].casefold().startswith("telegram"):
            if row[1].isdigit():
                process_ids.add(int(row[1]))
    return process_ids


def _telegram_window() -> Any:
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise TelegramDesktopError(
            "Telegram UI automation requires pywinauto; install requirements.txt"
        ) from exc

    process_ids = _telegram_process_ids()
    windows = Desktop(backend="uia").windows(visible_only=True)
    for window in windows:
        if window.process_id() in process_ids:
            return window

    title_matches = [
        window
        for window in windows
        if "telegram" in (window.window_text() or "").casefold()
    ]
    if title_matches:
        return title_matches[0]
    if process_ids:
        raise TelegramNotRunningError(
            "Telegram Desktop is running, but no visible Telegram window was found. "
            "Restore or unlock its main window and retry."
        )
    else:
        raise TelegramNotRunningError(
            "Telegram Desktop is not running. Call telegram_open first."
        )


def open_telegram() -> str:
    """Open or focus Telegram Desktop using its registered tg:// protocol."""
    if os.name != "nt":
        raise TelegramDesktopError("Telegram Desktop automation is supported on Windows")

    try:
        os.startfile("tg://")
    except OSError as exc:
        raise TelegramDesktopError(
            f"Could not open Telegram Desktop via the tg:// protocol: {exc}"
        ) from exc

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            window = _telegram_window()
            window.set_focus()
            return "Opened or focused Telegram Desktop"
        except TelegramNotRunningError:
            time.sleep(0.25)
    raise TelegramDesktopError("Telegram Desktop did not become available within 15 seconds")


def _named_controls(window: Any) -> list[dict[str, Any]]:
    controls = []
    for control in window.descendants():
        if not control.is_visible():
            continue
        name = str(control.window_text() or "").strip()
        if not name:
            name = str(control.element_info.name or "").strip()
        if name:
            controls.append(
                {
                    "name": name,
                    "control_type": control.element_info.control_type,
                    "_control": control,
                }
            )
    return controls


def _search_box(window: Any) -> Any:
    edits = window.descendants(control_type="Edit")
    search_edits = []
    for edit in edits:
        if not edit.is_visible() or not edit.is_enabled():
            continue
        name = str(edit.window_text() or "").strip()
        if not name:
            name = str(edit.element_info.name or "").strip()
        if name.casefold() == "search":
            search_edits.append(edit)

    if not search_edits:
        search_buttons = [
            button
            for button in window.descendants(control_type="Button")
            if button.is_visible()
            and str(button.window_text() or "").strip().casefold() == "search"
        ]
        if search_buttons:
            search_buttons[0].click_input()
            search_edits = [
                edit
                for edit in window.descendants(control_type="Edit")
                if edit.is_visible()
                and edit.is_enabled()
                and str(edit.element_info.name or edit.window_text() or "")
                .strip()
                .casefold()
                == "search"
            ]

    if not search_edits:
        raise TelegramDesktopError(
            "Telegram's accessible Search field is not available in this window"
        )

    inner_edits = [
        edit
        for edit in search_edits
        if "inputfield::inner"
        in str(edit.element_info.class_name).casefold()
    ]
    search_box = inner_edits[-1] if inner_edits else search_edits[-1]
    search_box.click_input()
    return search_box


def _enter_search_query(window: Any, query: str) -> None:
    _search_box(window)
    press_key("a", ["ctrl"])
    type_text(query)
    time.sleep(0.75)


def search_chats(query: str) -> list[dict[str, str]]:
    """Search Telegram Desktop for a person, group, or channel by name."""
    if not query.strip():
        raise ValueError("Search query cannot be empty")

    window = _telegram_window()
    window.set_focus()
    _enter_search_query(window, query)

    chat_types = {"ListItem", "TreeItem", "DataItem"}
    results = [
        {"name": item["name"], "control_type": item["control_type"]}
        for item in _named_controls(window)
        if item["control_type"] in chat_types
        and query.casefold() in item["name"].casefold()
    ]
    return results


def open_chat(chat_name: str) -> str:
    """Search for and open a uniquely named visible chat result."""
    if not chat_name.strip():
        raise ValueError("Chat name cannot be empty")

    window = _telegram_window()
    window.set_focus()
    _enter_search_query(window, chat_name)

    chat_types = {"ListItem", "TreeItem", "DataItem"}
    matches = [
        item
        for item in _named_controls(window)
        if item["control_type"] in chat_types
        and chat_name.casefold() in item["name"].casefold()
    ]
    exact_matches = [
        item for item in matches if item["name"].casefold() == chat_name.casefold()
    ]
    candidates = exact_matches or matches
    if not candidates:
        raise TelegramDesktopError(f"No visible Telegram chat matched {chat_name!r}")
    if len(candidates) != 1:
        raise TelegramDesktopError(
            f"Chat search for {chat_name!r} was ambiguous; refine the search"
        )

    candidates[0]["_control"].click_input()
    return f"Opened Telegram chat: {candidates[0]['name']}"


def read_messages(limit: int = 30) -> list[str]:
    """Read text exposed by visible message-like controls in the current chat."""
    if not 1 <= limit <= 100:
        raise ValueError("Message limit must be between 1 and 100")

    window = _telegram_window()
    message_types = {"Text", "ListItem", "DataItem"}
    messages = []
    seen = set()
    for item in _named_controls(window):
        text = item["name"]
        if item["control_type"] in message_types and text not in seen:
            seen.add(text)
            messages.append(text)
    if not messages:
        raise TelegramDesktopError(
            "No visible message text is exposed by Telegram's UI Automation tree"
        )
    return messages[-limit:]


def send_message(chat_name: str, text: str) -> str:
    """Open a named person/channel and send a message after confirmation."""
    if not chat_name.strip():
        raise ValueError("Chat name cannot be empty")
    if not text.strip():
        raise ValueError("Message cannot be empty")
    if len(text) > 4096:
        raise ValueError("Telegram messages are limited to 4096 characters")

    open_chat_result = open_chat(chat_name)
    opened_chat_name = open_chat_result.removeprefix("Opened Telegram chat: ")
    window = _telegram_window()
    edits = [
        control
        for control in window.descendants(control_type="Edit")
        if control.is_visible() and control.is_enabled()
    ]
    if not edits:
        raise TelegramDesktopError(
            "No visible message input found; open the intended chat first"
        )
    if len(edits) > 1:
        raise TelegramDesktopError(
            "Multiple text inputs are visible; close search and select one chat first"
        )

    try:
        answer = input(
            f"Send this message to Telegram chat {opened_chat_name!r}? "
            "Type 'yes' to confirm: "
        )
    except EOFError:
        answer = ""
    if answer.strip().lower() != "yes":
        return "Cancelled Telegram message send"

    edits[0].click_input()
    type_text(text)
    press_key("enter")
    return f"Sent Telegram message to {opened_chat_name}"
