"""
Build sacamantecas.

Builds sacamantecas executable for Win32 in a virtual environment.

Creates the virtual environment first if it does not exist, installs the needed
requirements inside and then runs the building process.
"""
import sys
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from mkvenv import is_venv_active, mkvenv, VenvCreationError
from utils import error, run, RunError


def get_version(program_name):
    """Get the version code from program_name."""
    version = None
    reason = ''
    script_name = program_name + '.py'
    try:
        with open(script_name, encoding='utf-8') as program:
            for line in program.readlines():
                if line.startswith('__version__'):
                    version = line.strip().split(' = ')[1].strip("'")
                    break
    except FileNotFoundError:
        reason = f'{script_name} does not exist'
    except PermissionError:
        reason = f'{script_name} cannot be read'
    else:
        if version is None:
            reason = 'missing version number'
    if reason:
        print()
        error(f'Unable to detect {program_name} version, {reason}.')
        version = None
    return version


def build_executable(pyinstaller_path, program_name):
    """Build the frozen executable."""
    build_path = pyinstaller_path.parent.parent / 'build'
    dist_path = build_path.with_stem('dist')
    executable = (dist_path / program_name).with_suffix('.exe')
    if executable.exists():
        # Remove executable produced by previous runs.
        os.remove(executable)
    print('Building executable.')
    cmd = [pyinstaller_path]
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={build_path}', f'--specpath={build_path}', f'--distpath={dist_path}'])
    cmd.extend(['--onefile', program_name + '.py'])
    try:
        result = run(cmd)
    except RunError as exc:
        if exc.returncode:
            print(exc.stderr)
    if result.returncode or not executable.exists():
        error('Executable was not created.')
        return None
    return executable


def create_zip_bundle(bundle_path, executable):
    """Create the ZIP bundle."""
    print(f'Creating ZIP bundle {bundle_path}')
    with ZipFile(bundle_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.write(executable, executable.name)
        bundle.write(executable.with_suffix('.ini').name)


def main():
    """."""
    # Name of the program, for future use.
    program_name = Path(os.getcwd()).name

    print(f'Building {program_name}', end='', flush=True)

    # Get version number being built.
    version = get_version(program_name)
    if version is None:
        return 1
    print('', version)

    # Create virtual environment and get its location.
    if not is_venv_active():
        try:
            print('Creating virtual environment.')
            venv_path = mkvenv()
            print(f'Virtual environment created at {venv_path}')
        except VenvCreationError as exc:
            error(f'creating virtual environment.\n{exc}.')
            return 1

    # The virtual environment is guaranteed to work from this point on.

    # Build the frozen executable.
    executable = build_executable(venv_path / 'Scripts' / 'pyinstaller.exe', program_name)
    if executable is None:
        return 1

    # Executable was created, so create ZIP bundle.
    create_zip_bundle(f'{program_name}_{version}.zip', executable)

    print('Successful build.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
