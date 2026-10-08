import os
from pathlib import Path

from automation.providers import create_provider_session
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


def run_agent(user_prompt: str) -> None:
    system_prompt = (
        "You are a Windows Automation Agent. Use the provided tools to "
        "control the operating system based on the user's instructions. "
        "File operations are restricted to the project directory. When "
        "listing the project directory, call manage_files with action "
        "'list' and path '.'. Always provide every required tool argument. "
        "Only terminate a process when the user explicitly asks; identify "
        "its PID before calling kill_process. "
        "System-changing operations require the user to type 'yes' "
        "in the terminal; never imply they have occurred if they cancel. "
        "Telegram tools operate only on the user's logged-in Telegram "
        "Desktop UI; do not claim access to chats not visible or available "
        "to that account. Never send a Telegram message unless the user "
        "confirms by typing 'yes' in the terminal. Use "
        "telegram_send_message with chat_name and text to search for the "
        "target and send; do not try to list all Telegram chats. If a tool "
        "reports a missing Python dependency, explain the need, then call "
        "manage_project_dependencies with action 'install'; it will ask "
        "the user to confirm in the terminal before installing only "
        "packages listed in requirements.txt into this Python interpreter."
    )
    session = create_provider_session(system_prompt, user_prompt, TOOLS)
    print(f"\n[User Request]: {user_prompt}")

    while True:
        turn = session.next_turn()
        if not turn.tool_calls:
            print(f"\n[Agent Response]: {turn.text}")
            return

        results = []
        for tool_call in turn.tool_calls:
            function_name = tool_call.name
            raw_arguments = tool_call.arguments
            print(f"[Agent Tool Call]: {function_name}({raw_arguments})")
            results.append(execute_tool_call(function_name, raw_arguments))
        session.add_tool_results(turn.tool_calls, results)
