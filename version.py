"""Define sacamantecas version, according to Semantic Versioning 2.0 (https://semver.org/)."""
# pylint: disable=unused-variable
import sys
from time import strftime

V_MAJOR = '5'
V_MINOR = '2'
V_PATCH = '0'
V_PRERELEASE = 'alpha'
V_BUILD = strftime('%Y%m%d-%H%M%S')

SEMVER = f'{V_MAJOR}.{V_MINOR}.{V_PATCH}' + (f'-{V_PRERELEASE}+{V_BUILD}' if V_PRERELEASE else '')

# Development mode is enabled if a prerelease version is running within a virtual environment.
DEVELOPMENT_MODE = bool(V_PRERELEASE and sys.prefix != sys.base_prefix)
