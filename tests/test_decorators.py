#! /usr/bin/env python3
"""Test suite for decorators."""
import logging
from typing import NoReturn

import pytest

from sacamantecas import keyboard_interrupt_handler, logger, Messages


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
