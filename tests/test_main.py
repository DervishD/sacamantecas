#! /usr/bin/env python3
"""Test suite for `main()` function."""
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
    Messages,
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

    assert captured.out == f'{Messages.APP_BANNER}\n{Messages.PROCESS_DONE}\n'

    heading = f'{Messages.ERROR_PREFIX}{Messages.NO_ARGUMENTS_HEADING[0].lower()}{Messages.NO_ARGUMENTS_HEADING[1:]}'
    message = Messages.NO_ARGUMENTS_INSTRUCTIONS
    expected = f'{format_message(heading, message, indentation=Constants.ERROR_PAYLOAD_INDENTATION)}\n'
    assert captured.err == expected


@keyboard_interrupt_handler
def interrupted_function() -> NoReturn:
    """Mock function to be decorated."""
    raise KeyboardInterrupt


def test_keyboard_interrupt_handler(capsys: pytest.CaptureFixture[str]) -> None:  # pylint: disable=unused-variable
    """Test the `keyboard_interrupt_handler()` decorator."""
    logger.config(main_log_output=None, full_log_output=None)

    try:
        interrupted_function()
    except KeyboardInterrupt as exc:
        pytest.fail(f'Unexpected exception «{type(exc).__name__}{exc.args}»', pytrace=False)

    logging.shutdown()

    result = capsys.readouterr().err.rstrip()
    message = Messages.KEYBOARD_INTERRUPT[0].lower() + Messages.KEYBOARD_INTERRUPT[1:]
    expected = f'{Messages.WARNING_PREFIX}{message}'

    assert result == expected
