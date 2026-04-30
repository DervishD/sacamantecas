"""Test suite for validating program metadata."""
from pathlib import Path
import re

from legion import get_project_metadata

from sacamantecas.about import PROGRAM_NAME, VERSION

PROJECT_METADATA = get_project_metadata()


# This project uses a PyPA compliant versioning scheme, as defined in
# https://packaging.python.org/en/latest/specifications/version-specifiers/#version-scheme
#
# This scheme is partially compliant with *Semantic Versioning 2.0*, as
# defined in https://semver.org/, at least for final releases, since it
# uses a version string in the form of `MAJOR.MINOR.PATCH`.
#
# For other kind of releases, the scheme diverges because of the syntax
# of the different segments which can be present in the public version
# identifier. The local version identifier, however, is fully compliant!
#
# For final releases, only the *release* segment is used, with exactly
# three components, corresponding to `MAJOR.MINOR.PATCH`.
#
# For development releases, instead of using the *developmental release*
# segment defined by PyPA, a *post release* segment is used, followed by
# a local version specifier. The reason for avoiding the *developmental
# release* segment is that these releases are considered preliminary for
# the next final release, they are ordered **before** that release, but
# the *release* segment is that of the *next* final release. But in here
# the term *development* is used differently, for releases **after** the
# *last* final release that are ordered **after** the last final release
# without changing the *release* segment at all.
#
# The *post-release* segment includes the number of commits made since
# the latest tagged commit, and the local version specifier contains the
# active branch name and the last commit abbreviated hash, separated by
# a period, and a final `.dirty` optional marker if the working copy is
# dirty, that is, it has uncommitted changes.
#
# So, the regex used to validate the version string is a bit different
# than the one provided in the PyPA documentation.

# pylint: disable-next=unused-variable
def test_version_matches_pypa_spec() -> None:
    """Test program version string against PyPA spec."""
    pypa_spec_compliant_version_regex = r"""^
        (?P<release>(?:0|[1-9][0-9]*+)(?:\.(?:0|[1-9][0-9]*+)){2})  # Release segment (mandatory segment).
        (?:                                                         # Development release segment (optional segment).
            (?P<distance>\.post(?:0|[1-9][0-9]*+))                  #   Post release with distance.
            \+                                                      #   Local version specifier.
                (?P<branch>[a-z0-9]++)                              #     Branch name.
                \.(?P<hash>[0-9a-f]{7,40})                          #     Commit hash.
                (?P<dirty>\.dirty)?+                                #     Dirty marker (optional within segment).
        )?+
    $"""
    assert re.fullmatch(pypa_spec_compliant_version_regex, VERSION, re.ASCII|re.VERBOSE) is not None


# pylint: disable-next=unused-variable
def test_project_root() -> None:
    """Test the project root for the program is coherent."""
    assert PROJECT_METADATA is not None
    assert Path(__file__).parent.parent == PROJECT_METADATA['project_root']


# pylint: disable-next=unused-variable
def test_program_name_matches_metadata() -> None:
    """Test the hardcorded program name is what it should be."""
    assert PROJECT_METADATA is not None
    assert PROJECT_METADATA['project']['name'] == PROGRAM_NAME
