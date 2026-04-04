"""Configuration file for pytest."""
import os
from pathlib import Path
import subprocess
from textwrap import dedent
import tomllib
from typing import TYPE_CHECKING

import pytest

from .helpers import LogPaths

if TYPE_CHECKING:
    from collections.abc import Generator

METADATA_GENERATOR_SCRIPT = Path('scripts', 'generate_metadata.py')
MISSING_PROJECT_METADATA_MODULE_ERROR = dedent(f"""
    Missing project metadata module '{{}}'.
    Run '{METADATA_GENERATOR_SCRIPT}' to generate the module.
""").strip()
def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Preliminary assertions."""
    project_root = Path(subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],  # noqa: S607
        encoding='utf-8',
        capture_output=True,
        check=True,
    ).stdout.strip())
    metadata = tomllib.loads((project_root / 'pyproject.toml').read_text(encoding='utf-8'))
    about_path = Path(metadata['tool']['local']['sources_root']).resolve() / metadata['project']['name'] / 'about.py'

    if not about_path.is_file():
        raise RuntimeError(MISSING_PROJECT_METADATA_MODULE_ERROR.format(about_path))


@pytest.fixture
def log_paths(tmp_path: Path) -> Generator[LogPaths]:
    """Generate temporary paths for logging files in *tmp_path*."""
    main_output_path = tmp_path / 'log.txt'
    full_output_path = tmp_path / 'trace.txt'

    yield LogPaths(main_output_path, full_output_path)

    main_output_path.unlink()
    full_output_path.unlink()


@pytest.fixture
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
