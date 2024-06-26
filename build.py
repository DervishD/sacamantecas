"""Building script.

Build application executable for Win32 in a virtual environment
and pack it with the INI file in a ZIP file for distribution.
"""
from collections.abc import Sequence
from io import TextIOWrapper
import os
from subprocess import CalledProcessError, CompletedProcess, run
import sys
from typing import TextIO
from zipfile import ZIP_DEFLATED, ZipFile

from sacamantecas import Constants
from version import SEMVER

UTF8 = Constants.UTF8
APP_PATH = Constants.APP_PATH
VENV_PATH = APP_PATH.parent / '.venv'
BUILD_PATH = APP_PATH.parent / 'build'
PYINSTALLER = VENV_PATH / 'Scripts' / 'pyinstaller.exe'
FROZEN_EXE_PATH = (BUILD_PATH / APP_PATH.name).with_suffix('.exe')
PACKAGE_PATH = APP_PATH.with_stem(f'{APP_PATH.stem}_v{SEMVER.split('+')[0]}').with_suffix('.zip')
INIFILE_PATH = Constants.INIFILE_PATH
ERROR_MARKER = '\n*** '
ERROR_HEADER = 'Error, '
PROGRESS_MARKER = '  ▶ '


# Reconfigure standard output streams so they use UTF-8 encoding, no matter
# if they are redirected to a file when running the program from a shell.
if sys.stdout and isinstance(sys.stdout, TextIOWrapper):
    sys.stdout.reconfigure(encoding=Constants.UTF8)
if sys.stderr and isinstance(sys.stderr, TextIOWrapper):
    sys.stderr.reconfigure(encoding=Constants.UTF8)


def pretty_print(message: str, *, marker: str = '', header: str = '', stream: TextIO = sys.stdout) -> None:
    """Pretty-print message to stream, with a final newline.

    The first line contains the marker and header, if any, and the rest of lines
    are indented according to the length of the marker so they are aligned with
    the header.

    The stream is finally flushed to ensure the message is printed.

    By default, marker and header are empty and the stream is sys.stdout.
    """
    marker_len = len([char for char in marker if char.isprintable()])

    lines = message.splitlines() if message else ['']
    lines[0] = f'{marker}{header}{lines[0]}'
    lines[1:] = [f'\n{' ' * marker_len}{line}' for line in lines[1:]]
    lines[-1] += '\n'
    stream.writelines(lines)
    stream.flush()


def error(message: str) -> None:
    """Pretty-print error message to sys.stderr."""
    pretty_print(message, marker=ERROR_MARKER, header=ERROR_HEADER, stream=sys.stderr)


def progress(message: str) -> None:
    """Pretty-print progress message to sys.stdout."""
    pretty_print(message, marker=PROGRESS_MARKER)


def run_command(command: Sequence[str]) -> CompletedProcess[str]:
    """Run command, capturing the output."""
    try:
        return run(command, check=True, capture_output=True, encoding=UTF8, text=True)
    except FileNotFoundError as exc:
        raise CalledProcessError(0, command, None, f"Command '{command[0]}' not found.\n") from exc


def is_venv_ready() -> bool:
    """Check if virtual environment is active and functional."""
    progress(f'Checking virtual environment at {VENV_PATH}')

    # If no virtual environment exists, try to use global packages.
    if not VENV_PATH.exists():
        return True

    # But if it exists, it has to be active.
    if os.environ['VIRTUAL_ENV'].lower() != str(VENV_PATH).lower():
        error('wrong or missing VIRTUAL_ENV environment variable.')
        return False

    if sys.prefix == sys.base_prefix:
        error('virtual environment is not active.')
        return False

    return True


def are_required_packages_installed() -> bool:
    """Check installed packages to ensure they fit requirements.txt contents."""
    progress('Checking that required packages are installed')

    pip_list = ['pip', 'list', '--local', '--format=freeze', '--not-required', '--exclude=pip']
    installed_packages = {package.split('==')[0] for package in run_command(pip_list).stdout.splitlines()}

    with open('requirements.txt', 'rt', encoding='utf-8') as requirements:
        required_packages = [line for line in requirements.readlines() if not line.startswith('#')]
        required_packages = {package.split('>=')[0] for package in required_packages}

    if diff := required_packages - installed_packages:
        diff = '\n'.join(diff)
        error(f'missing packages:\n{diff}\n')
        return False

    return True


def build_frozen_executable() -> bool:
    """Build frozen executable."""
    progress('Building frozen executable')

    if FROZEN_EXE_PATH.exists():
        os.remove(FROZEN_EXE_PATH)

    cmd = [str(PYINSTALLER)]
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={BUILD_PATH}', f'--specpath={BUILD_PATH}', f'--distpath={BUILD_PATH}'])
    cmd.extend(['--onefile', str(APP_PATH)])
    try:
        run_command(cmd)
    except CalledProcessError as exc:
        error(f'could not create frozen executable.\n{exc.stderr}')
        return False

    return True


def build_package() -> None:
    """Build distributable package."""
    progress(f'Building distributable package {PACKAGE_PATH}.')

    with ZipFile(PACKAGE_PATH, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.write(FROZEN_EXE_PATH, FROZEN_EXE_PATH.name)
        bundle.write(INIFILE_PATH, INIFILE_PATH.name)


def main() -> int:
    """."""
    pretty_print(f'Building {APP_PATH.stem} {SEMVER}')

    if not is_venv_ready():
        return 1

    if not are_required_packages_installed():
        return 1

    # The virtual environment is guaranteed to work from this point on.

    if not build_frozen_executable():
        return 1
    build_package()

    pretty_print('\nApplication built successfully!')

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
