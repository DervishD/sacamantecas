#! /usr/bin/env python3
"""Test suite for the logging system."""
from importlib.metadata import metadata, requires, version
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

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tests.helpers import LogPaths


def get_clean_logfile_contents (logfile: Path) -> list[str]:  # pylint: disable=unused-variable
    """Get clean *logfile**. For now, just remove timestamps."""
    return [' '.join(line.split(' ')[1:]) for line in logfile.read_text(encoding='utf-8').splitlines()]


def test_logging_setup(log_paths: LogPaths, monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test that the logging system is properly set-up."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', log_paths.main)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', log_paths.full)

    assert not log_paths.main.is_file()
    assert not log_paths.full.is_file()

    def f(message: str) -> ExitCodes:
        logger.error(message)
        return ExitCodes.SUCCESS

    message = 'Test message'
    loggerize(f)(message)

    assert log_paths.main.is_file()
    assert log_paths.full.is_file()

    self_version = version(Constants.PROGRAM_NAME)
    repository = next(
        (url for url in metadata(Constants.PROGRAM_NAME).get_all('Project-URL', []) if url.startswith('source')),
        '',
    ).split(', ', maxsplit=1)[1]
    platform_string = f'(Windows {platform.version()};{platform.architecture()[0]};{platform.machine()})'
    required_packages = [f'{pkg.replace('==', ' v')}' for pkg in requires(Constants.PROGRAM_NAME) or []]
    required_packages = [f'        DEBUG    | loggerize_wrapper() Usando paquete {pkg}' for pkg in required_packages]

    expected_full_log = dedent(f"""
        DEBUG    | loggerize_wrapper() Registro de depuración iniciado.
        INFO     | loggerize_wrapper() sacamantecas versión {self_version} ({repository})
        {'\n'.join(required_packages).lstrip()}
        DEBUG    | loggerize_wrapper() sacamantecas/{self_version} +{repository} {platform_string}
        ERROR    | f() {message}
        INFO     | loggerize_wrapper()
        INFO     | loggerize_wrapper() Proceso finalizado.
        DEBUG    | loggerize_wrapper() Registro de depuración finalizado.
    """).lstrip().splitlines()

    expected_main_log = dedent(f"""
        sacamantecas versión {self_version} ({repository})
        {message}

        Proceso finalizado.
    """).lstrip().splitlines()

    assert get_clean_logfile_contents(log_paths.full) == expected_full_log
    assert get_clean_logfile_contents(log_paths.main) == expected_main_log


def test_logging_helpers(capsys: pytest.CaptureFixture[str]) -> None:  # pylint: disable=unused-variable
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
