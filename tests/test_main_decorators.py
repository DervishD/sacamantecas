#! /usr/bin/env python3
"""Test suite for main decorators."""
import logging

import pytest

from sacamantecas import DEBUGFILE_PATH, keyboard_interrupt_handler, LOGFILE_PATH, loggerize, Messages, setup_logging


@loggerize
def loggerized_function():
    """Mock function to be decorated."""


@keyboard_interrupt_handler
def interrupted_function():
    """Mock function to be decorated."""
    raise KeyboardInterrupt


def test_loggerize(log_paths, monkeypatch):   # pylint: disable=unused-variable
    """Test the loggerize() decorator."""  # cSpell:ignore loggerize
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    assert not LOGFILE_PATH.is_file()
    assert not DEBUGFILE_PATH.is_file()

    loggerized_function()
    logging.shutdown()

    assert LOGFILE_PATH.is_file()
    assert DEBUGFILE_PATH.is_file()


def test_keyboard_interrupt_handler(log_paths, capsys):  # pylint: disable=unused-variable
    """Test the keyboard_interrupt_handler() decorator."""
    setup_logging(log_paths.log, log_paths.debug)

    try:
        interrupted_function()
    except KeyboardInterrupt as exc:
        pytest.fail(f'Unexpected exception «{type(exc).__name__}{exc.args}»', pytrace=False)

    logging.shutdown()

    result = capsys.readouterr().err.rstrip()
    expected = f'{Messages.WARNING_HEADER}{Messages.KEYBOARD_INTERRUPT}'

    assert result == expected
