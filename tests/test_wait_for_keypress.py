#! /usr/bin/env python3
"""Test suite for main() function."""
from typing import Any
import pytest

from sacamantecas import Constants, wait_for_keypress, WFKStatuses


def test_imported() -> None:  # pylint: disable=unused-variable
    """Test wait_for_keypress() when the application script is imported."""
    assert wait_for_keypress() == WFKStatuses.IMPORTED


def test_no_console_attached(monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test wait_for_keypress() when there is no console attached."""
    def patched_getconsolemode(*_: Any) -> int:
        return 0

    monkeypatch.setattr('sacamantecas.__name__', '__main__')
    monkeypatch.setattr('ctypes.windll.kernel32.GetConsoleMode', patched_getconsolemode)

    assert wait_for_keypress() == WFKStatuses.NO_CONSOLE_ATTACHED


@pytest.mark.parametrize(('title', 'frozen', 'result'), [
    ('', False, WFKStatuses.NO_CONSOLE_TITLE),
    (Constants.APP_NAME, True, WFKStatuses.NO_TRANSIENT_FROZEN),
    (Constants.APP_NAME, False, WFKStatuses.NO_TRANSIENT_PYTHON),
    (Constants.APP_NAME.upper(), False, WFKStatuses.WAIT_FOR_KEYPRESS),
])
# pylint: disable-next=unused-variable
def test_wait_for_keypress(monkeypatch: pytest.MonkeyPatch, title: str, frozen: bool, result: WFKStatuses) -> None:
    """Test wait_for_keypress() general scenarios, with attached console."""
    def patched_getconsolemode(*_: Any) -> int:
        return 1

    def patched_getconsoletitle(buffer: object, *_: Any) -> int:
        setattr(buffer, 'value', title)
        return len(title)

    def patched_getch() -> int:
        return 0

    monkeypatch.setattr('sacamantecas.__name__', '__main__')
    monkeypatch.setattr('ctypes.windll.kernel32.GetConsoleMode', patched_getconsolemode)
    monkeypatch.setattr('sys.frozen', frozen, raising=False)
    monkeypatch.setattr('ctypes.windll.kernel32.GetConsoleMode', patched_getconsolemode)
    monkeypatch.setattr('ctypes.windll.kernel32.GetConsoleTitleW', patched_getconsoletitle)
    monkeypatch.setattr('sacamantecas.getch', patched_getch)

    assert wait_for_keypress() == result
