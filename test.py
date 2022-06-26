"""
Test sacamantecas.

Runs sacamantecas test suite.
"""
import sys
import os
import io
import re
from difflib import unified_diff
from pathlib import Path
from zipfile import ZipFile
from mkvenv import get_venv_path, is_venv_active
from utils import PROGRAM_LABEL, SCRIPT_NAME, RunError, error, run


# Command for running the script for the tests.
COMMAND = (get_venv_path().resolve() / 'Scripts' / 'python.exe', Path(SCRIPT_NAME).resolve())
# Directory containing the tests.
TESTS_PATH = Path('tests').resolve()


class TestBase():
    """Base class for all tests."""
    def __init__(self, testname, testitem):
        self.testname = testname
        self.testitem = testitem  # Item under test.
        self.basename = Path(testitem)  # For computing needed filenames.
        self.outfile = None  # File produced as output of the test.
        self.reffile = None  # Reference file to check if the output file is correct or not.
        self.reason = ()  # Reason of test failure, a tuple of lines.

    def run(self):
        """
        Run the test.

        Returns True if the test passed, False if it failed.

        If a test fails, details are in 'self.reason', a tuple of lines.
        """
        # Build the needed filenames.
        self.outfile = self.basename.with_stem(f'{self.basename.stem}_out')
        self.reffile = self.basename.with_stem(f'{self.basename.stem}_ref')

        # Run the script
        try:
            run((*COMMAND, self.testitem))
        except RunError as exc:
            self.reason = exc.stderr.lstrip().splitlines(keepends=True)
            return False

        # Load the filename's contents to be compared.
        # Usually redefined in derived classes.
        olines, rlines = self.readfiles()

        # Get diff lines and truncate them if needed.
        diff = unified_diff(olines, rlines, 'test output', 'reference', n=1)
        diff = [line.rstrip()[:99] + '…\n' if len(line.rstrip()) > 100 else line for line in diff]
        if diff:
            diff.insert(0, 'Differences found:\n')
            self.reason = diff
            return False

        # Files are identical so remove output file and return success.
        self.outfile.unlink(missing_ok=True)
        return True

    def readfiles(self):
        """Load output and reference files contents into instance attributes."""
        with open(self.outfile, encoding='utf-8') as ofile:
            olines = ofile.readlines()
        with open(self.reffile, encoding='utf-8') as rfile:
            rlines = rfile.readlines()
        return (olines, rlines)


class TestUri(TestBase):
    """Class for single URI tests."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.basename = Path(re.sub(r'\W', '_', self.testitem, re.ASCII)).with_suffix('.txt')


class TestTxt(TestBase):
    """Class for text input file tests."""


class TestXls(TestBase):
    """Class for xlsx input file tests."""
    def readfiles(self):
        # Excel files are really Zip files and for comparing the data inside
        # only the 'xl/worksheets/sheet1.xml' file has to be read.
        #
        # Since usually the XML file will consist in a single line, some crude
        # formatting is done so the differences shown make a bit of sense in
        # order to check the output Excel file later. The line is broken at XML
        # tags and newline characters are added.
        rep = {r'<': '\n<', r'>': '>\n'}
        with ZipFile(self.outfile, 'r') as ofile:
            with ofile.open('xl/worksheets/sheet1.xml') as sheet:
                olines = io.TextIOWrapper(sheet, encoding='utf-8').read()
                olines = re.sub(r'|'.join(rep.keys()), lambda m: rep[m.group(0)], olines).splitlines(keepends=True)
        with ZipFile(self.reffile, 'r') as rfile:
            with rfile.open('xl/worksheets/sheet1.xml') as sheet:
                rlines = io.TextIOWrapper(sheet, encoding='utf-8').read()
                rlines = re.sub(r'|'.join(rep.keys()), lambda m: rep[m.group(0)], rlines).splitlines(keepends=True)
        return (olines, rlines)


TESTS = (
    # pylint: disable-next=line-too-long
    TestUri('single file URI', 'file:///./html/http___ceres_mcu_es_pages_Main_idt_134248_inventary_DE2016_1_24_table_FMUS_museum_MOM.html'),  # noqa for pycodestyle.
    TestTxt('text input with file URIs', 'local.txt'),
    TestXls('xlsx input with file URIs', 'local.xlsx'),
    # # pylint: disable-next=line-too-long
    TestUri('single http URI (potentially slow)', 'http://ceres.mcu.es/pages/Main?idt=134248&inventary=DE2016/1/24&table=FMUS&museum=MOM'),  # noqa for pycodestyle.
    TestTxt('text input with http URIs (potentially slow)', 'network.txt'),
    TestXls('xlsx input with http URIs (potentially slow)', 'network.xlsx'),
)


def main():
    """."""
    print(f'Running tests for {PROGRAM_LABEL}')

    if not is_venv_active():
        error('detecting virtual environment.\nVirtual environment is not active.')
        return 1

    os.chdir(TESTS_PATH)

    some_test_failed = False
    try:
        for test in TESTS:
            print(f'Testing {test.testname} ', end='', flush=True)
            if test.run():
                print('✅')
            else:
                some_test_failed = True
                print('❌')
                sys.stdout.writelines((f'\n*** {test.reason[0]}',) + tuple(f'  {line}' for line in test.reason[1:]))
    except KeyboardInterrupt:
        pass
    return some_test_failed


if __name__ == '__main__':
    sys.exit(main())
