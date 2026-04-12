"""Test suite for the logging system."""
import logging
import platform
from textwrap import dedent
from typing import TYPE_CHECKING

from legion import format_message

from sacamantecas import (
    Constants,
    error,
    ExitCodes,
    logger,
    loggerize,
    warning,
)
from sacamantecas.about import DEPENDENCIES, PROGRAM_NAME, REPOSITORY, VERSION

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


# pylint: disable-next=unused-variable
def test_logging_setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that the logging system is properly set-up."""
    def remove_timestamps (logfile: Path) -> list[str]:
        return [' '.join(line.split(' ')[1:]) for line in logfile.read_text(encoding='utf-8').splitlines()]

    main_log_path = tmp_path / Constants.MAIN_OUTPUT_PATH.name
    full_log_path = tmp_path / Constants.FULL_OUTPUT_PATH.name
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', main_log_path)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', full_log_path)

    assert not main_log_path.is_file()
    assert not full_log_path.is_file()

    def f(message: str) -> ExitCodes:
        logger.error(message)
        return ExitCodes.SUCCESS

    message = 'Test message'
    loggerize(f)(message)

    assert main_log_path.is_file()
    assert full_log_path.is_file()

    platform_string = f'(Windows {platform.version()};{platform.architecture()[0]};{platform.machine()})'
    required_packages = [pkg.replace('==', ' v') for pkg in DEPENDENCIES]
    required_packages = [f'        DEBUG    | loggerize_wrapper() Usando paquete {pkg}' for pkg in required_packages]

    expected_full_log = dedent(f"""
        DEBUG    | loggerize_wrapper() Registro de depuración iniciado.
        INFO     | loggerize_wrapper() {PROGRAM_NAME} versión {VERSION} ({REPOSITORY})
        {'\n'.join(required_packages).lstrip()}
        DEBUG    | loggerize_wrapper() {PROGRAM_NAME}/{VERSION} +{REPOSITORY} {platform_string}
        ERROR    | f() {message}
        INFO     | loggerize_wrapper()
        INFO     | loggerize_wrapper() Proceso finalizado.
        DEBUG    | loggerize_wrapper() Registro de depuración finalizado.
    """).lstrip().splitlines()

    expected_main_log = dedent(f"""
        {PROGRAM_NAME} versión {VERSION} ({REPOSITORY})
        {message}

        Proceso finalizado.
    """).lstrip().splitlines()

    assert remove_timestamps(full_log_path) == expected_full_log
    assert remove_timestamps(main_log_path) == expected_main_log


# pylint: disable-next=unused-variable
def test_logging_helpers(capsys: pytest.CaptureFixture[str]) -> None:
    """Test logging helper functions."""
    message = 'Test message 1\n\nTest message 2\n\n'
    heading = 'Heading'

    logger.config()

    warning(message)
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == f'* Aviso: {message[0].lower()}{message[1:]}\n'

    error(heading, message)
    captured = capsys.readouterr()
    assert not captured.out
    assert captured.err == format_message(
        f'\n*** Error: {heading[0].lower()}{heading[1:]}',
        f'{message}\n',
        indentation='    ')

    logging.shutdown()
