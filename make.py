"""
Build sacamantecas.

Builds sacamantecas executable for Win32 in a virtual environment.

Creates the virtual environment first if it does not exist, installs the needed
requirements inside and then runs the building process.
"""
import sys
import os
from zipfile import ZipFile, ZIP_DEFLATED
from mkvenv import get_venv_path, is_venv_active, mkvenv, VenvCreationError
from utils import PROGRAM_ROOT, PROGRAM_PATH, PROGRAM_NAME, PROGRAM_LABEL, error, run, RunError


def build_frozen_executable(venv_path):
    """Build frozen executable."""
    print(f'Building {PROGRAM_LABEL} frozen executable.')
    pyinstaller_path = venv_path / 'Scripts' / 'pyinstaller.exe'
    build_path = pyinstaller_path.parent.parent / 'build'
    dist_path = build_path.with_stem('dist')
    executable = (dist_path / PROGRAM_NAME).with_suffix('.exe')
    if executable.exists():
        # Remove executable produced by previous runs.
        os.remove(executable)
    print('Building executable.')
    cmd = [pyinstaller_path]
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={build_path}', f'--specpath={build_path}', f'--distpath={dist_path}'])
    cmd.extend(['--onefile', PROGRAM_PATH])
    try:
        result = run(cmd)
    except RunError as exc:
        if exc.returncode:
            print(exc.stderr)
    if result.returncode or not executable.exists():
        error('Executable was not created.')
        return False

    # Executable was created, so create ZIP bundle.
    bundle_path = PROGRAM_ROOT / f'{PROGRAM_LABEL.replace(" ", "_")}.zip'
    print(f'Creating ZIP bundle «{bundle_path}».')
    with ZipFile(bundle_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        inifile = PROGRAM_PATH.with_suffix('.ini')
        bundle.write(executable, executable.name)
        bundle.write(inifile, inifile.name)
    print('Successful build.')
    return True


def create_virtual_environment(arg):
    """Create virtual environment."""


def run_unit_tests(arg):
    """Run the automated unit test suite."""


def main():
    """."""
    if len(sys.argv):
        match sys.argv[0].upper():
            case 'B' | 'BUILD':  # Build executable.
                operation = build_frozen_executable
            case 'V' | 'VENV':  # Create virtual environment.
                operation = create_virtual_environment
            case 'T' | 'TEST':  # Run the unit tests.
                operation = run_unit_tests
            case _:  # By default, build executable.
                operation = build_frozen_executable

    # Create virtual environment and get its location.
    if is_venv_active():
        venv_path = get_venv_path()
    else:
        try:
            print('Creating virtual environment.')
            venv_path = mkvenv()
            print(f'Virtual environment created at «{venv_path}».')
        except VenvCreationError as exc:
            error(f'creating virtual environment.\n{exc}.')
            return 1

    # The virtual environment is guaranteed to work from this point on.

    # Build the frozen executable.
    if not operation(venv_path):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
