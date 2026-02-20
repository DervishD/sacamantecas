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


@pytest.mark.parametrize(('running_as_script', 'console_attached', 'console_transient', 'expected'), [
    (False, None, None, False),
    (True, False, None, False),
    (True, True, False, False),
    (True, True, True, True),
], ids=[
    'test_no_wait_for_keypress_script_imported',
    'test_no_wait_for_keypress_no_console_attached',
    'test_no_wait_for_keypress_no_transient_console',
    'test_do_wait_for_keypress',
])
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
