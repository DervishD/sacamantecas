#! /usr/bin/env python3
"""Test suite for `main()` function."""
from importlib.metadata import metadata, version
import logging
from typing import NoReturn, TYPE_CHECKING

from legion import format_message
import pytest

from sacamantecas import (
    BaseParser,
    Constants,
    ExitCodes,
    keyboard_interrupt_handler,
    logger,
    main,
    SkimmingError,
    SourceError,
)
from tests.test_logging import get_clean_logfile_contents

if TYPE_CHECKING:
    from pathlib import Path

    from helpers import LogPaths


def test_no_arguments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test handling of missing command line arguments."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    assert main() == ExitCodes.NO_ARGUMENTS

    captured = capsys.readouterr()

    self_version = version(Constants.PROGRAM_NAME)
    repository = next(
        (url for url in metadata(Constants.PROGRAM_NAME).get_all('Project-URL', []) if url.startswith('source')),
        '',
    ).split(', ', maxsplit=1)[1]

    assert captured.out == f'{Constants.PROGRAM_NAME} versión {self_version} ({repository})\n\nProceso finalizado.\n'

    heading = '\n*** Error: no se han especificado fuentes de entrada para ser procesadas.'
    message = (
        '\n'
        'Arrastre y suelte un fichero de entrada sobre el icono de la aplicación,\n'
        'o bien proporcione los nombres de las fuentes de entrada como argumentos.'
    )
    expected = f'{format_message(heading, message, indentation='    ')}\n'
    assert captured.err == expected


@keyboard_interrupt_handler
def interrupted_function() -> NoReturn:
    """Mock function to be decorated."""
    raise KeyboardInterrupt


def test_keyboard_interrupt_handler(capsys: pytest.CaptureFixture[str]) -> None:
    """Test the `keyboard_interrupt_handler()` decorator."""
    logger.config(main_log_output=None, full_log_output=None)

    interrupted_function()

    logging.shutdown()

    result = capsys.readouterr().err.rstrip()
    message = 'el usuario interrumpió la operación de la aplicación.'
    expected = f'* Aviso: {message}'

    assert result == expected


@pytest.mark.parametrize(('exception', 'mocked_entry_point_name'), [
    pytest.param(SourceError, 'bootstrap', id='test_main_source_error_handling'),
    pytest.param(SkimmingError, 'saca_las_mantecas', id='test_main_skimming_error_handling'),
])
def test_main_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    exception: type[Exception],
    mocked_entry_point_name: str,
) -> None:
    """Test main loop exception handling in `main()`."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    inifile_path = tmp_path / 'profiles.ini'
    monkeypatch.setattr(Constants, 'INIFILE_PATH', inifile_path)
    inifile_path.write_text('[mock_section]\nurl = .*\nmock_key = mock_value\n')

    error_message = 'mock_error_message'
    def mock_entry_point(*_: object) -> None:
        raise exception(error_message)
    monkeypatch.setitem(main.__globals__, mocked_entry_point_name, mock_entry_point)

    exitcode = main('https://localhost')
    captured = capsys.readouterr()

    assert exitcode == ExitCodes.WARNING
    assert captured.err.strip() == f'* Aviso: {error_message}'


class MockParser(BaseParser):
    """Mock parser."""  # noqa: D204
    PARAMETERS = BaseParser.PARAMETERS | {'mock_key'}
def test_main_full_invocation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, log_paths: LogPaths) -> None:
    """Test full invocation of `main()` function."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', log_paths.main)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', log_paths.full)

    inifile_path = tmp_path / 'profiles.ini'
    monkeypatch.setattr(Constants, 'INIFILE_PATH', inifile_path)
    inifile_path.write_text('[mock_section]\nurl = .*\nmock_key = mock_value\n')

    def mock_saca_las_mantecas(_u: str, _p: BaseParser) -> dict[str, str]:
        return {'mock_key' : 'mock_value'}
    monkeypatch.setitem(main.__globals__, 'saca_las_mantecas', mock_saca_las_mantecas)

    exitcode = main('https://localhost')
    assert exitcode == ExitCodes.SUCCESS

    main_log_contents = get_clean_logfile_contents(log_paths.main)
    full_log_contents = get_clean_logfile_contents(log_paths.full)

    assert log_paths.main.is_file()
    assert log_paths.full.is_file()
    assert 'Registro de depuración iniciado.' in full_log_contents[0]
    assert 'sacamantecas versión' in full_log_contents[1]
    assert 'sacamantecas versión' in main_log_contents[0]
    assert 'Proceso finalizado.' in main_log_contents[-1]
    assert 'Proceso finalizado.' in full_log_contents[-2]
    assert 'Registro de depuración finalizado.' in full_log_contents[-1]
