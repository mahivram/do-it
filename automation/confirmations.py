"""Confirmation prompts that work in both the terminal and local web UI."""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Callable, Iterator


ConfirmationHandler = Callable[[str], bool]

_confirmation_handler: ContextVar[ConfirmationHandler | None] = ContextVar(
    "confirmation_handler", default=None
)


@contextmanager
def use_confirmation_handler(handler: ConfirmationHandler) -> Iterator[None]:
    token: Token[ConfirmationHandler | None] = _confirmation_handler.set(handler)
    try:
        yield
    finally:
        _confirmation_handler.reset(token)


def request_confirmation(
    action_description: str, input_function: Callable[[str], str]
) -> bool:
    """Require explicit approval from the active UI or the terminal."""
    handler = _confirmation_handler.get()
    if handler is not None:
        return handler(action_description)

    try:
        answer = input_function(
            f"{action_description}. Type 'yes' to confirm (anything else cancels): "
        )
    except EOFError:
        return False
    return answer.strip().lower() == "yes"
