#! /usr/bin/env python3
"""Test suite for main decorators."""
import logging
import pytest
import sacamantecas as sm


@sm.loggerize
def loggerized_function():
    """Mock function to be decorated."""


@sm.keyboard_interrupt_handler
def interrupted_function():
    """Mock function to be decorated."""
    raise KeyboardInterrupt


def test_loggerize(log_paths, monkeypatch):   # pylint: disable=unused-variable
    """Test the loggerize() decorator."""  # cSpell:ignore loggerize
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", log_paths.log)
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", log_paths.debug)

    assert not sm.LOGFILE_PATH.is_file()
    assert not sm.DEBUGFILE_PATH.is_file()

    loggerized_function()
    logging.shutdown()

    assert sm.LOGFILE_PATH.is_file()
    assert sm.DEBUGFILE_PATH.is_file()


def test_keyboard_interrupt_handler(log_paths, capsys):  # pylint: disable=unused-variable
    """Test the keyboard_interrupt_handler() decorator."""
    sm.setup_logging(log_paths.log, log_paths.debug)

    try:
        interrupted_function()
    except KeyboardInterrupt as exc:
        pytest.fail(f'Unexpected exception «{type(exc).__name__}{exc.args}»', pytrace=False)

    logging.shutdown()

    result = capsys.readouterr().err.rstrip()
    expected = f'{sm.WARNING_HEADER}{sm.MESSAGES.KEYBOARD_INTERRUPTION}'

    assert result == expected
