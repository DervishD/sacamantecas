"""Test suite for `main()` function."""
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
from sacamantecas.about import BUILD, PROGRAM_NAME, REPOSITORY

if TYPE_CHECKING:
    from pathlib import Path

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

    assert captured.out == f'{PROGRAM_NAME} versión {BUILD} ({REPOSITORY})\n\nProceso finalizado.\n'

    heading = '\n*** Error: no se han especificado fuentes de entrada para ser procesadas.'
    message = (
        '\n'
        'Arrastre y suelte un fichero de entrada sobre el icono de la aplicación,\n'
        'o bien proporcione los nombres de las fuentes de entrada como argumentos.'
    )
    expected = f'{format_message(heading, message, indentation='    ')}\n'
    assert captured.err == expected


# pylint: disable-next=unused-variable
def test_keyboard_interrupt_handler(capsys: pytest.CaptureFixture[str]) -> None:
    """Test the `keyboard_interrupt_handler()` decorator."""
    @keyboard_interrupt_handler
    def interrupted_function() -> NoReturn:
        """Mock function to be decorated."""
        raise KeyboardInterrupt

    logger.config(main_log_output=None, full_log_output=None)

    interrupted_function()

    logging.shutdown()  # pylint: disable=unreachable

    result = capsys.readouterr().err.rstrip()
    message = 'el usuario interrumpió la operación de la aplicación.'
    expected = f'* Aviso: {message}'

    assert result == expected


# pylint: disable-next=unused-variable
class ATestParser(BaseParser):
    """Test parser, needed for the test units below."""  # noqa: D204
    PARAMETERS = BaseParser.PARAMETERS | {'example_key'}


@pytest.mark.parametrize(('exception', 'entry_point_name'), [
    pytest.param(SourceError, 'bootstrap', id='test_main_source_error_handling'),
    pytest.param(SkimmingError, 'saca_las_mantecas', id='test_main_skimming_error_handling'),
])
# pylint: disable-next=unused-variable
def test_main_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    exception: type[Exception],
    entry_point_name: str,
) -> None:
    """Test main loop exception handling in `main()`."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    inifile_path = tmp_path / 'profiles.ini'
    monkeypatch.setattr(Constants, 'INIFILE_PATH', inifile_path)
    inifile_path.write_text('[example_section]\nurl = .*\nexample_key = example_value\n')

    error_message = 'example_error_message'
    def mock_entry_point(*_: object) -> None:
        raise exception(error_message)
    monkeypatch.setitem(main.__globals__, entry_point_name, mock_entry_point)

    def patched_generate_sinkfile_path(_: Path) -> Path:
        return sinkfile_path
    sinkfile_path = tmp_path / 'testsink_out.txt'
    monkeypatch.setitem(main.__globals__, 'generate_sinkfile_path', patched_generate_sinkfile_path)

    exitcode = main('https://localhost')
    captured = capsys.readouterr()

    assert exitcode == ExitCodes.WARNING
    assert captured.err.strip() == f'* Aviso: {error_message}'


# pylint: disable-next=unused-variable
def test_main_full_invocation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test full invocation of `main()` function."""
    main_log_path = tmp_path / Constants.MAIN_OUTPUT_PATH.name
    full_log_path = tmp_path / Constants.FULL_OUTPUT_PATH.name
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', main_log_path)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', full_log_path)

    inifile_path = tmp_path / 'profiles.ini'
    monkeypatch.setattr(Constants, 'INIFILE_PATH', inifile_path)
    inifile_path.write_text('[example_section]\nurl = .*\nexample_key = example_value\n')

    def mock_saca_las_mantecas(_u: str, _p: BaseParser) -> dict[str, str]:
        return {'example_key' : 'example_value'}
    monkeypatch.setitem(main.__globals__, 'saca_las_mantecas', mock_saca_las_mantecas)

    def patched_generate_sinkfile_path(_: Path) -> Path:
        return sinkfile_path
    sinkfile_path = tmp_path / 'testsink_out.txt'
    monkeypatch.setitem(main.__globals__, 'generate_sinkfile_path', patched_generate_sinkfile_path)

    exitcode = main('https://localhost')
    assert exitcode == ExitCodes.SUCCESS

    main_log_contents = main_log_path.read_text().splitlines()
    full_log_contents = full_log_path.read_text().splitlines()

    assert 'Registro de depuración iniciado.' in full_log_contents[0]
    assert 'sacamantecas versión' in full_log_contents[1]
    assert 'sacamantecas versión' in main_log_contents[0]
    assert 'Proceso finalizado.' in main_log_contents[-1]
    assert 'Proceso finalizado.' in full_log_contents[-2]
    assert 'Registro de depuración finalizado.' in full_log_contents[-1]
