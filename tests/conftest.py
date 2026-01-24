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
    """Generate temporary paths for logging files in *tmp_path*."""
    main_output_path = tmp_path / 'log.txt'
    full_output_path = tmp_path / 'trace.txt'

    yield LogPaths(main_output_path, full_output_path)

    main_output_path.unlink()
    full_output_path.unlink()


@pytest.fixture
# pylint: disable-next=unused-variable
def unreadable_path(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path]:
    """Create a file in *tmp_path*, unreadable by the current user."""
    path = tmp_path / request.param
    path.write_text('')

    subprocess.run(['icacls', str(path), '/inheritance:r'], check=True)  # noqa: S603, S607
    yield path

    path.unlink()


@pytest.fixture
# pylint: disable-next=unused-variable
def unwritable_path(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path]:
    """Create a file in *tmp_path*, non writable by the current user."""
    path = tmp_path / request.param
    path.write_text('')

    subprocess.run(['icacls', str(path), '/deny', f'{os.environ["USERNAME"]}:W'], check=True)  # noqa: S603, S607
    yield path
    subprocess.run(['icacls', str(path), '/grant', f'{os.environ["USERNAME"]}:W'], check=True)  # noqa: S603, S607

    path.unlink()
