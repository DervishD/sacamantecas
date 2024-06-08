#! /usr/bin/env python3
"""Test suite for decorators."""
import logging
from typing import NoReturn

import pytest

from conftest import LogPaths
from sacamantecas import Constants, keyboard_interrupt_handler, logger, loggerize, Messages

@loggerize
def loggerized_function() -> None:
    """Mock function to be decorated."""


@keyboard_interrupt_handler
def interrupted_function() -> NoReturn:
    """Mock function to be decorated."""
    raise KeyboardInterrupt


# pylint: disable-next=unused-variable
def test_loggerize(log_paths: LogPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the loggerize() decorator."""  # cSpell:ignore loggerize
    monkeypatch.setattr(Constants, 'LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'DEBUGFILE_PATH', log_paths.debug)

    assert not log_paths.log.is_file()
    assert not log_paths.debug.is_file()

    loggerized_function()

    logging.shutdown()

    assert log_paths.log.is_file()
    assert log_paths.debug.is_file()


# pylint: disable-next=unused-variable
def test_keyboard_interrupt_handler(log_paths: LogPaths, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the keyboard_interrupt_handler() decorator."""
    logger.config(log_paths.log, log_paths.debug)

    try:
        interrupted_function()
    except KeyboardInterrupt as exc:
        pytest.fail(f'Unexpected exception «{type(exc).__name__}{exc.args}»', pytrace=False)

    logging.shutdown()

    result = capsys.readouterr().err.rstrip()
    expected = f'{Messages.WARNING_HEADER}{Messages.KEYBOARD_INTERRUPT[0].lower()}{Messages.KEYBOARD_INTERRUPT[1:]}'

    assert result == expected
