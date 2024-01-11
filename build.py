"""
Build application executable for Win32 in a virtual environment
and pack it with the INI file in a ZIP file for distribution.
"""
import os
from pathlib import Path
from subprocess import CalledProcessError, run
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from version import APP_NAME, SEMVER

UTF8 = 'utf-8'
ROOT_PATH = Path(__file__).parent
APP_PATH = Path(__file__).with_stem(APP_NAME)
VENV_PATH = ROOT_PATH / '.venv'
BUILD_PATH = ROOT_PATH / 'build'
PYINSTALLER = VENV_PATH / 'Scripts' / 'pyinstaller.exe'
FROZEN_EXE_PATH = (BUILD_PATH / APP_NAME).with_suffix('.exe')
PACKAGE_PATH = ROOT_PATH / f'{APP_NAME}_v{SEMVER.split('+')[0]}.zip'


# Reconfigure standard output streams so they use UTF-8 encoding, no matter
# if they are redirected to a file when running the program from a shell.
sys.stdout.reconfigure(encoding=UTF8)
sys.stderr.reconfigure(encoding=UTF8)


def pretty_print(marker, header, message, stream):
    """
    Pretty-print message to stream, with a final newline.

    The first line contains the marker and header, and the rest are indented
    according to the length of the marker so they are aligned with the header.

    A final newline is added.

    The stream is finally flushed to ensure the message is printed.
    """
    lines = message.splitlines()
    lines[0] = f'{marker}{header}{lines[0]}'
    lines[1:] = [f'\n{' ' * len(marker)}{line}' for line in lines[1:]]
    lines[-1] += '\n'
    stream.writelines(lines)
    stream.flush()


def error(message):
    """Pretty-print error message to sys.stderr."""
    marker = '*** '
    header = 'Error, '
    stream = sys.stderr
    print('', file=stream)
    pretty_print(marker, header, message, stream)


def progress(message):
    """Pretty-print progress message to sys.stdout."""
    marker = '  ▶ '
    pretty_print(marker, '', message, sys.stdout)


def run_command(command):
    """Helper for running commands and capturing the output."""
    try:
        return run(command, check=True, capture_output=True, encoding=UTF8, text=True)
    except FileNotFoundError as exc:
        raise CalledProcessError(0, command, None, f"Command '{command[0]}' not found.\n") from exc


def is_venv_ready():
    """Checks if virtual environment is active and functional."""
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


def are_required_packages_installed():
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


def build_frozen_executable():
    """Build frozen executable."""
    progress('Building frozen executable')

    if FROZEN_EXE_PATH.exists():
        os.remove(FROZEN_EXE_PATH)

    cmd = [PYINSTALLER]
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={BUILD_PATH}', f'--specpath={BUILD_PATH}', f'--distpath={BUILD_PATH}'])
    cmd.extend(['--onefile', APP_PATH])
    try:
        run_command(cmd)
    except CalledProcessError as exc:
        error(f'could not create frozen executable.\n{exc.stderr}')
        return False

    return True


def build_package():
    """Build distributable package."""
    progress(f'Building distributable package {PACKAGE_PATH}.')

    inifile = APP_PATH.with_suffix('.ini')
    with ZipFile(PACKAGE_PATH, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.write(FROZEN_EXE_PATH, FROZEN_EXE_PATH.name)
        bundle.write(inifile, inifile.name)


def main():
    """."""
    print(f'Building {APP_NAME} {SEMVER}')

    if not is_venv_ready():
        return 1

    if not are_required_packages_installed():
        return 1

    # The virtual environment is guaranteed to work from this point on.

    if not build_frozen_executable():
        return 1
    build_package()

    print('\nApplication built successfully!')

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
