import os
from pathlib import Path
from typing import Any, Callable

from automation.confirmations import ConfirmationHandler, use_confirmation_handler
from automation.interactions import UserInputHandler, use_user_input_handler
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


def _system_prompt(web_mode: bool = False) -> str:
    confirmation_instructions = (
        "Actions that request confirmation will pause and require the user to "
        "approve or cancel in the app before proceeding. Never bypass a "
        "confirmation request."
        if web_mode
        else "System-changing operations require the user to type 'yes' "
        "in the terminal; never imply they have occurred if they cancel."
    )
    telegram_confirmation = (
        "Never send a Telegram message unless the user approves the in-app "
        "confirmation."
        if web_mode
        else "Never send a Telegram message unless the user confirms by typing "
        "'yes' in the terminal."
    )
    dependency_confirmation = (
        "it will require in-app confirmation before installing only packages "
        "listed in requirements.txt into this Python interpreter."
        if web_mode
        else "it will ask the user to confirm in the terminal before installing "
        "only packages listed in requirements.txt into this Python interpreter."
    )
    return (
        "You are a Windows Automation Agent. Use the provided tools to "
        "control the operating system based on the user's instructions. "
        "Act on the live system, not a guessed or canned sequence. Ground every "
        "claim in actual tool results. After each action, inspect the resulting "
        "state before deciding or claiming the next step; report what was "
        "observed, including errors or uncertainty. For browser tasks, use "
        "get_active_windows and inspect_chrome_window to read the accessible "
        "Chrome state, then click_chrome_control only for a uniquely observed "
        "control. If an account or result choice is unclear, call ask_user with "
        "the actual observed choices and wait for the user's answer. If the "
        "screen content is not exposed to accessibility, say so and ask the "
        "user to clarify or perform that step; do not pretend it succeeded. "
        "If the user answers that they want to cancel or stop, do not take "
        "further actions. "
        "After typing or clicking, do not claim the page accepted it unless "
        "a subsequent inspection confirms the result. Perform at most one "
        "tool action from a tool-call batch; the other requested calls will "
        "be returned as not run. Review the actual result, then request the "
        "next action only when appropriate. "
        "File operations are restricted to the project directory. When "
        "listing the project directory, call manage_files with action "
        "'list' and path '.'. Always provide every required tool argument. "
        "Only terminate a process when the user explicitly asks; identify "
        "its PID before calling kill_process. "
        f"{confirmation_instructions} "
        "Telegram tools operate only on the user's logged-in Telegram "
        "Desktop UI; do not claim access to chats not visible or available "
        f"to that account. {telegram_confirmation} Use "
        "telegram_send_message with chat_name and text to search for the "
        "target and send; do not try to list all Telegram chats. If a tool "
        "reports a missing Python dependency, explain the need, then call "
        f"manage_project_dependencies with action 'install'; {dependency_confirmation}"
    )


def run_agent_request(
    user_prompt: str,
    provider_config: dict[str, str] | None = None,
    confirmation_handler: ConfirmationHandler | None = None,
    on_tool_event: Callable[[dict[str, Any]], None] | None = None,
    user_input_handler: UserInputHandler | None = None,
) -> dict[str, Any]:
    """Run one agent request and return its response and tool activity."""
    session = create_provider_session(
        _system_prompt(
            web_mode=confirmation_handler is not None or user_input_handler is not None
        ),
        user_prompt,
        TOOLS,
        provider_config=provider_config,
    )
    tool_events: list[dict[str, Any]] = []
    confirmation_context = (
        use_confirmation_handler(confirmation_handler)
        if confirmation_handler is not None
        else None
    )
    user_input_context = (
        use_user_input_handler(user_input_handler)
        if user_input_handler is not None
        else None
    )

    try:
        if confirmation_context is not None:
            confirmation_context.__enter__()
        if user_input_context is not None:
            user_input_context.__enter__()
        for _ in range(30):
            turn = session.next_turn()
            if not turn.tool_calls:
                return {"response": turn.text or "", "tools": tool_events}

            results = []
            for call_index, tool_call in enumerate(turn.tool_calls):
                event = {
                    "id": len(tool_events),
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                    "status": "running" if call_index == 0 else "skipped",
                }
                tool_events.append(event)
                if call_index > 0:
                    result = {
                        "error": (
                            "Not run: the agent performs one action at a time "
                            "and must inspect the previous result first. "
                            "Retry only if still needed."
                        )
                    }
                    event["result"] = result
                    if on_tool_event is not None:
                        on_tool_event(dict(event))
                    results.append(result)
                    continue

                if on_tool_event is not None:
                    on_tool_event(dict(event))

                try:
                    result = execute_tool_call(tool_call.name, tool_call.arguments)
                except Exception as exc:
                    event["status"] = "failed"
                    event["result"] = str(exc)
                    if on_tool_event is not None:
                        on_tool_event(dict(event))
                    raise

                event["status"] = (
                    "failed"
                    if isinstance(result, dict) and "error" in result
                    else "completed"
                )
                event["result"] = result
                if on_tool_event is not None:
                    on_tool_event(dict(event))
                results.append(result)
            session.add_tool_results(turn.tool_calls, results)
    finally:
        if user_input_context is not None:
            user_input_context.__exit__(None, None, None)
        if confirmation_context is not None:
            confirmation_context.__exit__(None, None, None)

    raise RuntimeError("Agent exceeded the 30-turn tool-call limit")


def run_agent(user_prompt: str) -> None:
    result = run_agent_request(user_prompt)
    print(f"\n[User Request]: {user_prompt}")
    for tool in result["tools"]:
        print(f"[Agent Tool Call]: {tool['name']}({tool['arguments']})")
    print(f"\n[Agent Response]: {result['response']}")
