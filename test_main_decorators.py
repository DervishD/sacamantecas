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


def test_loggerize(tmp_path, monkeypatch):   # pylint: disable=unused-variable
    """Test the loggerize() decorator."""  # cSpell:ignore loggerize
    monkeypatch.setattr("sacamantecas.LOGFILE_PATH", tmp_path / 'log_filename.txt')
    monkeypatch.setattr("sacamantecas.DEBUGFILE_PATH", tmp_path / 'debug_filename.txt')

    assert not sm.LOGFILE_PATH.is_file()
    assert not sm.DEBUGFILE_PATH.is_file()

    loggerized_function()
    logging.shutdown()

    assert sm.LOGFILE_PATH.is_file()
    assert sm.DEBUGFILE_PATH.is_file()

    sm.LOGFILE_PATH.unlink()
    sm.DEBUGFILE_PATH.unlink()


def test_keyboard_interrupt_handler(tmp_path, capsys):  # pylint: disable=unused-variable
    """Test the keyboard_interrupt_handler() decorator."""
    log_filename = tmp_path / 'log_filename.txt'
    debug_filename = tmp_path / 'debug_filename.txt'
    sm.setup_logging(log_filename, debug_filename)

    try:
        interrupted_function()
    except KeyboardInterrupt as exc:
        pytest.fail(f'Unexpected exception «{type(exc).__name__}{exc.args}»', pytrace=False)

    logging.shutdown()
    log_filename.unlink()
    debug_filename.unlink()

    assert capsys.readouterr().err.rstrip() == f'{sm.WARNING_HEADER}{sm.MESSAGES.KEYBOARD_INTERRUPTION}'
