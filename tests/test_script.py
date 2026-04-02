"""Test suite for running the package as a script."""
import runpy
import sys
from textwrap import dedent

import pytest

from sacamantecas import Constants, ExitCodes


def test_script_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test running the module instead of importing it."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    sys.argv = [Constants.__module__]
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(Constants.__module__)
    assert excinfo.value.code == ExitCodes.NO_ARGUMENTS

    expected_stdout_start = 'sacamantecas versión'
    expected_stdout_end = 'Proceso finalizado.'
    expected_stderr = dedent("""
        *** Error: no se han especificado fuentes de entrada para ser procesadas.

            Arrastre y suelte un fichero de entrada sobre el icono de la aplicación,
            o bien proporcione los nombres de las fuentes de entrada como argumentos.
    """)
    # Optionally capture stdout/stderr
    captured = capsys.readouterr()
    assert captured.out.startswith(expected_stdout_start)
    assert captured.out.strip().endswith(expected_stdout_end)
    assert captured.err == expected_stderr
