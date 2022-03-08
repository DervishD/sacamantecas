"""
Build sacamantecas.

Builds sacamantecas executable for Win32 in a virtual environment.

Creates the virtual environment first if it does not exist, installs the needed
requirements inside and then runs the building process.
"""
import sys
import os
import venv
import subprocess
import zipfile


# Set to 'True' if diagnostic output is needed.
DEBUG = False


def error(message):
    """Pretty-print 'message' to stderr."""
    print(f'*** Error: {message}', flush=True, file=sys.stderr)


def main():  # pylint: disable=too-many-branches,too-many-statements,too-many-locals,too-many-return-statements
    """."""
    # Name of the program, for future use.
    program_name = os.path.basename(os.getcwd())

    print(f'Building {program_name}', end='', flush=True)
    version = None
    reason = ''
    try:
        script_name = program_name + '.py'
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
        return 1

    print('', version)

    # Get the virtual environment directory name.
    # IT HAS TO BE THE FIRST LINE IN THE '.gitignore' FILE.
    # IT HAS TO CONTAIN THE STRING 'venv' SOMEWHERE.
    venv_path = None
    reason = ''
    try:
        with open('.gitignore', encoding='utf-8') as gitignore:
            venv_path = gitignore.readline().strip()
            if 'venv' not in venv_path:
                venv_path = None
    except FileNotFoundError:
        reason = '.gitignore does not exist'
    except PermissionError:
        reason = '.gitignore cannot be read'
    else:
        if venv_path is None:
            reason = 'missing venv directory in .gitignore'
    if reason:
        error(f'Unable to detect venv, {reason}.')
        return 1

    if os.path.exists(venv_path) and not os.path.isdir(venv_path):
        error('Venv directory name exists and it is not a directory.')
        return 1

    # Create the virtual environment if it does not exist.
    if not os.path.exists(venv_path):
        print(f'Creating venv at "{venv_path}".')
        with open(os.devnull, 'w', encoding='utf-8') as devnull:
            # Save a reference for the original stdout so it can be restored later.
            duplicated_stdout_fileno = os.dup(1)

            # Flush buffers, because os.dup2() is not aware of them.
            sys.stdout.flush()
            # Point file descriptor 1 to devnull if not DEBUG mode.
            if not DEBUG:
                os.dup2(devnull.fileno(), 1)

            # The normal output for the calls below is suppressed.
            # Error output is not.
            venv.create(venv_path, with_pip=True, upgrade_deps=True)

            # Flush buffers, because os.dup2() is not aware of them.
            sys.stdout.flush()
            # Restore file descriptor 1 to its original output if not DEBUG mode.
            if not DEBUG:
                os.dup2(duplicated_stdout_fileno, 1)

    # The virtual environment is guaranteed to exist below this point.
    print(f'Venv detected at {venv_path}')

    # The virtual environment does not really need to be activated, because the
    # commands that will be run will be the ones INSIDE the virtual environment.
    #
    # So, the only other thing that is MAYBE needed it setting the 'VIRTUAL_ENV'
    # environment variable so the launched programs can detect they are really
    # running inside a virtual environment. Apparently this is not essential,
    # but it is easy to do and will not do any harm.
    os.environ['VIRTUAL_ENV'] = os.path.abspath(venv_path)
    bin_path = os.path.join(venv_path, 'Scripts')  # Path for launched venv-programs.

    # Suppress normal output for the launched programs if not DEBUG mode.
    # Error output is always shown.
    stdout = subprocess.DEVNULL if not DEBUG else None

    # Install needed packages.
    print('Installing needed packages.')
    cmd = [os.path.join(bin_path, 'pip'), 'install', '-r', 'requirements.txt']
    try:
        subprocess.run(cmd, check=True, stdout=stdout)
    except subprocess.CalledProcessError as exc:
        error(f'Problem calling {cmd[0]} (returned {exc.returncode}).')
        return 1

    # Create the executable.
    build_path = os.path.join(venv_path, 'build')
    dist_path = os.path.join(venv_path, 'dist')
    executable = os.path.join(dist_path, program_name + '.exe')
    if os.path.exists(executable):
        # Remove executable produced by previous runs.
        os.remove(executable)
    print('Building executable.')
    cmd = [os.path.join(bin_path, 'pyinstaller')]
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={build_path}', f'--specpath={build_path}', f'--distpath={dist_path}'])
    cmd.extend(['--onefile', script_name])
    try:
        subprocess.run(cmd, check=True, stdout=stdout)
    except subprocess.CalledProcessError as exc:
        error(f'Problem calling {cmd[0]} (returned {exc.returncode}).')
        return 1
    if not os.path.exists(executable):
        error('Executable was not created.')
        return 1

    # Executable was created, so create ZIP bundle.
    bundle_path = f'{program_name}_{version}.zip'
    print(f'Creating ZIP bundle {bundle_path}')
    with zipfile.ZipFile(bundle_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        bundle.write(executable, program_name + '.exe')
        bundle.write(program_name + '.ini')

    print('Successful build.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
