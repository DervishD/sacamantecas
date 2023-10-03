#! /usr/bin/env python3
"""Test suite for load_profiles()."""
from pathlib import Path
import os
import subprocess
import pytest
from sacamantecas import MissingProfilesError, ProfilesSyntaxError, load_profiles


@pytest.fixture(name='unreadable_file')
def fixture_unreadable_file(tmp_path: Path) -> Path:  # pylint: disable=unused-variable
    """Create a file which is unreadable by the current user."""
    filename = tmp_path / 'unreadable.ini'
    filename.write_text('')

    subprocess.run(['icacls', str(filename), '/deny', f'{os.environ["USERNAME"]}:R'], check=True)
    yield filename
    subprocess.run(['icacls', str(filename), '/grant', f'{os.environ["USERNAME"]}:R'], check=True)

    filename.unlink()


def test_missing(tmp_path: Path) -> None:  # pylint: disable=unused-variable
    """Test for missing profiles configuration file."""
    filename = str(tmp_path / 'non_existent_profiles_file.ini')
    with pytest.raises(MissingProfilesError):
        load_profiles(filename)


def test_unreadable(unreadable_file: Path) -> None:  # pylint: disable=unused-variable
    """Test for unreadable profiles configuration file."""
    with pytest.raises(MissingProfilesError):
        load_profiles(str(unreadable_file))


@pytest.mark.parametrize("text,error", [
    ('o', 'MissingSectionHeader'),
    ('[s]\no', 'Parsing'),
    ('[s]\no = v\no = v', 'DuplicateOption'),
    ('[s]\no = (', 'BadRegex')
])
def test_syntax_errors(tmp_path: Path, text: str, error: str) -> None:  # pylint: disable=unused-variable
    """Test for syntax errors in profiles configuration file."""
    filename = tmp_path / 'profiles_syntax_error.ini'
    filename.write_text(text)

    with pytest.raises(ProfilesSyntaxError) as exc:
        load_profiles(str(filename))
    assert exc.value.error == error

    filename.unlink()


@pytest.mark.parametrize("text", ['', '[s]'])
def test_empty(tmp_path: Path, text: str) -> None:  # pylint: disable=unused-variable
    """Test for empty profiles configuration file."""
    filename = tmp_path / 'profiles_empty.ini'
    filename.write_text(text)

    assert load_profiles(str(filename)) == {}
