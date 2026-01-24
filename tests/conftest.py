#! /usr/bin/env python3
"""Configuration file for pytest."""
import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from .helpers import LogPaths

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def log_paths(tmp_path: Path) -> Generator[LogPaths]:  # pylint: disable=unused-variable
    """Generate temporary filenames for logging files in *tmp_path*."""
    logfile_path = tmp_path / 'log.txt'
    debugfile_path = tmp_path / 'debug.txt'

    yield LogPaths(logfile_path, debugfile_path)

    logfile_path.unlink()
    debugfile_path.unlink()


@pytest.fixture
# pylint: disable-next=unused-variable
def unreadable_file(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path]:
    """Create a file in *tmp_path*, unreadable by the current user."""
    filename = tmp_path / request.param
    filename.write_text('')

    subprocess.run(['icacls', str(filename), '/inheritance:r'], check=True)  # noqa: S603, S607
    yield filename

    filename.unlink()


@pytest.fixture
# pylint: disable-next=unused-variable
def unwritable_file(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path]:
    """Create a file in *tmp_path*, non writable by the current user."""
    filename = tmp_path / request.param
    filename.write_text('')

    subprocess.run(['icacls', str(filename), '/deny', f'{os.environ["USERNAME"]}:W'], check=True)  # noqa: S603, S607
    yield filename
    subprocess.run(['icacls', str(filename), '/grant', f'{os.environ["USERNAME"]}:W'], check=True)  # noqa: S603, S607

    filename.unlink()
