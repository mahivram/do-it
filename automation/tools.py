import json
from subprocess import SubprocessError

from apps.telegram.desktop import (
    open_chat,
    open_telegram,
    read_messages,
    search_chats,
    send_message,
)
from automation.dependencies import manage_project_dependencies
from automation.files import manage_files
from automation.input import (
    click_mouse,
    move_mouse,
    press_key,
    scroll_mouse,
    type_text,
)
from automation.processes import kill_process
from automation.system import (
    create_system_restore_point,
    get_hardware_info,
    get_power_info,
    get_system_info,
    get_system_uptime,
    list_environment_variables,
    manage_power,
    manage_windows_features,
    manage_windows_updates,
)
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
            "name": "manage_project_dependencies",
            "description": (
                "Check this project's required Python packages or install them "
                "from requirements.txt into the Python interpreter currently "
                "running the agent. Installation requires the user to type yes "
                "in the terminal. Use when a tool reports a missing dependency."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["check", "install"]}
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_open",
            "description": "Open or focus the user's logged-in Telegram Desktop app.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_search_chats",
            "description": "Search Telegram Desktop for a person, group, or channel by name.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_open_chat",
            "description": "Search for and open one uniquely matching Telegram chat, group, or channel.",
            "parameters": {
                "type": "object",
                "properties": {"chat_name": {"type": "string"}},
                "required": ["chat_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_read_messages",
            "description": "Read visible message text from the currently open Telegram chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_send_message",
            "description": "Search for and open the specified Telegram person, group, or channel, then send only after the user types yes in the terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_name": {
                        "type": "string",
                        "description": "Person, group, or channel to search for and message.",
                    },
                    "text": {"type": "string", "maxLength": 4096}
                },
                "required": ["chat_name", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get Windows OS version, build, and architecture.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_uptime",
            "description": "Get system uptime and last boot time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hardware_info",
            "description": "Get CPU, RAM, disk, and GPU information.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_environment_variables",
            "description": "List environment variables, redacting variables whose names indicate secrets or credentials.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_power",
            "description": "Shutdown, restart, sleep, hibernate, or lock Windows. Requires direct confirmation in the user's terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["shutdown", "restart", "sleep", "hibernate", "lock"],
                    }
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_system_restore_point",
            "description": "Create a Windows system restore point after direct terminal confirmation. May require administrator privileges and System Protection to be enabled.",
            "parameters": {
                "type": "object",
                "properties": {"description": {"type": "string"}},
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_windows_updates",
            "description": "List available Windows Updates, or install/hide a specific update by its update_id. Install and hide require direct terminal confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "install", "hide"],
                    },
                    "update_id": {
                        "type": "string",
                        "description": "Update GUID returned by the list action.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_windows_features",
            "description": "List Windows optional features, or enable/disable a feature. Changes require direct terminal confirmation and administrator privileges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "enable", "disable"],
                    },
                    "feature_name": {
                        "type": "string",
                        "description": "FeatureName returned by the list action.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_power_info",
            "description": "Get battery status and configured Windows power plans.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
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
    "manage_project_dependencies": manage_project_dependencies,
    "telegram_open": open_telegram,
    "telegram_search_chats": search_chats,
    "telegram_open_chat": open_chat,
    "telegram_read_messages": read_messages,
    "telegram_send_message": send_message,
    "get_system_info": get_system_info,
    "get_system_uptime": get_system_uptime,
    "get_hardware_info": get_hardware_info,
    "list_environment_variables": list_environment_variables,
    "manage_power": manage_power,
    "create_system_restore_point": create_system_restore_point,
    "manage_windows_updates": manage_windows_updates,
    "manage_windows_features": manage_windows_features,
    "get_power_info": get_power_info,
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
