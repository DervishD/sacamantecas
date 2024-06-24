#! /usr/bin/env python3
"""Configuration file for pytest."""
from collections.abc import Generator
import os
from pathlib import Path
import subprocess
from typing import NamedTuple

import pytest


class LogPaths (NamedTuple):
    """Log paths abstraction."""  # noqa: D204
    log: Path
    debug: Path
@pytest.fixture
def log_paths(tmp_path: Path) -> Generator[LogPaths, None, None]:  # pylint: disable=unused-variable
    """Generate temporary filenames for logging files."""
    logfile_path = tmp_path / 'log.txt'
    debugfile_path = tmp_path / 'debug.txt'

    yield LogPaths(logfile_path, debugfile_path)

    logfile_path.unlink()
    debugfile_path.unlink()


@pytest.fixture
# pylint: disable-next=unused-variable
def unreadable_file(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path, None, None]:
    """Create a file which is unreadable by the current user."""
    filename = tmp_path / request.param
    filename.write_text('')

    subprocess.run(['icacls', str(filename), '/deny', f'{os.environ["USERNAME"]}:R'], check=True)
    yield filename
    subprocess.run(['icacls', str(filename), '/grant', f'{os.environ["USERNAME"]}:R'], check=True)

    filename.unlink()


@pytest.fixture
# pylint: disable-next=unused-variable
def unwritable_file(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path, None, None]:
    """Create a file which is not writable by the current user."""
    filename = tmp_path / request.param
    filename.write_text('')

    subprocess.run(['icacls', str(filename), '/deny', f'{os.environ["USERNAME"]}:W'], check=True)
    yield filename
    subprocess.run(['icacls', str(filename), '/grant', f'{os.environ["USERNAME"]}:W'], check=True)

    filename.unlink()
