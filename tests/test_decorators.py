#! /usr/bin/env python3
"""Test suite for decorators."""
import logging

import pytest

from sacamantecas import Constants, keyboard_interrupt_handler, loggerize, Messages, setup_logging


@loggerize
def loggerized_function():
    """Mock function to be decorated."""


@keyboard_interrupt_handler
def interrupted_function():
    """Mock function to be decorated."""
    raise KeyboardInterrupt


def test_loggerize(log_paths, monkeypatch):   # pylint: disable=unused-variable
    """Test the loggerize() decorator."""  # cSpell:ignore loggerize
    monkeypatch.setattr(Constants, 'LOGFILE_PATH', log_paths.log)
    monkeypatch.setattr(Constants, 'DEBUGFILE_PATH', log_paths.debug)

    assert not log_paths.log.is_file()
    assert not log_paths.debug.is_file()

    loggerized_function()
    logging.shutdown()

    assert log_paths.log.is_file()
    assert log_paths.debug.is_file()


def test_keyboard_interrupt_handler(log_paths, capsys):  # pylint: disable=unused-variable
    """Test the keyboard_interrupt_handler() decorator."""
    setup_logging(log_paths.log, log_paths.debug)

    try:
        interrupted_function()
    except KeyboardInterrupt as exc:
        pytest.fail(f'Unexpected exception «{type(exc).__name__}{exc.args}»', pytrace=False)

    logging.shutdown()

    result = capsys.readouterr().err.rstrip()
    expected = f'{Messages.WARNING_HEADER}{Messages.KEYBOARD_INTERRUPT[0].lower()}{Messages.KEYBOARD_INTERRUPT[1:]}'

    assert result == expected
