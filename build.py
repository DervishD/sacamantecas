"""
Build sacamantecas.

Builds sacamantecas executable for Win32 in a virtual environment.

Creates the virtual environment first if it does not exist, installs the needed
requirements inside and then runs the building process.
"""
import io
import sys
import os
import re
from pathlib import Path
from difflib import unified_diff
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
    result = run((*command, testitem))

    # If testitem is an URI, the test output must be written to the output file,
    # since by default is just dumped to console.
    if not str(testitem).endswith(('.txt', '.xlsx')):
        with open(outfile, 'w', encoding='utf-8') as dumpfile:
            dumpfile.write(result.stdout)

    # Compare the resulting files.
    # If any of them does not exist, consider the test failed.
    try:
        if str(outfile).endswith('txt'):
            # For text files just read them into memory.
            with open(outfile, encoding='utf-8') as ofile:
                outlines = ofile.readlines()
            with open(reffile, encoding='utf-8') as rfile:
                reflines = rfile.readlines()
        else:
            # For Excel files, treat them as Zip files and compare the data
            # inside. To wit, 'xl/worksheets/sheet1.xml' file.
            with ZipFile(outfile, 'r') as ofile:
                with ofile.open('xl/worksheets/sheet1.xml') as sheet:
                    outlines = io.TextIOWrapper(sheet, encoding='utf-8').readlines()
            with ZipFile(reffile, 'r') as rfile:
                with rfile.open('xl/worksheets/sheet1.xml') as sheet:
                    reflines = io.TextIOWrapper(sheet, encoding='utf-8').readlines()
    except FileNotFoundError as exc:
        return (f'*** File {exc.filename} does not exist.\n', )

    # Get diff lines and truncate them if needed.
    diff = unified_diff(outlines, reflines, str(outfile), str(reffile), n=1)
    diff = [line.rstrip()[:69] + '…\n' if len(line.rstrip()) > 70 else line for line in diff]
    if diff:
        diff.insert(0, '*** Differences found:\n')
        return diff
    return ()


def run_test_suite(command):
    """Run the automated test suite."""
    tests = (
        'file:///./tests/http___ceres_mcu_es_pages_Main_idt_134248_inventary_DE2016_1_24_table_FMUS_museum_MOM.html',
        'test_local.txt',
        'test_local.xlsx',
        'http://ceres.mcu.es/pages/Main?idt=134248&inventary=DE2016/1/24&table=FMUS&museum=MOM',
        'test_network.txt',
        'test_network.xlsx',
    )

    for testitem in tests:
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
