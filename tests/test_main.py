#! /usr/bin/env python3
"""Test suite for main() function."""
from pathlib import Path

import pytest

from conftest import LogPaths
from sacamantecas import Constants, ExitCodes, main, Messages

PAD = ' ' * Constants.ERROR_PAYLOAD_INDENT
LOGGING_LEVELNAME_SEPARATOR = Constants.LOGGING_LEVELNAME_SEPARATOR

def test_logging_setup(log_paths: LogPaths, monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test for proper logging setup."""
    monkeypatch.setattr(Constants, 'LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'DEBUGFILE_PATH', log_paths.debug)

    assert not log_paths.log.is_file()
    assert not log_paths.debug.is_file()

    assert main() == ExitCodes.NO_ARGUMENTS

    assert log_paths.log.is_file()
    assert log_paths.debug.is_file()


def test_no_arguments(log_paths: LogPaths, monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test handling of missing command line arguments."""
    monkeypatch.setattr(Constants, 'LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'DEBUGFILE_PATH', log_paths.debug)

    assert main() == ExitCodes.NO_ARGUMENTS

    result = log_paths.log.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = '\n'.join((
        Messages.APP_BANNER,
        Messages.ERROR_HEADER,
        '\n'.join(f'{PAD}{line}' for line in Messages.NO_ARGUMENTS.split('\n')),
        Messages.PROCESS_DONE
    ))
    assert result == expected

    result = log_paths.debug.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = '\n'.join((
        f'DEBUG   {LOGGING_LEVELNAME_SEPARATOR}{Messages.DEBUGGING_INIT}',
        f'INFO    {LOGGING_LEVELNAME_SEPARATOR}{Messages.APP_BANNER}',
        f'DEBUG   {LOGGING_LEVELNAME_SEPARATOR}{Constants.USER_AGENT}',
        '\n'.join(f'ERROR   {LOGGING_LEVELNAME_SEPARATOR}{line}' for line in Messages.ERROR_HEADER.split('\n')),
        '\n'.join(f'ERROR   {LOGGING_LEVELNAME_SEPARATOR}{PAD}{line}' for line in Messages.NO_ARGUMENTS.split('\n')),
        '\n'.join(f'INFO    {LOGGING_LEVELNAME_SEPARATOR}{line}' for line in Messages.PROCESS_DONE.split('\n')),
        f'DEBUG   {LOGGING_LEVELNAME_SEPARATOR}{Messages.DEBUGGING_DONE}'
    ))
    assert result == expected


# pylint: disable-next=unused-variable
def test_missing_ini(
    log_paths: LogPaths,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test for missing main INI file."""
    monkeypatch.setattr(Constants, 'LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'DEBUGFILE_PATH', log_paths.debug)

    filename = str(tmp_path / 'non_existent.ini')

    monkeypatch.setattr(Constants, 'INIFILE_PATH', filename)
    assert main('') == ExitCodes.ERROR

    result = capsys.readouterr().err.splitlines()[3].strip()
    expected = f'No se encontró o no se pudo leer el fichero de perfiles «{filename}».'

    assert result == expected


# pylint: disable-next=unused-variable
def test_ini_syntax_error(
    log_paths: LogPaths,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test for syntax errors in INI file."""
    monkeypatch.setattr(Constants, 'LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'DEBUGFILE_PATH', log_paths.debug)

    filename = tmp_path / 'profiles_syntax_error.ini'
    filename.write_text('o')

    monkeypatch.setattr(Constants, 'INIFILE_PATH', filename)
    assert main('') == ExitCodes.ERROR

    result = capsys.readouterr().err.splitlines()[3].strip()
    expected = 'Error de sintaxis «MissingSectionHeader» leyendo el fichero de perfiles.'

    assert result == expected

    filename.unlink()
