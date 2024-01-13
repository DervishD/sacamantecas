#! /usr/bin/env python3
"""Test suite for main() function."""
import pytest

from sacamantecas import APP_NAME, EMPTY_STRING, wait_for_keypress, WFKStatuses


def test_imported():  # pylint: disable=unused-variable
    """Test wait_for_keypress() when the application script is imported."""
    assert wait_for_keypress() == WFKStatuses.IMPORTED


def test_no_console_attached(monkeypatch):  # pylint: disable=unused-variable
    """Test wait_for_keypress() when there is no console attached."""
    monkeypatch.setattr('sacamantecas.__name__', '__main__')
    monkeypatch.setattr('ctypes.windll.kernel32.GetConsoleMode', lambda *_: 0)
    assert wait_for_keypress() == WFKStatuses.NO_CONSOLE_ATTACHED


@pytest.mark.parametrize('title, frozen, result', [
    (EMPTY_STRING, False, WFKStatuses.NO_CONSOLE_TITLE),
    (APP_NAME, True, WFKStatuses.NO_TRANSIENT_FROZEN),
    (APP_NAME, False, WFKStatuses.NO_TRANSIENT_PYTHON),
    (APP_NAME.upper(), False, WFKStatuses.WAIT_FOR_KEYPRESS)
])
def test_wait_for_keypress(monkeypatch, title, frozen, result):  # pylint: disable=unused-variable
    """Test wait_for_keypress() general scenarios, with attached console."""
    monkeypatch.setattr('sacamantecas.__name__', '__main__')
    monkeypatch.setattr('ctypes.windll.kernel32.GetConsoleMode', lambda *_: 1)

    monkeypatch.setattr('sys.frozen', frozen, raising=False)
    monkeypatch.setattr('ctypes.windll.kernel32.GetConsoleMode', lambda *_: 1)
    monkeypatch.setattr(
        'ctypes.windll.kernel32.GetConsoleTitleW',
        lambda buffer, _: (setattr(buffer, 'value', title), len(title))[-1]
    )
    monkeypatch.setattr('sacamantecas.getch', lambda: 0)
    assert wait_for_keypress() == result
