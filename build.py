"""
Build sacamantecas.

Builds sacamantecas executable for Win32 in a virtual environment.

Creates the virtual environment first if it does not exist, installs the needed
requirements inside and then runs the building process.
"""
import sys
import os
import re
from pathlib import Path
from difflib import unified_diff
import venv
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED


def error(message):
    """Pretty-print 'message' to stderr."""
    print(f'*** Error: {message}', flush=True, file=sys.stderr)


def run_command(command):
    """Helper for running commands and capturing output if needed."""
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        error(f'Problem calling {command[0]} (returned {exc.returncode}).')
        return exc.returncode
    return result


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


def setup_venv():
    """Sets up virtual environment if needed."""
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
        return None

    venv_path = Path(venv_path)
    if venv_path.exists() and not venv_path.is_dir():
        error('Venv directory name exists and it is not a directory.')
        return None

    # Create the virtual environment if it does not exist.
    if not venv_path.exists():
        print(f'Creating venv at "{venv_path}".')
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
    return venv_path


def install_packages(pip_path):
    """Install needed packages in virtual environment."""
    print('Installing needed packages.')
    result = run_command((pip_path, 'install', '-r', 'requirements.txt'))
    if result.returncode:
        print(result.stderr)
        return False
    return True


def run_single_test(command, testitem):
    """Run a single test from the suite."""
    if testitem.endswith(('.txt', '.xlsx')):
        # testitem is a text or Excel file.
        testitem = outfile = reffile = Path(testitem)
        testitem = 'tests' / testitem
    else:
        # testitem is an URI.
        outfile = reffile = Path(re.sub(r'\W', '_', f'test_{testitem}', re.ASCII)).with_suffix('.txt')
    outfile = ('tests' / outfile).with_stem(f'{outfile.stem}_out')
    reffile = ('tests' / reffile).with_stem(f'{reffile.stem}_ref')

    # Remove output from previous runs (outfile)
    outfile.unlink(missing_ok=True)
    # Run the test. Since the command will always return a 0 status,
    # result.returncode is not checked. Failures will be handled below.
    result = run_command((*command, testitem))

    # If testitem is an URI, the test output must be written to the output file,
    # since by default is just dumped to console.
    if not str(testitem).endswith(('.txt', '.xlsx')):
        with open(outfile, 'w', encoding='utf-8') as dumpfile:
            dumpfile.write(result.stdout)

    # Compare the resulting files.
    # If any of them does not exist, consider the test failed.
    try:
        with open(outfile, encoding='utf-8') as ofile:
            outlines = ofile.readlines()
        with open(reffile, encoding='utf-8') as rfile:
            reflines = rfile.readlines()
    except FileNotFoundError as exc:
        return (f'*** File {exc.filename} does not exist.\n', )

    diff = list(unified_diff(outlines, reflines, str(outfile), str(reffile), n=1))
    if diff:
        diff.insert(0, '*** Differences found:\n')
        return diff
    return ()


def run_test_suite(command):
    """Run the automated test suite."""
    tests = (
        'file:///./tests/http___ceres_mcu_es_pages_Main_idt_134248_inventary_DE2016_1_24_table_FMUS_museum_MOM.html',
        'test_local.txt',
        # 'test_local.xlsx',
        'http://ceres.mcu.es/pages/Main?idt=134248&inventary=DE2016/1/24&table=FMUS&museum=MOM',
        'test_network.txt',
        # 'test_network.xlsx',
    )

    for testname, testitem in tests:
        testname = ''
        if testitem.endswith('.txt'):
            testname = 'TXT input, '
        if testitem.endswith('.xlsx'):
            testname = 'XLSX input, '
        if testitem.startswith('file://'):
            testname = 'file URI'
        if testitem.startswith('http://'):
            testname = 'http URI (potentially slow)'
        if '_local' in testitem:
            testname += 'file URIs'
        if '_network' in testitem:
            testname += 'http URIs (potentially slow)'
        print(f"Running test '{testname}' ", end='', flush=True)
        if output := run_single_test(command, testitem):
            print('❌\n')
            sys.stdout.writelines(output)
            return False
        print('✅')
    return True


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
    result = run_command(cmd)
    if result.returncode:
        print(result.stderr)
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

    # Set up virtual environment and get its location.
    venv_path = setup_venv()
    if venv_path is None:
        return 1
    print(f'Venv detected at {venv_path}')

    # The virtual environment is guaranteed to exist from this point on.
    #
    # The virtual environment does not really need to be activated, because the
    # commands that will be run will be the ones INSIDE the virtual environment.
    #
    # So, the only other thing that is MAYBE needed it setting the 'VIRTUAL_ENV'
    # environment variable so the launched programs can detect they are really
    # running inside a virtual environment. Apparently this is not essential,
    # but it is easy to do and will not do any harm.
    os.environ['VIRTUAL_ENV'] = str(venv_path.resolve())

    # Install needed packages in virtual environment.
    if not install_packages(venv_path / 'Scripts' / 'pip.exe'):
        return 1

    # Run the automated test suite.
    if not run_test_suite((venv_path / 'Scripts' / 'python.exe', program_name + '.py')):
        return 1

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
