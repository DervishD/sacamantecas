"""Building script.

Build application executable for `Win32` in a virtual environment and
pack it together with the corresponding `.ini` file in a `.zip` file for
distribution.
"""
from importlib.metadata import metadata
import os
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, run
import sys
from typing import cast, TextIO, TYPE_CHECKING
from zipfile import ZIP_DEFLATED, ZipFile

from sacamantecas import Constants

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from io import TextIOWrapper


VENV_DIRNAME = '.venv'
BUILD_DIRNAME = 'build'
BUNDLE_VERSION = Constants.APP_VERSION.split('+', maxsplit=1)[0]
BUNDLE_SUFFIX = 'zip'

PROJECT_ROOT = Path(__file__).parent.resolve()

PACKAGE_DATAFILES = (
    Constants.INIFILE_PATH,
    PROJECT_ROOT / 'README.md',
    PROJECT_ROOT / 'CHANGELOG.md',
)

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


def is_venv_ready(venv_path: Path) -> bool:
    """Check if the virtual environment is active and functional."""
    # If no virtual environment exists, try to use global packages.
    if not venv_path.exists():
        return True

    # But if it exists, it has to be active.
    if os.environ['VIRTUAL_ENV'].lower() != str(venv_path).lower():
        error('wrong or missing VIRTUAL_ENV environment variable.')
        return False

    if sys.prefix == sys.base_prefix:
        error('virtual environment is not active.')
        return False

    return True


def get_required_packages(distribution: str) -> set[str]:
    """Get the set of required packages for *distribution*."""
    return set(metadata(distribution).get_all('Requires-Dist', {}))


def are_required_packages_installed(required_packages: set[str]) -> bool:
    """Check that *required_packages* are installed."""
    pip_list = ['pip', 'list', '--local', '--format=freeze', '--not-required', '--exclude=pip', '--exclude-editable']
    installed_packages = {line.strip() for line in run_command(pip_list).stdout.splitlines()}

    if diff := required_packages - installed_packages:
        diff = '\n'.join(diff)
        error(f'missing packages:\n{diff}\n')
        return False

    return True


def build_frozen_executable(frozen_exe_path: Path) -> bool:
    """Build frozen executable at *frozen_exe_path*."""
    app_name = frozen_exe_path.stem
    build_path = frozen_exe_path.parent
    script_path = Path(getattr(sys.modules.get(app_name), '__file__', '')).resolve()

    if frozen_exe_path.exists():
        frozen_exe_path.unlink()

    cmd = ['pyinstaller']
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={build_path}', f'--specpath={build_path}', f'--distpath={build_path}'])
    cmd.extend(['--copy-metadata', app_name, '--onefile', '--name', app_name])
    cmd.append(str(script_path))
    try:
        run_command(cmd)
    except CalledProcessError as exc:
        error(f'could not create frozen executable.\n{exc.stderr}')
        return False

    return True


def create_bundle(bundle_path: Path, manifest:Iterable[Path]) -> None:
    """Build bundle at *bundle_path* containing *manifest* paths."""
    with ZipFile(bundle_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in manifest:
            bundle.write(path, path.name)


def main() -> int:
    """."""
    pretty_print(f'Building {Constants.APP_NAME} {Constants.APP_VERSION}')

    venv_path = PROJECT_ROOT / VENV_DIRNAME
    progress(f'Checking virtual environment: {venv_path}')
    if not is_venv_ready(venv_path):
        return 1

    required_packages = get_required_packages(Constants.APP_NAME)
    progress(f'Checking that required packages are installed: {', '.join(required_packages)}')
    if not are_required_packages_installed(required_packages):
        return 1

    # The virtual environment is guaranteed to work from this point on.

    frozen_exe_path = (PROJECT_ROOT / BUILD_DIRNAME / Constants.APP_NAME).with_suffix('.exe')
    progress(f'Building frozen executable: {frozen_exe_path}')
    if not build_frozen_executable(frozen_exe_path):
        return 1

    bundle_path = PROJECT_ROOT / f'{Constants.APP_NAME}_v{BUNDLE_VERSION}.{BUNDLE_SUFFIX}'
    progress(f'Building distributable bundle: {bundle_path}')
    manifest = (frozen_exe_path, *PACKAGE_DATAFILES)
    create_bundle(bundle_path, manifest)

    pretty_print('\nApplication built successfully!')

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
