#! /usr/bin/env python3
"""Test suite for `main()` function."""

from importlib.metadata import metadata
from typing import TYPE_CHECKING

from sacamantecas import Constants, ExitCodes, main, Messages
from tests.helpers import format_log_message, remove_logging_timestamps

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tests.helpers import LogPaths

PADDING = ' ' * Constants.ERROR_PAYLOAD_INDENT

def test_logging_setup(log_paths: LogPaths, monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test for proper logging setup."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', log_paths.trace)

    assert not log_paths.log.is_file()
    assert not log_paths.trace.is_file()

    assert main() == ExitCodes.NO_ARGUMENTS

    assert log_paths.log.is_file()
    assert log_paths.trace.is_file()


def test_no_arguments(log_paths: LogPaths, monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test handling of missing command line arguments."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', log_paths.trace)

    assert main() == ExitCodes.NO_ARGUMENTS

    message = Messages.NO_ARGUMENTS[0].lower() + Messages.NO_ARGUMENTS[1:]

    result = remove_logging_timestamps(log_paths.log.read_text(encoding=Constants.UTF8).split('\n'))
    expected_log = [
        *format_log_message(Messages.APP_BANNER),
        *format_log_message(f'{Messages.ERROR_PREFIX}{message}'),
        *format_log_message(Messages.NO_ARGUMENTS_DETAILS, padding=PADDING),
        *format_log_message(Messages.PROCESS_DONE),
        '',
    ]

    assert result == expected_log

    result = remove_logging_timestamps(log_paths.trace.read_text(encoding=Constants.UTF8).split('\n'))
    dependency_packages = metadata(Constants.APP_NAME).get_all('Requires-Dist', {})
    dependency_banners = [Messages.DEPENDENCY_BANNER.format(pkg.replace('==', ' v')) for pkg in dependency_packages]
    expected_trace = [
        *format_log_message(Messages.DEBUGGING_INIT, levelname='DEBUG'),
        *format_log_message(Messages.APP_BANNER, levelname='INFO'),
        *format_log_message('\n'.join(dependency_banners), levelname='DEBUG'),
        *format_log_message(Constants.USER_AGENT, levelname='DEBUG'),
        *format_log_message(f'{Messages.ERROR_PREFIX}{message}', levelname='ERROR'),
        *format_log_message(Messages.NO_ARGUMENTS_DETAILS, levelname='ERROR', padding=PADDING),
        *format_log_message(Messages.PROCESS_DONE, levelname='INFO'),
        *format_log_message(Messages.DEBUGGING_DONE, levelname='DEBUG'),
        '',
    ]

    assert result == expected_trace


# pylint: disable-next=unused-variable
def test_missing_ini(
    log_paths: LogPaths,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test for missing main INI file."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', log_paths.trace)

    path = tmp_path / 'non_existent.ini'
    monkeypatch.setattr(Constants, 'INIFILE_PATH', path)

    assert main('') == ExitCodes.ERROR

    result = '\n'.join(capsys.readouterr().err.split('\n')[0:2])
    message = Messages.MISSING_PROFILES.format(path)
    expected = f'{Messages.ERROR_PREFIX}{message[0].lower() + message[1:]}'

    assert result == expected


# pylint: disable-next=unused-variable
def test_ini_syntax_error(
    log_paths: LogPaths,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test for syntax errors in INI file."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', log_paths.trace)

    path = tmp_path / 'profiles_syntax_error.ini'
    path.write_text('o')
    monkeypatch.setattr(Constants, 'INIFILE_PATH', path)

    assert main('') == ExitCodes.ERROR

    result = '\n'.join(capsys.readouterr().err.split('\n')[0:2])
    message = Messages.PROFILES_WRONG_SYNTAX.format('MissingSectionHeader')
    expected = f'{Messages.ERROR_PREFIX}{message[0].lower() + message[1:]}'

    assert result == expected

    path.unlink()
