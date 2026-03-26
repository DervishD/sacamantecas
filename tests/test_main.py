#! /usr/bin/env python3
"""Test suite for `main()` function."""
from importlib.metadata import metadata, version
import logging
from typing import NoReturn

from legion import format_message
import pytest

from sacamantecas import (
    Constants,
    ExitCodes,
    keyboard_interrupt_handler,
    logger,
    main,
)


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


# pylint: disable-next=unused-variable
def test_keyboard_interrupt_handler(capsys: pytest.CaptureFixture[str]) -> None:
    """Test the `keyboard_interrupt_handler()` decorator."""
    logger.config(main_log_output=None, full_log_output=None)

    try:
        interrupted_function()
    except KeyboardInterrupt as exc:
        pytest.fail(f'Unexpected exception «{type(exc).__name__}{exc.args}»', pytrace=False)

    logging.shutdown()

    result = capsys.readouterr().err.rstrip()
    message = 'el usuario interrumpió la operación de la aplicación.'
    expected = f'* Aviso: {message}'

    assert result == expected
