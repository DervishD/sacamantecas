"""Helpers for test units."""
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

class LogPaths(NamedTuple):  # pylint: disable=unused-variable
    """Log paths abstraction."""  # noqa: D204
    log: Path
    debug: Path
