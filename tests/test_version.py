#! /usr/bin/env python3
"""Test suite for validating application version string."""
import re

from sacamantecas import SEMVER

# Regular expression obtained directly from https://semver.org/
# from the 'official' sample at https://regex101.com/r/Ly7O1x/3/
# but without the named capturing groups, as they are not needed.
SEMVER_REGEX = r"""^
    # MAJOR.MINOR.PATCH:
    (?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)
    # Dot separated prerelease identifiers:
    (?:-(?:(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?
    # Dot separated build identifiers:
    (?:\+(?:[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?
$"""
def test_validate_version_string() -> None:  # pylint: disable=unused-variable
    """Test application version string."""
    assert re.fullmatch(SEMVER_REGEX, SEMVER, re.ASCII|re.VERBOSE) is not None
