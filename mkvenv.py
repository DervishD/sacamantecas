"""
Create virtual environment for sacamantecas.

Creates a virtual environment for sacamantecas if it does not exist. Also, it
provides a public function to get the full path for the virtual environment.
"""
import sys
import os
import venv
from pathlib import Path
from utils import error, run, RunError


class VenvError(Exception):
    """Base exception for all module defined exceptions."""


class VenvNotFoundError(VenvError):
    """Exception to signal that virtual environment was not found."""


class VenvCreationError(VenvError):
    """Exception to signal error when creating virtual environment."""


def get_venv_path():
    """
    Get the virtual environment path for this project.
    IT HAS TO BE THE FIRST LINE IN THE '.gitignore' FILE.
    IT HAS TO CONTAIN THE STRING 'venv' SOMEWHERE.
    """
    venv_path = None
    try:
        with open('.gitignore', encoding='utf-8') as gitignore:
            venv_path = gitignore.readline().strip()
            if 'venv' not in venv_path:
                venv_path = None
    except FileNotFoundError as exc:
        raise VenvNotFoundError('.gitignore does not exist') from exc
    except PermissionError as exc:
        raise VenvNotFoundError('.gitignore cannot be read') from exc

    if venv_path is None:
        raise VenvNotFoundError('.gitignore does not contain a virtual environment path')

    venv_path = Path(venv_path)
    if venv_path.exists() and not venv_path.is_dir():
        raise VenvNotFoundError('Virtual environment path exists but it is not a directory')

    return venv_path


def create_venv(venv_path):
    """Create virtual environment at 'venv_path'."""
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
        run((venv_path / 'Scripts' / 'pip.exe', 'install', '-r', 'requirements.txt'))
    except RunError as exc:
        raise VenvCreationError(f'pip: {exc.stderr}') from exc
    return venv_path


def mkvenv():  # pylint: disable=unused-variable
    """
    Helper function to simplify virtual environment creation from script which
    import this module, making the procedure simpler and shorter to write.
    """
    try:
        return create_venv(get_venv_path())
    except VenvNotFoundError as exc:
        raise VenvCreationError from exc


def main():
    """."""
    try:
        venv_path = get_venv_path()
    except VenvNotFoundError as exc:
        error(f'determining virtual environment path.\n{exc}.')
        return 1

    print(f'Creating virtual environment at «{venv_path}».')
    try:
        create_venv(venv_path)
    except VenvCreationError as exc:
        error(f'creating virtual environment.\n{exc}')
        return 1
    print(f'Virtual environment succesfully created at «{venv_path}».')
    return 0


if __name__ == '__main__':
    sys.exit(main())
