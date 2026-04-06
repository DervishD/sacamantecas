"""Helpers for test units."""
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


# pylint: disable-next=unused-variable
class LogPaths(NamedTuple):
    """Log paths abstraction."""  # noqa: D204
    main: Path
    full: Path
