#! /usr/bin/env python3
"""Test suite for `main()` function."""
import pytest

from sacamantecas import (
    is_console_attached,  # pyright: ignore[reportPrivateUsage]
    is_console_transient,  # pyright: ignore[reportPrivateUsage]
    is_running_as_script,  # pyright: ignore[reportPrivateUsage]
    wait_for_keypress,
)

from .helpers import CallableSpy


@pytest.mark.parametrize(('is_running_as_script', 'is_console_attached', 'is_console_transient', 'expected'),
    [
        (True, True, True, True),
        (False, True, True, False),
        (False, False, True, False),
        (False, False, False, False),
    ],
    ids=[
        'wait for keypress',
        'do not wait, script imported',
        'do not wait, no console attached',
        'do not wait, no transient console',
    ],
)
# pylint: disable=unused-variable
def test_wait_for_keypress(
    monkeypatch: pytest.MonkeyPatch, *,
    running_as_script: bool, console_attached: bool, console_transient: bool,
    expected: bool) -> None:
    """Test `wait_for_keypress()` waits only when it should."""
    getch_spy = CallableSpy(lambda: b'')

    monkeypatch.setitem(wait_for_keypress.__globals__, 'getch', getch_spy)
    monkeypatch.setitem(wait_for_keypress.__globals__, is_running_as_script.__name__, lambda: running_as_script)
    monkeypatch.setitem(wait_for_keypress.__globals__, is_console_attached.__name__, lambda: console_attached)
    monkeypatch.setitem(wait_for_keypress.__globals__, is_console_transient.__name__, lambda: console_transient)

    wait_for_keypress()

    assert getch_spy.called is expected
