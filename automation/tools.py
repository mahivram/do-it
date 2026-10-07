import json
from subprocess import SubprocessError

from automation.files import manage_files
from automation.input import (
    click_mouse,
    move_mouse,
    press_key,
    scroll_mouse,
    type_text,
)
from automation.processes import kill_process
from automation.windows import (
    close_window,
    focus_and_bring_to_front,
    get_active_windows,
    open_window,
    set_window_bounds,
)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_active_windows",
            "description": "Get visible open windows and their Win32 HWNDs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_and_bring_to_front",
            "description": "Bring a window to the foreground by its HWND.",
            "parameters": {
                "type": "object",
                "properties": {"hwnd": {"type": "integer"}},
                "required": ["hwnd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_window_bounds",
            "description": "Set a window's screen position and size by HWND. Width and height must be positive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hwnd": {"type": "integer"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "w": {"type": "integer"},
                    "h": {"type": "integer"},
                },
                "required": ["hwnd", "x", "y", "w", "h"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_window",
            "description": "Launch an application by executable name or path, optionally passing arguments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "application": {"type": "string"},
                    "args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["application"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_window",
            "description": "Request a graceful window close by HWND.",
            "parameters": {
                "type": "object",
                "properties": {"hwnd": {"type": "integer"}},
                "required": ["hwnd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "Force-terminate a process and all its child processes using its PID. This cannot be undone; first identify the PID and ensure the user requested termination.",
            "parameters": {
                "type": "object",
                "properties": {"pid": {"type": "integer", "minimum": 5}},
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_files",
            "description": (
                "List, read, create, write, delete, or rename files and folders "
                "inside the project directory only. Delete removes a folder and "
                "all its contents. Use rename with destination; use content for "
                "create_file or write_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list",
                            "read",
                            "create_file",
                            "write_file",
                            "create_folder",
                            "delete",
                            "rename",
                        ],
                    },
                    "path": {"type": "string"},
                    "destination": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["action", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type Unicode text into the currently focused application.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "maxLength": 5000}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press and release a named key, optionally with modifiers. Named keys include enter, tab, escape, arrows, backspace, delete, space, home, end, page_up, page_down, and f1-f12.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "modifiers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["ctrl", "alt", "shift", "win"],
                        },
                    },
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse pointer to absolute screen coordinates.",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_mouse",
            "description": "Click a mouse button at the current pointer position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                    },
                    "clicks": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_mouse",
            "description": "Scroll the mouse wheel; positive delta scrolls up and negative delta scrolls down.",
            "parameters": {
                "type": "object",
                "properties": {"delta": {"type": "integer"}},
                "required": ["delta"],
            },
        },
    },
]

TOOL_MAP = {
    "get_active_windows": get_active_windows,
    "focus_and_bring_to_front": focus_and_bring_to_front,
    "set_window_bounds": set_window_bounds,
    "open_window": open_window,
    "close_window": close_window,
    "kill_process": kill_process,
    "manage_files": manage_files,
    "type_text": type_text,
    "press_key": press_key,
    "move_mouse": move_mouse,
    "click_mouse": click_mouse,
    "scroll_mouse": scroll_mouse,
}

TOOL_SCHEMAS = {
    tool["function"]["name"]: tool["function"]["parameters"] for tool in TOOLS
}


def execute_tool_call(function_name: str, raw_arguments: str):
    tool_func = TOOL_MAP.get(function_name)
    if tool_func is None:
        return {"error": f"Tool {function_name} not found"}

    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON arguments for {function_name}: {exc.msg}"}

    if not isinstance(arguments, dict):
        return {"error": f"Arguments for {function_name} must be a JSON object"}

    required = TOOL_SCHEMAS[function_name].get("required", [])
    missing = [name for name in required if name not in arguments]
    if missing:
        return {
            "error": (
                f"Missing required argument(s) for {function_name}: "
                f"{', '.join(missing)}. Retry with all required arguments."
            )
        }

    try:
        return tool_func(**arguments)
    except (OSError, RuntimeError, SubprocessError, TypeError, ValueError) as exc:
        return {"error": f"Tool {function_name} failed: {exc}"}
