#! /usr/bin/env python3
"""Test suite for main()."""
import sacamantecas as sm

def test_logging_setup(log_paths, monkeypatch):  # pylint: disable=unused-variable
    """Test for proper logging setup."""
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    assert sm.main([]) == sm.EXITCODE_FAILURE
    assert sm.LOGFILE_PATH.is_file()
    assert sm.DEBUGFILE_PATH.is_file()


def test_no_arguments(log_paths, monkeypatch):  # pylint: disable=unused-variable
    """Test handling of missing command line arguments."""
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    assert sm.main([]) == sm.EXITCODE_FAILURE

    result = sm.LOGFILE_PATH.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = f'{sm.PROGRAM_BANNER}\n{sm.ERROR_HEADER}{sm.MESSAGES.NO_PROGRAM_ARGUMENTS}\n{sm.MESSAGES.EOP}'
    assert result == expected

    result = sm.DEBUGFILE_PATH.read_text(encoding='utf-8').splitlines()
    result = '\n'.join([' '.join(line.split(' ')[1:]) for line in result])
    expected = '\n'.join((
        f'[DEBUG] {sm.MESSAGES.DEBUGGING_INIT}',
        f'[DEBUG] {sm.MESSAGES.USER_AGENT}',
        f'[INFO] {sm.PROGRAM_BANNER}',
        '\n'.join(f'[ERROR]{" " if line else ""}{line}' for line in sm.ERROR_HEADER.splitlines()),
        '\n'.join(f'[ERROR]{" " if line else ""}{line}' for line in sm.MESSAGES.NO_PROGRAM_ARGUMENTS.splitlines()),
        '\n'.join(f'[INFO]{" " if line else ""}{line}' for line in sm.MESSAGES.EOP.splitlines()),
        f'[DEBUG] {sm.MESSAGES.DEBUGGING_DONE}'
    ))
    assert result == expected


def test_missing_ini(log_paths, tmp_path, monkeypatch, capsys):  # pylint: disable=unused-variable
    """Test for missing main INI file."""
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    filename = str(tmp_path / 'non_existent_profiles_file.ini')

    monkeypatch.setattr("sacamantecas.INIFILE_PATH", filename)
    assert sm.main(['']) == sm.EXITCODE_FAILURE

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
    assert sm.main(['']) == sm.EXITCODE_FAILURE

    result = capsys.readouterr().err.splitlines()[2]
    expected = 'Error de sintaxis «MissingSectionHeader» leyendo el fichero de perfiles.'

    assert result == expected

    filename.unlink()
