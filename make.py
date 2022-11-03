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
import inspect
from types import SimpleNamespace
from subprocess import run, CalledProcessError
from pathlib import Path
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED


CONFIG = SimpleNamespace()  # Global configuration object.


# Reconfigure standard output streams so they use UTF-8 encoding even if they
# are redirected to a file when running the program from a shell.
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def error(message):
    """Pretty-print 'message' to sys.stderr."""
    lines = message.splitlines()
    lines[0] = f'*** Error {lines[0]}\n'
    lines[1:] = [f'    {line}\n' for line in lines[1:]]
    sys.stderr.writelines(lines)
    if message.endswith('\n'):
        sys.stderr.write('\n')
    sys.stderr.flush()


def run_command(command):
    """Helper for running commands and capturing the output."""
    try:
        return run(command, check=True, capture_output=True, encoding='utf-8', text=True)
    except FileNotFoundError as exc:
        raise CalledProcessError(0, command, None, f"Command '{command[0]}' not found.\n") from exc


def get_venv_path():
    """
    Get the virtual environment path for this project.
    IT HAS TO BE THE FIRST LINE IN THE 'gitignore' FILE.
    IT HAS TO CONTAIN THE STRING 'venv' SOMEWHERE.
    """
    venv_path = None
    message = None
    try:
        with open(CONFIG.root_path / '.gitignore', encoding='utf-8') as gitignore:
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
            # The virtual environment path is relative to the 'root_path'.
            venv_path = CONFIG.root_path / venv_path
            if venv_path.exists() and not venv_path.is_dir():
                message = 'Virtual environment path exists but it is not a directory'

    if message:
        error(f'finding virtual environment path.\n{message}.')
        return None

    return venv_path


def process_argv():
    """
    Process command line arguments.

    Check that there is just ONE target provided and that is is valid.

    Return the target, a tuple containing the canonical name and the handler.
    """
    error_message = None
    if len(sys.argv) > 2:  # Too many targets provided.
        error_message = f'too many targets provided {*sys.argv[1:],}'

    if len(sys.argv) < 2:  # No target provided.
        error_message = 'no target provided'

    if len(sys.argv) == 2:  # Single target provided, check if it is valid.
        target = sys.argv[1]
        found_targets = []
        for possible_target in CONFIG.targets:
            if possible_target[0].startswith(target):
                found_targets.append(possible_target)
        if not found_targets:
            error_message = f"target '{target}' does not exist"
        if len(found_targets) > 1:
            error_message = f"target '{target}' is ambiguous, can be {*found_targets,}"
        target = found_targets[0]

    if error_message:  # Some problem with command line, signal the error and show usage.
        error(f'in command line, {error_message}.\n')
        print_usage()
        return None

    # Single target provided, return it.
    return target


def print_usage():
    """Print the usage instructions to stdout."""
    valid_targets = [target[0] for target in CONFIG.targets]
    print(f'Usage: python {Path(__file__).name} ({" | ".join(valid_targets)})\n')
    maxlen = len(max(valid_targets, key=len)) + 2
    for target in CONFIG.targets:
        print(f'  {target[0]:{maxlen}} {target[1].__doc__}')
    print()
    print('Target names can be abbreviated.')


def target_help():  # pylint: disable=unused-variable
    """Show this help."""
    # Cannot be simpler than that…
    print_usage()


def target_venv():
    """Create virtual environment."""
    # First, check if virtual environment is already active.
    #
    # This is done by checking if the 'VIRTUAL_ENV' environment variable is set.
    # By itself, this is good enough proof that the virtual environment has been
    # activated, but it does NOT check if it has been properly set up, like if
    # all needed packages have been correctly installed or not.
    if 'VIRTUAL_ENV' in os.environ:
        print(f"Virtual environment already active at '{CONFIG.venv_path}'.")
        return True

    print(f"Creating virtual environment at '{CONFIG.venv_path}'.")
    if not CONFIG.venv_path.exists():
        with open(os.devnull, 'w', encoding='utf-8') as devnull:
            # Save a reference for the original stdout so it can be restored later.
            duplicated_stdout_fileno = os.dup(1)

            # Flush buffers, because os.dup2() is not aware of them.
            sys.stdout.flush()
            # Point file descriptor 1 to devnull to silent general output.
            os.dup2(devnull.fileno(), 1)

            # The normal output for the calls below is suppressed.
            # Error output is not.
            venv.create(CONFIG.venv_path, with_pip=True, upgrade_deps=True)

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
    os.environ['VIRTUAL_ENV'] = str(CONFIG.venv_path.resolve())

    try:
        run_command((CONFIG.venv_path / 'Scripts' / 'pip.exe', 'install', '-r', CONFIG.root_path / 'requirements.txt'))
    except CalledProcessError as exc:
        error(f'creating virtual environment.\npip: {exc.stderr}.')
        return False

    print('Virtual environment created successfully.')
    return True


