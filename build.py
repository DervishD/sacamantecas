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
from utils import PROGRAM_NAME, PROGRAM_VERSION, PROGRAM_LABEL, error, run, RunError


def main():
    """."""
    print(f'Building {PROGRAM_LABEL}')

    # Create virtual environment and get its location.
    if is_venv_active():
        venv_path = get_venv_path()
    else:
        try:
            print('Creating virtual environment.')
            venv_path = mkvenv()
            print(f'Virtual environment created at {venv_path}')
        except VenvCreationError as exc:
            error(f'creating virtual environment.\n{exc}.')
            return 1

    # The virtual environment is guaranteed to work from this point on.

    # Build the frozen executable.
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
    cmd.extend(['--onefile', PROGRAM_NAME + '.py'])
    try:
        result = run(cmd)
    except RunError as exc:
        if exc.returncode:
            print(exc.stderr)
    if result.returncode or not executable.exists():
        error('Executable was not created.')
        return 1

    # Executable was created, so create ZIP bundle.
    bundle_path = f'{PROGRAM_NAME}_{PROGRAM_VERSION}.zip'
    print(f'Creating ZIP bundle {bundle_path}')
    with ZipFile(bundle_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.write(executable, executable.name)
        bundle.write(executable.with_suffix('.ini').name)

    print('Successful build.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
