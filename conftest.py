#! /usr/bin/env python3
"""Configuration file for pytest."""
from collections import namedtuple
import os
import subprocess

import pytest


LogPaths = namedtuple('LogPaths', ['log', 'debug'])
@pytest.fixture()
def log_paths(tmp_path):  # pylint: disable=unused-variable
    """Generate temporary filenames for logging files."""
    logfile_path = tmp_path / 'log.txt'
    debugfile_path = tmp_path / 'debug.txt'

    yield LogPaths(logfile_path, debugfile_path)

    logfile_path.unlink()
    debugfile_path.unlink()


@pytest.fixture()
def unreadable_file(tmp_path, filename):  # pylint: disable=unused-variable
    """Create a file which is unreadable by the current user."""
    filename = tmp_path / filename
    filename.write_text('')

    subprocess.run(['icacls', str(filename), '/deny', f'{os.environ["USERNAME"]}:R'], check=True)
    yield filename
    subprocess.run(['icacls', str(filename), '/grant', f'{os.environ["USERNAME"]}:R'], check=True)

    filename.unlink()