def target_executable():  # pylint: disable=unused-variable
    """Build and bundle frozen executable."""
    print('Building frozen executable.')
    pyinstaller_path = CONFIG.venv_path / 'Scripts' / 'pyinstaller.exe'
    build_path = CONFIG.venv_path / 'build'
    dist_path = CONFIG.venv_path / 'dist'
    executable = dist_path / CONFIG.program_path.with_suffix('.exe').name
    bundle_path = CONFIG.root_path / f'{CONFIG.program_path.stem}_{CONFIG.program_version}.zip'

    if executable.exists():
        # Remove executable produced by previous runs.
        os.remove(executable)

    cmd = [pyinstaller_path]
    cmd.append('--log-level=WARN')
    cmd.extend([f'--workpath={build_path}', f'--specpath={build_path}', f'--distpath={dist_path}'])
    cmd.extend(['--onefile', CONFIG.program_path])
    try:
        run_command(cmd)
    except CalledProcessError as exc:
        error(f'creating executable.\n{exc.stderr}.')
        return False

    # Executable was created, so create ZIP bundle.
    print(f"Creating ZIP bundle '{bundle_path}'.")
    with ZipFile(bundle_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        inifile = CONFIG.program_path.with_suffix('.ini')
        bundle.write(executable, executable.name)
        bundle.write(inifile, inifile.name)
    print('Frozen executable built successfully.')
    return True


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

        Return True if the test passed, False if it failed.

        If a test fails, details are in 'self.reason', a tuple of lines.
        """
        # Build the needed filenames.
        self.outfile = self.basename.with_stem(f'{self.basename.stem}_out')
        self.reffile = self.basename.with_stem(f'{self.basename.stem}_ref')

        # Run the script
        try:
            run_command((*command, self.testitem))
        except CalledProcessError as exc:
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


def target_test():  # pylint: disable=unused-variable
    """Run the automated unit test suite."""
    print('Running unit tests.')
    tests = (
        # pylint: disable-next=line-too-long
        TestUri('single file URI', 'file:///./html/http___ceres_mcu_es_pages_Main_idt_134248_inventary_DE2016_1_24_table_FMUS_museum_MOM.html'),  # noqa for pycodestyle.
        TestTxt('text input with file URIs', 'local.txt'),
        TestXls('xlsx input with file URIs', 'local.xlsx'),
        # # pylint: disable-next=line-too-long
        TestUri('single http URI (potentially slow)', 'http://ceres.mcu.es/pages/Main?idt=134248&inventary=DE2016/1/24&table=FMUS&museum=MOM'),  # noqa for pycodestyle.
        TestTxt('text input with http URIs (potentially slow)', 'network.txt'),
        TestXls('xlsx input with http URIs (potentially slow)', 'network.xlsx'),
    )
    command = (CONFIG.venv_path / 'Scripts' / 'python.exe', CONFIG.program_path)

    # Get into 'tests' directory.
    previous_working_directory = os.getcwd()
    os.chdir(Path('tests').resolve())

    some_test_failed = False
    for test in tests:
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
    # Set up global configuration.
    CONFIG.root_path = Path(__file__).parent  # Full path of root directory for finding and accessing files.
    CONFIG.program_path = Path(__file__).with_stem(Path(__file__).parent.stem)
    CONFIG.venv_path = get_venv_path()
    if CONFIG.venv_path is None:  # Exit early if venv_path could not be determined.
        return 1

    # Get the program version directly from the program's source file.
    with open(CONFIG.program_path, encoding='utf-8') as program:
        for line in program.readlines():
            if line.startswith('__version__'):
                CONFIG.program_version = line.strip().split(' = ')[1].strip("'")
                break

    # Get list of targets.
    CONFIG.targets = inspect.getmembers(sys.modules['__main__'], inspect.isfunction)
    CONFIG.targets = [(target, inspect.getsourcelines(target[1])[1]) for target in CONFIG.targets]
    CONFIG.targets = [target[0] for target in sorted(CONFIG.targets, key=lambda target: target[1])]
    CONFIG.targets = filter(lambda t: t[0].startswith('target_'), CONFIG.targets)
    CONFIG.targets = map(lambda t: (t[0].removeprefix('target_'), t[1]), CONFIG.targets)
    CONFIG.targets = list(CONFIG.targets)

    # Get the provided target, if any.
    target = process_argv()
    if target is None:  # No valid target, exit.
        return 1

    print(f'Making {CONFIG.program_path.stem} {CONFIG.program_version}\n')

    # No matter the target, the first thing to do is creating (if it does not
    # exist) or activate (if it exists) the virtual environment. This is done by
    # ALWAYS running the 'venv' target.
    if not target_venv():
        return 1

    if target[0] == 'venv':
        # The only operation required by the user was creating/activating the
        # virtual environment, so everything is done.
        return 0

    # The virtual environment is guaranteed to work from this point on.
    # Run the required target.
    target[1]()

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
