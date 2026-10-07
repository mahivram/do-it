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
]

# Map tool names to actual functions
TOOL_MAP = {
    "get_active_windows": get_active_windows,
    "focus_and_bring_to_front": focus_and_bring_to_front,
    "open_window": open_window,
    "close_window": close_window,
}

def run_agent(user_prompt: str):
    messages = [
        {
            "role": "system",
            "content": "You are a Windows Automation Agent. Use Win32 tools to control the operating system based on user instructions."
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
                fn_args = json.loads(tool_call.function.arguments)

                print(f"[Agent Tool Call]: {fn_name}({fn_args})")

                # Execute tool
                tool_func = TOOL_MAP.get(fn_name)
                if tool_func:
                    result = tool_func(**fn_args)
                else:
                    result = f"Error: Tool {fn_name} not found"

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
    run_agent("open Notepad application and bring it to the front.")