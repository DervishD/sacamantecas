#! /usr/bin/env python3
"""Test suite for validating application version string."""
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
# 'dev' release segment uses a dot and not a hyphen as separator. The
# local version identifier, however, is actually compliant!
#
# The scheme does not make use of all defined segments. To wit, it uses
# ONLY the 'release' segment, but for development both a 'dev' release
# segment and a local version identifier are added. The 'dev' release
# segment includes the number of commits since the latest tagged commit,
# and the local local version identifier contains the abbreviated hash
# of the current commit, and an optional marker if the working copy is
# dirty, that is, current working copy has uncommitted changes. As such,
# the regex used to validate the version string has been adapted from
# the one provided in 'PyPA' documentation.
VERSION_REGEX = r"""^
    (0|[1-9][0-9]*)(\.(0|[1-9][0-9]*)){2}  # Release segment
    (\.dev(0|[1-9][0-9]*))?                # 'dev' release segment
    (\+[0-9a-f]{7}(?:\.dirty)?)?           # Local version identifier
$"""

def test_validate_version_string() -> None:  # pylint: disable=unused-variable
    """Test application version string."""
    assert re.fullmatch(VERSION_REGEX, Constants.APP_VERSION, re.ASCII|re.VERBOSE) is not None
