"""Test platform-specific behavior."""
import importlib
import sys

import pytest

from sacamantecas.about import PROGRAM_NAME as MODULE_NAME


# pylint: disable-next=unused-variable
def test_loads_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the module loads correctly on win32 platform."""
    monkeypatch.delitem(sys.modules, MODULE_NAME, raising=False)
    monkeypatch.setattr('sys.platform', 'win32')

    module = importlib.import_module(MODULE_NAME)

    assert callable(module.main)


# pylint: disable-next=unused-variable
def test_rejects_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that SystemExit is raised on non-win32 platforms."""
    error_message = '\nThis program is compatible only with the Win32 platform.'
    monkeypatch.delitem(sys.modules, MODULE_NAME, raising=False)
    monkeypatch.setattr('sys.platform', 'example_platform')

    with pytest.raises(SystemExit) as excinfo:
        importlib.import_module(MODULE_NAME)

    assert excinfo.value.code == error_message
