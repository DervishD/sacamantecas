#! /usr/bin/env python3
"""Test suite for validating application metadata."""
from importlib.metadata import metadata, version
import re

from sacamantecas import Constants


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
    """Test application version string."""
    pypa_spec_compliant_version_regex = r"""^
        (0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}  # Release segment
        (\.post(0|[1-9][0-9]*))?               # '.post' release segment
        (\+[0-9a-f]{7}(?:\.dirty)?)?           # Local version identifier
    $"""
    program_version = version(Constants.PROGRAM_NAME)
    assert re.fullmatch(pypa_spec_compliant_version_regex, program_version, re.ASCII|re.VERBOSE) is not None
    assert program_version == Constants.VERSION


def test_program_name_matches_metadata() -> None:
    """Test the hardcorded app name is what it should be."""
    assert metadata(Constants.PROGRAM_NAME)['Name'] ==  Constants.PROGRAM_NAME
