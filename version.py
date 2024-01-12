"""Define sacamantecas version, according to Semantic Versioning 2.0 (https://semver.org/)"""
import sys


V_MAJOR = '5'
V_MINOR = '0'
V_PATCH = '0'
V_PRERELEASE = 'beta-3'
V_BUILD = __import__('time').strftime('%Y%m%d-%H%M%S')

SEMVER = f'{V_MAJOR}.{V_MINOR}.{V_PATCH}'
SEMVER += f'-{V_PRERELEASE}' if V_PRERELEASE else ''
SEMVER += f'+{V_BUILD}' if V_PRERELEASE and V_BUILD else ''

# Development mode is enabled if a prerelease version is running within a virtual environment.
DEVELOPMENT_MODE = bool(V_PRERELEASE and sys.prefix != sys.base_prefix)  # pylint: disable=unused-variable
