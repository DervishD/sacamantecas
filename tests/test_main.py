#! /usr/bin/env python3
"""Test suite for main() function."""
from sacamantecas import Config, ExitCodes, main, Messages


def test_logging_setup(log_paths, monkeypatch):  # pylint: disable=unused-variable
    """Test for proper logging setup."""
    monkeypatch.setattr('sacamantecas.Config.LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr('sacamantecas.Config.DEBUGFILE_PATH', log_paths.debug)

    assert not log_paths.log.is_file()
    assert not log_paths.debug.is_file()

    assert main() == ExitCodes.NO_ARGUMENTS

    assert log_paths.log.is_file()
    assert log_paths.debug.is_file()


def test_no_arguments(log_paths, monkeypatch):  # pylint: disable=unused-variable
    """Test handling of missing command line arguments."""
    monkeypatch.setattr('sacamantecas.Config.LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr('sacamantecas.Config.DEBUGFILE_PATH', log_paths.debug)

    assert main() == ExitCodes.NO_ARGUMENTS

    result = log_paths.log.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = '\n'.join((
        Messages.APP_BANNER,
        Messages.ERROR_HEADER.rstrip(),
        '\n'.join(f'{"    " if line else ""}{line}' for line in Messages.NO_ARGUMENTS.splitlines()),
        Messages.PROCESS_DONE
    ))
    assert result == expected

    result = log_paths.debug.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = '\n'.join((
        f'DEBUG   | {Messages.DEBUGGING_INIT}',
        f'INFO    | {Messages.APP_BANNER}',
        f'DEBUG   | {Config.USER_AGENT}',
        '\n'.join(f'ERROR   |{" " if line else ""}{line}' for line in Messages.ERROR_HEADER.splitlines()),
        '\n'.join(f'ERROR   |{"     " if line else ""}{line}' for line in Messages.NO_ARGUMENTS.splitlines()),
        '\n'.join(f'INFO    |{" " if line else ""}{line}' for line in Messages.PROCESS_DONE.splitlines()),
        f'DEBUG   | {Messages.DEBUGGING_DONE}'
    ))
    assert result == expected


def test_missing_ini(log_paths, tmp_path, monkeypatch, capsys):  # pylint: disable=unused-variable
    """Test for missing main INI file."""
    monkeypatch.setattr('sacamantecas.Config.LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr('sacamantecas.Config.DEBUGFILE_PATH', log_paths.debug)

    filename = str(tmp_path / 'non_existent.ini')

    monkeypatch.setattr('sacamantecas.Config.INIFILE_PATH', filename)
    assert main('') == ExitCodes.ERROR

    result = capsys.readouterr().err.splitlines()[2].strip()
    expected = f'No se encontró o no se pudo leer el fichero de perfiles «{filename}».'

    assert result == expected


def test_ini_syntax_error(log_paths, tmp_path, monkeypatch, capsys):  # pylint: disable=unused-variable
    """Test for syntax errors in INI file."""
    monkeypatch.setattr('sacamantecas.Config.LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr('sacamantecas.Config.DEBUGFILE_PATH', log_paths.debug)

    filename = tmp_path / 'profiles_syntax_error.ini'
    filename.write_text('o')

    monkeypatch.setattr('sacamantecas.Config.INIFILE_PATH', filename)
    assert main('') == ExitCodes.ERROR

    result = capsys.readouterr().err.splitlines()[2].strip()
    expected = 'Error de sintaxis «MissingSectionHeader» leyendo el fichero de perfiles.'

    assert result == expected

    filename.unlink()
