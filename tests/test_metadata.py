"""Test suite for validating program metadata."""
from pathlib import Path
import re
import subprocess
import tomllib

from sacamantecas.about import PROGRAM_NAME, VERSION

PROJECT_ROOT = Path(subprocess.run(
    ['git', 'rev-parse', '--show-toplevel'],  # noqa: S607
    encoding='utf-8',
    capture_output=True,
    check=True,
).stdout.strip())

# This project uses a PyPA compliant versioning scheme, as defined in
# https://packaging.python.org/en/latest/specifications/version-specifiers/
#
# This scheme is partially compliant with 'Semantic Versioning 2.0', as
# defined in https://semver.org/, for released versions, since they will
# use a version string in the form of 'MAJOR.MINOR.PATCH'.
#
# But for development versions, the actual scheme diverges because the
# 'post' release segment uses a dot and not a hyphen as separator. The
# local version identifier, however, is actually compliant!
#
# The scheme does not make use of all defined segments. To wit, it uses
# ONLY the 'release' segment, but for development both a 'post' release
# segment and a local version identifier are added. The 'post' release
# segment includes the number of commits since the latest tagged commit,
# and the local local version identifier contains the abbreviated hash
# of the current commit, and an optional marker if the working copy is
# dirty, that is, current working copy has uncommitted changes. As such,
# the regex used to validate the version string has been adapted from
# the one provided in 'PyPA' documentation.
def test_version_matches_pypa_spec() -> None:
    """Test program version string against PyPA spec."""
    pypa_spec_compliant_version_regex = r"""^
        (?:0|[1-9][0-9]*+)(?:\.(?:0|[1-9][0-9]*+)){2}               # Release segment
        (?:\.post(?:0|[1-9][0-9]*+))?+                              # '.post' release segment
        (?:\+(?:[a-zA-Z.]++)?+(?:[0-9a-f]{7,40})?+(?:\.dirty)?+)?+  # Local version identifier
    $"""
    assert re.fullmatch(pypa_spec_compliant_version_regex, VERSION, re.ASCII|re.VERBOSE) is not None


def test_project_root() -> None:
    """Test the project root for the program is coherent."""
    assert Path(__file__).parent.parent == PROJECT_ROOT


def test_program_name_matches_metadata() -> None:
    """Test the hardcorded program name is what it should be."""
    live_program_name = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['name']
    assert live_program_name ==  PROGRAM_NAME
