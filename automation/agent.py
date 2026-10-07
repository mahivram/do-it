import json
import os
from pathlib import Path

from openai import OpenAI

from automation.tools import TOOLS, execute_tool_call


def _load_env_file() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return

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


_load_env_file()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)


def run_agent(user_prompt: str) -> None:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Windows Automation Agent. Use the provided tools to "
                "control the operating system based on the user's instructions. "
                "File operations are restricted to the project directory. When "
                "listing the project directory, call manage_files with action "
                "'list' and path '.'. Always provide every required tool argument. "
                "Only terminate a process when the user explicitly asks; identify "
                "its PID before calling kill_process."
                "System-changing operations require the user to type 'yes' "
                "in the terminal; never imply they have occurred if they cancel."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]
    print(f"\n[User Request]: {user_prompt}")

    while True:
        response = client.chat.completions.create(
            model="liquid/lfm-2.5-2.6b:free",
            messages=messages,
            tools=TOOLS,
            temperature=0.2,
        )
        response_message = response.choices[0].message
        messages.append(response_message)

        if not response_message.tool_calls:
            print(f"\n[Agent Response]: {response_message.content}")
            return

        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            raw_arguments = tool_call.function.arguments
            print(f"[Agent Tool Call]: {function_name}({raw_arguments})")
            result = execute_tool_call(function_name, raw_arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )
