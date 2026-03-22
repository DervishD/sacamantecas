"""Helpers for test units."""
from typing import NamedTuple, TYPE_CHECKING

from sacamantecas import Constants

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path
    from typing import Any


class LogPaths(NamedTuple):  # pylint: disable=unused-variable
    """Log paths abstraction."""  # noqa: D204
    log: Path
    trace: Path


def remove_logging_timestamps (contents: Sequence[str]) -> Sequence[str]:  # pylint: disable=unused-variable
    """Process *contents*, removing timestamps."""
    return [' '.join(line.split(' ')[1:]) for line in contents]


def format_log_message(message: str, *, levelname:str = '', padding: str = '') -> list[str]:  # pylint: disable=unused-variable
    """Format *message* so it looks like a logging entry.

    The *levelname* is prepended to the message if provided, and in that
    case a separator is appended.

    If *padding* is provided, it is inserted before the message.
    """
    if levelname:
        preamble = f'{levelname:<{Constants.LOGGING_LEVELNAME_MAX_LEN}}{Constants.LOGGING_LEVELNAME_SEPARATOR}'
    else:
        preamble = ''
    return [f'{preamble}{padding}{line}'.rstrip() for line in message.split('\n')]


class CallableSpy[**P, R]:  # pylint: disable=unused-variable, too-few-public-methods
    """Generic spy pattern for callables."""

    def __init__(self, target: Callable[P, R]) -> None:
        """."""
        self.target = target

        self.called: bool = False
        self.call_count: int = 0
        self.calls: list[tuple[R, tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """."""
        self.called = True
        self.call_count += 1

        retval = self.target(*args, **kwargs)
        self.calls.append((retval, args, kwargs))

        return retval
