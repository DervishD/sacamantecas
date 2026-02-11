"""Building script.

Build application executable for `Win32` in a virtual environment and
pack it together with the corresponding `.ini` file in a `.zip` file for
distribution.
"""
import os
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run
import sys
import tomllib
from typing import cast, TextIO, TYPE_CHECKING
from zipfile import ZIP_DEFLATED, ZipFile

from sacamantecas import Constants

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import TextIOWrapper


SCRIPT_PATH = sys.modules[Constants.__module__].__file__ or ''
BASE_PATH = Path(__file__).parent
VENV_PATH = BASE_PATH / '.venv'
BUILD_PATH = BASE_PATH / 'build'
PYINSTALLER = VENV_PATH / 'Scripts' / 'pyinstaller.exe'
FROZEN_EXE_PATH = (BUILD_PATH / Constants.APP_NAME).with_suffix('.exe')
PACKAGE_SUFFIX = 'zip'
PACKAGE_PATH = BASE_PATH / f'{Constants.APP_NAME}_v{Constants.APP_VERSION.split('+', maxsplit=1)[0]}.{PACKAGE_SUFFIX}'
PYPROJECT_FILE = BASE_PATH / 'pyproject.toml'
ERROR_MARKER = '\n*** '
ERROR_HEADER = 'Error, '
PROGRESS_MARKER = '  ▶ '

# Reconfigure standard output streams so they use UTF-8 encoding even if
# they are redirected to a file when running the program from a shell.
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    cast('TextIOWrapper', sys.stdout).reconfigure(encoding=Constants.UTF8)
if sys.stderr and hasattr(sys.stdout, 'reconfigure'):
    cast('TextIOWrapper', sys.stderr).reconfigure(encoding=Constants.UTF8)


def pretty_print(message: str, *, marker: str = '', header: str = '', stream: TextIO = sys.stdout) -> None:
    """Pretty-print *message* to *stream*, with a final newline.

    The first line of the output will contain the *marker* and *header*,
    which are empty strings by default. All the subsequent lines will be
    indented with the length of the *marker* so they appear aligned with
    the *header*.

    The *stream* (`sys.stdout` by default) is finally flushed to ensure
    the message is printed.
    """
    marker_len = len([char for char in marker if char.isprintable()])

    lines = message.splitlines() if message else ['']
    lines[0] = f'{marker}{header}{lines[0]}'
    lines[1:] = [f'\n{' ' * marker_len}{line}' for line in lines[1:]]
    lines[-1] += '\n'
    stream.writelines(lines)
    stream.flush()


def error(message: str) -> None:
    """Pretty-print error message to `sys.stderr`."""
    pretty_print(message, marker=ERROR_MARKER, header=ERROR_HEADER, stream=sys.stderr)


def progress(message: str) -> None:
    """Pretty-print progress message to `sys.stdout`."""
    pretty_print(message, marker=PROGRESS_MARKER)


def run_command(command: Sequence[str]) -> CompletedProcess[str]:
    """Run *command*, capturing its output."""
    try:
        return run(command, check=True, capture_output=True, encoding=Constants.UTF8, text=True)  # noqa: S603
    except FileNotFoundError as exc:
        raise CalledProcessError(0, command, None, f"Command '{command[0]}' not found.\n") from exc


def is_venv_ready() -> bool:
    """Check if the virtual environment is active and functional."""
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
    """Check application dependencies."""
    progress('Checking that required packages are installed')

    pip_list = ['pip', 'list', '--local', '--format=freeze', '--not-required', '--exclude=pip', '--exclude-editable']
    installed_packages = {line.strip() for line in run_command(pip_list).stdout.splitlines()}

    with PYPROJECT_FILE.open('rb') as pyproject:
        pyproject_contents = tomllib.load(pyproject)
        dependencies = set(pyproject_contents['project']['dependencies'])

    if diff := dependencies - installed_packages:
        diff = '\n'.join(diff)
        error(f'missing packages:\n{diff}\n')
        return False

    return True


def build_frozen_executable() -> bool:
    """Build frozen executable."""
    progress('Building frozen executable')

    if FROZEN_EXE_PATH.exists():
        FROZEN_EXE_PATH.unlink()

    cmd = [str(PYINSTALLER)]
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={BUILD_PATH}', f'--specpath={BUILD_PATH}', f'--distpath={BUILD_PATH}'])
    cmd.extend(['--copy-metadata', Constants.APP_NAME, '--onefile', '--name', Constants.APP_NAME])
    cmd.append(SCRIPT_PATH)
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
        bundle.write(Constants.INIFILE_PATH, Constants.INIFILE_PATH.name)


def main() -> int:
    """."""
    pretty_print(f'Building {Constants.APP_NAME} {Constants.APP_VERSION}')

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
