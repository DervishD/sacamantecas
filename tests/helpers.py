"""Helpers for test units."""
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any


class LogPaths(NamedTuple):  # pylint: disable=unused-variable
    """Log paths abstraction."""  # noqa: D204
    log: Path
    trace: Path


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
