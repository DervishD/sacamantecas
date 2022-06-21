"""
Test sacamantecas.

Runs sacamantecas test suite.
"""
import sys
import io
import re
from difflib import unified_diff
from pathlib import Path
from zipfile import ZipFile
from mkvenv import get_venv_path, is_venv_active
from utils import PROGRAM_LABEL, SCRIPT_NAME, error, run


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


def main():
    """."""
    print(f'Running tests for {PROGRAM_LABEL}')

    if not is_venv_active():
        error('detecting virtual environment.\nVirtual environment is not active.')
        return 1

    run_test_suite((get_venv_path() / 'Scripts' / 'python.exe', SCRIPT_NAME))

    return 0


if __name__ == '__main__':
    sys.exit(main())
