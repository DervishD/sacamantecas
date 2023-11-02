#! /usr/bin/env python3
"""Test suite for main()."""
from sacamantecas import DEBUGFILE_PATH, ExitCodes, LOGFILE_PATH, main, Messages


def test_logging_setup(log_paths, monkeypatch):  # pylint: disable=unused-variable
    """Test for proper logging setup."""
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    assert main() == ExitCodes.NO_ARGUMENTS
    assert LOGFILE_PATH.is_file()
    assert DEBUGFILE_PATH.is_file()


def test_no_arguments(log_paths, monkeypatch):  # pylint: disable=unused-variable
    """Test handling of missing command line arguments."""
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    assert main() == ExitCodes.NO_ARGUMENTS

    result = LOGFILE_PATH.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = f'{Messages.APP_INIT}\n{Messages.ERROR_HEADER}{Messages.NO_ARGUMENTS}\n{Messages.APP_DONE}'
    assert result == expected

    result = DEBUGFILE_PATH.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = '\n'.join((
        f'[DEBUG] {Messages.DEBUGGING_INIT}',
        f'[INFO] {Messages.APP_INIT}',
        f'[DEBUG] {Messages.USER_AGENT}',
        '\n'.join(f'[ERROR]{" " if line else ""}{line}' for line in Messages.ERROR_HEADER.splitlines()),
        '\n'.join(f'[ERROR]{" " if line else ""}{line}' for line in Messages.NO_ARGUMENTS.splitlines()),
        '\n'.join(f'[INFO]{" " if line else ""}{line}' for line in Messages.APP_DONE.splitlines()),
        f'[DEBUG] {Messages.DEBUGGING_DONE}'
    ))
    assert result == expected


def test_missing_ini(log_paths, tmp_path, monkeypatch, capsys):  # pylint: disable=unused-variable
    """Test for missing main INI file."""
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    filename = str(tmp_path / 'non_existent.ini')

    monkeypatch.setattr("sacamantecas.INIFILE_PATH", filename)
    assert main(['']) == ExitCodes.ERROR

    result = capsys.readouterr().err.splitlines()[2]
    expected = f'No se encontró o no se pudo leer el fichero de perfiles «{filename}».'

    assert result == expected


def test_ini_syntax_error(log_paths, tmp_path, monkeypatch, capsys):  # pylint: disable=unused-variable
    """Test for syntax errors in INI file."""
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    filename = tmp_path / 'profiles_syntax_error.ini'
    filename.write_text('o')

    monkeypatch.setattr("sacamantecas.INIFILE_PATH", filename)
    assert main(['']) == ExitCodes.ERROR

    result = capsys.readouterr().err.splitlines()[2]
    expected = 'Error de sintaxis «MissingSectionHeader» leyendo el fichero de perfiles.'

    assert result == expected

    filename.unlink()
