"""
Build sacamantecas.

Builds sacamantecas executable for Win32 in a virtual environment.

Creates the virtual environment first if it does not exist, installs the needed
requirements inside and then runs the building process.
"""
import sys
import os
import venv
from zipfile import ZipFile, ZIP_DEFLATED
from utils import PROGRAM_ROOT, PROGRAM_PATH, PROGRAM_NAME, PROGRAM_LABEL, error, run, RunError


def is_venv_active():
    """
    Check if virtual environment is active.

    This only checks if the 'VIRTUAL_ENV' environment variable is set or not,
    which is proof that the virtual environment has been activated, but it does
    NOT check if the virtual environment is properly set up (e.g. all needed
    packages are installed or not.)

    """
    return 'VIRTUAL_ENV' in os.environ


def get_venv_path():  # pylint: disable=unused-variable
    """
    Get the virtual environment path for this project.
    IT HAS TO BE THE FIRST LINE IN THE '.gitignore' FILE.
    IT HAS TO CONTAIN THE STRING 'venv' SOMEWHERE.
    """
    venv_path = None
    gitignore = PROGRAM_ROOT / '.gitignore'
    message = None
    try:
        with open(gitignore, encoding='utf-8') as gitignore:
            venv_path = gitignore.readline().strip()
            if 'venv' not in venv_path:
                venv_path = None
    except FileNotFoundError:
        message = '.gitignore does not exist'
    except PermissionError:
        message = '.gitignore cannot be read'
    else:
        if venv_path is None:
            message = '.gitignore does not contain a virtual environment path'
        else:
            venv_path = PROGRAM_ROOT / venv_path
            if venv_path.exists() and not venv_path.is_dir():
                message = 'Virtual environment path exists but it is not a directory'

    if message:
        error(f'finding virtual environment path.\n{message}.')
        return None

    return venv_path


def create_virtual_environment(venv_path):
    """Create virtual environment."""
    print(f'Creating virtual environment at «{venv_path}».')
    if not venv_path.exists():
        with open(os.devnull, 'w', encoding='utf-8') as devnull:
            # Save a reference for the original stdout so it can be restored later.
            duplicated_stdout_fileno = os.dup(1)

            # Flush buffers, because os.dup2() is not aware of them.
            sys.stdout.flush()
            # Point file descriptor 1 to devnull to silent general output.
            os.dup2(devnull.fileno(), 1)

            # The normal output for the calls below is suppressed.
            # Error output is not.
            venv.create(venv_path, with_pip=True, upgrade_deps=True)

            # Flush buffers, because os.dup2() is not aware of them.
            sys.stdout.flush()
            # Restore file descriptor 1 to its original output.
            os.dup2(duplicated_stdout_fileno, 1)

    # The virtual environment does not really need to be activated, because the
    # commands that will be run will be the ones INSIDE the virtual environment.
    #
    # So, the only other thing that is MAYBE needed it setting the 'VIRTUAL_ENV'
    # environment variable so the launched programs can detect they are really
    # running inside a virtual environment. Apparently this is not essential,
    # but it is easy to do and will not do any harm.
    os.environ['VIRTUAL_ENV'] = str(venv_path.resolve())

    try:
        run((venv_path / 'Scripts' / 'pip.exe', 'install', '-r', PROGRAM_ROOT / 'requirements.txt'))
    except RunError as exc:
        error(f'creating virtual environment.\npip: {exc.stderr}.')
        return False

    print('Virtual environment created successfully.')
    return True


def build_frozen_executable(venv_path):
    """Build frozen executable."""
    print('Building frozen executable.')
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
        error('creating executable.')
        return False

    # Executable was created, so create ZIP bundle.
    bundle_path = PROGRAM_ROOT / f'{PROGRAM_LABEL.replace(" ", "_")}.zip'
    print(f'Creating ZIP bundle «{bundle_path}».')
    with ZipFile(bundle_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        inifile = PROGRAM_PATH.with_suffix('.ini')
        bundle.write(executable, executable.name)
        bundle.write(inifile, inifile.name)
    print('Frozen executable built successfully.')
    return True


def run_unit_tests(arg):
    """Run the automated unit test suite."""


def main():
    """."""
    print(f'Making {PROGRAM_LABEL}\n')

    # No matter the operation (the 'make target'), the first thing to check is
    # if the virtual environment is active. If the virtual environment is not
    # active it will be activated, if it does not exist it has to be created.
    if (venv_path := get_venv_path()) is None:
        return 1

    if not is_venv_active():
        # Create virtual environment.
        if not create_virtual_environment(venv_path):
            return 1

    # The virtual environment is guaranteed to work from this point on.

    # If creating and activating the virtual environment was the only operation
    # requested, then everything is done.
    if len(sys.argv) < 2 or sys.argv[1].lower() in ('v', 'venv'):
        return 1

    # A different operation was requested.
    if len(sys.argv) >= 2 and sys.argv[1].lower() in ('e', 'exe'):
        # Build the frozen executable.
        return not build_frozen_executable(venv_path)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
