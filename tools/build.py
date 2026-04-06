"""Building script.

Build program executable for `Win32` in a virtual environment and pack
it, together with the corresponding `.ini` file and other assets, in a
`.zip` bundle for distribution.
"""  # noqa: INP001
import os
from pathlib import Path
import shutil
from subprocess import CalledProcessError, CompletedProcess, run
import sys
from typing import cast, TextIO, TYPE_CHECKING
from zipfile import ZIP_DEFLATED, ZipFile

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from io import TextIOWrapper

PROJECT_ROOT = Path(run(
    ['git', 'rev-parse', '--show-toplevel'],  # noqa: S607
    encoding='utf-8',
    capture_output=True,
    check=True).stdout.strip(),
).resolve()
PACKAGE_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(PACKAGE_DIR))
from sacamantecas.about import DEPENDENCIES, PROGRAM_NAME, VERSION  # noqa: E402

VENV_PATH = PROJECT_ROOT / '.venv'
BUILD_PATH = PROJECT_ROOT / 'build'
PACKAGE_ROOT = PACKAGE_DIR / PROGRAM_NAME

ENTRY_POINT = PACKAGE_ROOT / '__main__.py'
BUNDLE_ASSETS = (
    PACKAGE_ROOT / f'{PROGRAM_NAME}.ini',
    PROJECT_ROOT / 'README.md',
    PROJECT_ROOT / 'CHANGELOG.md',
)

ERROR_MARKER = '\n*** '
ERROR_HEADER = 'Error, '
PROGRESS_MARKER = '  ▶ '

# Reconfigure standard output streams so they use UTF-8 encoding even if
# they are redirected to a file when running the program from a shell.
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    cast('TextIOWrapper', sys.stdout).reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stdout, 'reconfigure'):
    cast('TextIOWrapper', sys.stderr).reconfigure(encoding='utf-8')


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
        return run(command, check=True, capture_output=True, encoding='utf-8', text=True)  # noqa: S603
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


def are_required_packages_installed(required_packages: list[str]) -> bool:
    """Check that *required_packages* are installed."""
    pip_list = ['pip', 'list', '--local', '--format=freeze', '--not-required', '--exclude=pip', '--exclude-editable']
    installed_packages = {line.strip() for line in run_command(pip_list).stdout.splitlines()}
    installed_packages.add('legion')  # TODO: remove when legion is no longer an editable install.

    if diff := set(required_packages) - installed_packages:
        diff = '\n'.join(diff)
        error(f'missing packages:\n{diff}\n')
        return False

    return True


def prepare_build_directory(build_path: Path) -> bool:
    """Prepare the *build_path* build directory."""
    # Create the directory if it does not already exist.
    # Create the .gitignore file.
    # Remove current contents except .gitignore file.
    error_message = 'last build leftovers cannot be removed.'
    try:
        shutil.rmtree(build_path)
        error_message = 'build directory cannot be created'
        build_path.mkdir()
        error_message = 'the .gitignore file cannot be created'
        (build_path / '.gitignore').write_text(f'# Created by {Path(__file__).name}\n*\n', encoding='utf-8')
    except PermissionError:
        error(error_message)
        return False
    return True


def build_frozen_executable(script_path: Path, frozen_exe_path: Path) -> bool:
    """Build *frozen_exe_path* from *script_path*."""
    build_path = frozen_exe_path.parent

    if frozen_exe_path.exists():
        frozen_exe_path.unlink()

    cmd = ['pyinstaller']
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={build_path}', f'--specpath={build_path}', f'--distpath={build_path}'])
    cmd.extend(['--onefile', '--name', frozen_exe_path.stem])
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
    pretty_print(f'Building {PROGRAM_NAME} {VERSION}')

    progress(f'Checking virtual environment: {VENV_PATH}')
    if not is_venv_ready(VENV_PATH):
        return 1

    required_packages = DEPENDENCIES
    progress(f'Checking that required packages are installed: {', '.join(required_packages)}')
    if not are_required_packages_installed(required_packages):
        return 1

    # CLEAN THE OLD BUILDING LEFTOVERS
    progress(f'Preparing build directory: {BUILD_PATH}')
    if not prepare_build_directory(BUILD_PATH):
        return 1

    # The virtual environment is guaranteed to work from this point on.
    frozen_exe_path = (BUILD_PATH / PROGRAM_NAME).with_suffix('.exe')
    progress(f'Building frozen executable: {frozen_exe_path}')
    if not build_frozen_executable(ENTRY_POINT, frozen_exe_path):
        return 1

    bundle_path = PROJECT_ROOT / f'{PROGRAM_NAME}_v{VERSION.split('+', maxsplit=1)[0]}.zip'
    progress(f'Building distributable bundle: {bundle_path}')
    manifest = (frozen_exe_path, *BUNDLE_ASSETS)
    create_bundle(bundle_path, manifest)

    pretty_print('\nApplication built successfully!')

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
