"""Test platform-specific behavior."""
import importlib
import sys

import pytest

SACAMANTECAS = 'sacamantecas'

@pytest.fixture(autouse=True)
def evict_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the module is evicted before each test."""
    monkeypatch.delitem(sys.modules, SACAMANTECAS, raising=False)

def test_loads_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the module loads correctly on win32 platform."""
    monkeypatch.setattr('sys.platform', 'win32')

    module = importlib.import_module(SACAMANTECAS   )
    assert module is not None

def test_rejects_non_windows(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test that SystemExit is raised on non-win32 platforms."""
    monkeypatch.setattr('sys.platform', 'linux')

    with pytest.raises(SystemExit) as excinfo:
        importlib.import_module(SACAMANTECAS)

    assert excinfo.value.code is None
    assert capsys.readouterr().out == '\nThis program is compatible only with the Win32 platform.\n'
