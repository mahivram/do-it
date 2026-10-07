import os
import json
from pathlib import Path
from openai import OpenAI
from win32_helper import (
    close_window,
    focus_and_bring_to_front,
    get_active_windows,
    open_window,
)
from file_tools import manage_files

env_file = Path(__file__).with_name(".env")
if env_file.exists():
    for line_number, line in enumerate(
        env_file.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not name.strip():
            raise ValueError(f"Invalid entry in .env at line {line_number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name.strip(), value)

# OpenRouter uses the standard OpenAI client SDK
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

# 1. Define tools in JSON Schema format
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_active_windows",
            "description": "Get a list of currently open visible windows and their Win32 HWNDs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_and_bring_to_front",
            "description": "Bring a window to the foreground by its HWND integer handle.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hwnd": {"type": "integer", "description": "The window handle (HWND)"}
                },
                "required": ["hwnd"],
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
                    "application": {
                        "type": "string",
                        "description": "Executable name or path, such as notepad.exe.",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional command-line arguments.",
                    },
                },
                "required": ["application"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_window",
            "description": "Request a graceful close of a window using its HWND. Get the HWND with get_active_windows first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hwnd": {
                        "type": "integer",
                        "description": "The window handle (HWND) to close.",
                    }
                },
                "required": ["hwnd"],
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
                    "path": {
                        "type": "string",
                        "description": (
                            "File or folder path, relative to the project directory "
                            "or an absolute path inside it."
                        ),
                    },
                    "destination": {
                        "type": "string",
                        "description": "New path inside the project directory, for rename.",
                    },
                    "content": {
                        "type": "string",
                        "description": "UTF-8 text content for create_file or write_file.",
                    },
                },
                "required": ["action", "path"],
            },
        },
    },
]

# Map tool names to actual functions
TOOL_MAP = {
    "get_active_windows": get_active_windows,
    "focus_and_bring_to_front": focus_and_bring_to_front,
    "open_window": open_window,
    "close_window": close_window,
    "manage_files": manage_files,
}

TOOL_SCHEMAS = {
    tool["function"]["name"]: tool["function"]["parameters"]
    for tool in tools
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
    except TypeError as exc:
        return {"error": f"Invalid arguments for {function_name}: {exc}"}


def run_agent(user_prompt: str):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Windows Automation Agent. Use Win32 tools to control "
                "the operating system based on user instructions. File operations "
                "are restricted to the project directory. When listing the "
                "project directory, call manage_files with action 'list' and "
                "path '.'. Always provide every required tool argument."
            )
        },
        {"role": "user", "content": user_prompt}
    ]

    print(f"\n[User Request]: {user_prompt}")

    # Agent Loop
    while True:
        response = client.chat.completions.create(
            # Select any capable model on OpenRouter (e.g. Claude 3.5 Sonnet or GPT-4o)
            model="liquid/lfm-2.5-2.6b:free",
            messages=messages,
            tools=tools,
            temperature=0.2,
        )

        response_message = response.choices[0].message
        messages.append(response_message)

        # Check if LLM decided to execute a tool
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                fn_name = tool_call.function.name
                raw_args = tool_call.function.arguments

                print(f"[Agent Tool Call]: {fn_name}({raw_args})")

                # Execute tool
                result = execute_tool_call(fn_name, raw_args)

                # Send observation back to OpenRouter
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
        else:
            # Agent completed task or produced final answer
            print(f"\n[Agent Response]: {response_message.content}")
            break

if __name__ == "__main__":
    run_agent("open Notepad application and bring it to the front. and also whic which folder file here ")