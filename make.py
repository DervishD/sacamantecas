"""
Build sacamantecas.

Builds sacamantecas executable for Win32 in a virtual environment.

Creates the virtual environment first if it does not exist, installs the needed
requirements inside and then runs the building process.
"""
import sys
import os
import re
import io
import venv
from pathlib import Path
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from utils import PROGRAM_ROOT, PROGRAM_PATH, PROGRAM_NAME, PROGRAM_LABEL, error, run, RunError


class TestBase():
    """Base class for all tests."""
    def __init__(self, testname, testitem):
        self.testname = testname
        self.testitem = testitem  # Item under test.
        self.basename = Path(testitem)  # For computing needed filenames.
        self.outfile = None  # File produced as output of the test.
        self.reffile = None  # Reference file to check if the output file is correct or not.
        self.reason = ()  # Reason of test failure, a tuple of lines.

    def run(self, command):
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
            run((*command, self.testitem))
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


def run_unit_tests(venv_path):
    """Run the automated unit test suite."""
    command = (venv_path / 'Scripts' / 'python.exe', PROGRAM_PATH)

    # Get into 'tests' directory.
    previous_working_directory = os.getcwd()
    os.chdir(Path('tests').resolve())

    some_test_failed = False
    for test in TESTS:
        print(f'Testing {test.testname} ', end='', flush=True)
        if test.run(command):
            print('✅')
        else:
            some_test_failed = True
            print('❌')
            sys.stdout.writelines((f'  *** {test.reason[0]}',) + tuple(f'  {line}' for line in test.reason[1:]))
    os.chdir(previous_working_directory)
    return some_test_failed


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
    else:
        print(f'Virtual environment active at «{venv_path}».\n')

    # The virtual environment is guaranteed to work from this point on.

    if len(sys.argv) >= 2:
        match sys.argv[1].lower():
            case ('v' | 'venv'):  # Create virtual environment (already done.)
                # If virtual environment creation and activation was the
                # requested operation, then everything is done, just pass.
                pass
            case ('e' | 'exe'):  # Build the frozen executable.
                return not build_frozen_executable(venv_path)
            case ('t' | 'test'):  # Run automated unit tests suite.
                return not run_unit_tests(venv_path)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
