"""Context-local requests for user input from the active interface."""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Callable, Generator


UserInputHandler = Callable[[str, list[str] | None], str | None]

_user_input_handler: ContextVar[UserInputHandler | None] = ContextVar(
    "user_input_handler", default=None
)


@contextmanager
def use_user_input_handler(
    handler: UserInputHandler,
) -> Generator[None, None, None]:
    token: Token[UserInputHandler | None] = _user_input_handler.set(handler)
    try:
        yield
    finally:
        _user_input_handler.reset(token)


def request_user_input(
    question: str,
    options: list[str] | None = None,
    input_function: Callable[[str], str] = input,
) -> str | None:
    handler = _user_input_handler.get()
    if handler is not None:
        return handler(question, options)

    if options:
        print("\n".join(f"{index}. {option}" for index, option in enumerate(options, 1)))
    prompt = f"{question} "
    try:
        answer = input_function(prompt)
    except EOFError:
        return None

    if options and answer.strip().isdigit():
        index = int(answer.strip()) - 1
        if 0 <= index < len(options):
            return options[index]
    return answer.strip() or None
