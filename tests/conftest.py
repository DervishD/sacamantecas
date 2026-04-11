"""Configuration file for pytest."""
import os
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
# pylint: disable-next=unused-variable
def unreadable_path(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path]:
    """Create a file in *tmp_path*, unreadable by the current user."""
    path = tmp_path / request.param
    path.write_text('')

    subprocess.run(  # noqa: S603
        ['icacls', str(path), '/inheritance:r'],  # noqa: S607
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    yield path

    path.unlink()


@pytest.fixture
# pylint: disable-next=unused-variable
def unwritable_path(tmp_path: Path, request: pytest.FixtureRequest) -> Generator[Path]:
    """Create a file in *tmp_path*, non writable by the current user."""
    path = tmp_path / request.param
    path.write_text('')

    subprocess.run(  # noqa: S603
        ['icacls', str(path), '/deny', f'{os.environ["USERNAME"]}:W'],  # noqa:  S607
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    yield path
    subprocess.run(  # noqa: S603
        ['icacls', str(path), '/grant', f'{os.environ["USERNAME"]}:W'],  # noqa: S607
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    path.unlink()
