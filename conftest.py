"""Configuration file for pytest."""
import os
import subprocess
from pathlib import Path
import pytest

@pytest.fixture
def unreadable_file(tmp_path: Path) -> Path:  # pylint: disable=unused-variable
    """Create a file which is unreadable by the current user."""
    filename = tmp_path / 'unreadable.ini'
    filename.write_text('')
    subprocess.run(['icacls', str(filename), '/deny', f'{os.environ["USERNAME"]}:R'], check=True)
    yield filename
    subprocess.run(['icacls', str(filename), '/grant', f'{os.environ["USERNAME"]}:R'], check=True)
    filename.unlink()
