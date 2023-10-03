#! /usr/bin/env python3
"""Configuration file for pytest."""
from collections import namedtuple
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
