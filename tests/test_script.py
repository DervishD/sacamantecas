"""Test suite for running the package as a script."""
import runpy
import sys

import pytest

from sacamantecas import ExitCodes, lowercase_first_letter, Messages, Paths

PACKAGE_NAME = Paths.__module__.partition('.')[0]

# pylint: disable-next=unused-variable
def test_script_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test running the module instead of importing it."""
    monkeypatch.setattr(Paths, 'MAIN_LOG', None)
    monkeypatch.setattr(Paths, 'FULL_LOG', None)
    monkeypatch.setattr(sys, 'argv', [PACKAGE_NAME])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(PACKAGE_NAME)
    assert excinfo.value.code == ExitCodes.NO_ARGUMENTS

    captured = capsys.readouterr()
    assert captured.out.strip().endswith(Messages.PROCESS_DONE)
    assert ' '.join(lowercase_first_letter(Messages.ERROR_NO_ARGUMENTS).split()) in ' '.join(captured.err.split())
