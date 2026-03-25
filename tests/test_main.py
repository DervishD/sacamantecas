#! /usr/bin/env python3
"""Test suite for `main()` function."""

from typing import TYPE_CHECKING

from legion import format_message

from sacamantecas import Constants, ExitCodes, main, Messages

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


# pylint: disable-next=unused-variable
def test_no_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test handling of missing command line arguments."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    assert main() == ExitCodes.NO_ARGUMENTS

    captured = capsys.readouterr()

    assert captured.out == f'{Messages.APP_BANNER}\n{Messages.PROCESS_DONE}\n'

    heading = f'{Messages.ERROR_PREFIX}{Messages.NO_ARGUMENTS_HEADING[0].lower()}{Messages.NO_ARGUMENTS_HEADING[1:]}'
    message = Messages.NO_ARGUMENTS_INSTRUCTIONS
    expected = f'{format_message(heading, message, indentation=Constants.ERROR_PAYLOAD_INDENTATION)}\n'
    assert captured.err == expected


# pylint: disable-next=unused-variable
def test_missing_ini(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test for missing main INI file."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    path = tmp_path / 'non_existent.ini'
    monkeypatch.setattr(Constants, 'INIFILE_PATH', path)

    assert main('') == ExitCodes.ERROR

    result = '\n'.join(capsys.readouterr().err.split('\n')[0:2])
    message = Messages.MISSING_PROFILES.format(path)
    expected = f'{Messages.ERROR_PREFIX}{message[0].lower() + message[1:]}'

    assert result == expected


# pylint: disable-next=unused-variable
def test_ini_syntax_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test for syntax errors in INI file."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    path = tmp_path / 'profiles_syntax_error.ini'
    path.write_text('o')
    monkeypatch.setattr(Constants, 'INIFILE_PATH', path)

    assert main('') == ExitCodes.ERROR

    result = '\n'.join(capsys.readouterr().err.split('\n')[0:2])
    message = Messages.PROFILES_WRONG_SYNTAX.format('MissingSectionHeader')
    expected = f'{Messages.ERROR_PREFIX}{message[0].lower() + message[1:]}'

    assert result == expected

    path.unlink()
