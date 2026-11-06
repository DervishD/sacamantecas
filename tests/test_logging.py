"""Test suite for the logging system."""
import logging
from typing import NamedTuple, TYPE_CHECKING

import pytest

from sacamantecas import (
    Debug,
    error,
    ExitCodes,
    log_exception,
    logger,
    loggerize,
    lowercase_first_letter,
    Messages,
    Paths,
    warning,
)
from sacamantecas.about import DEPENDENCIES

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class LogPaths(NamedTuple):
    """Paths of the log files used by a test."""

    main: Path
    full: Path


class LogOutputs(NamedTuple):
    """Everything a `loggerize()` run produces, ready to be compared."""

    main_log: list[str]
    full_log: list[str]
    console_stdout: list[str]
    console_stderr: str


@pytest.fixture(name='configured_logger')
# pylint: disable-next=unused-variable
def configured_logger_fixture(capsys: pytest.CaptureFixture[str]) -> Iterator[pytest.CaptureFixture[str]]:
    """Configure the logger for a test and shut it down afterwards."""
    logger.config()
    yield capsys
    logging.shutdown()


@pytest.fixture(name='log_paths')
# pylint: disable-next=unused-variable
def log_paths_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> LogPaths:
    """Redirect the program log files to a temporary directory."""
    main_log_path = tmp_path / Paths.MAIN_LOG.name
    full_log_path = tmp_path / Paths.FULL_LOG.name
    monkeypatch.setattr(Paths, 'MAIN_LOG', main_log_path)
    monkeypatch.setattr(Paths, 'FULL_LOG', full_log_path)
    return LogPaths(main_log_path, full_log_path)


@pytest.fixture(name='log_outputs')
# pylint: disable-next=unused-variable
def log_outputs_fixture(capsys: pytest.CaptureFixture[str], log_paths: LogPaths) -> LogOutputs:
    """Run a decorated function and return what `loggerize()` logs."""
    def remove_timestamps(logfile: Path) -> list[str]:
        """Return the lines of *logfile* without the timestamp."""
        return [line.partition(' ')[2] for line in logfile.read_text(encoding='utf-8').splitlines()]

    def decorated_function() -> ExitCodes:
        """Do nothing, essentially."""
        return ExitCodes.SUCCESS

    loggerize(decorated_function)()
    captured = capsys.readouterr()
    return LogOutputs(
        main_log=remove_timestamps(log_paths.main),
        full_log=remove_timestamps(log_paths.full),
        console_stdout=captured.out.splitlines(),
        console_stderr=captured.err,
    )


# pylint: disable-next=unused-variable
def test_error_prefix() -> None:
    """Test the contents of Messages.ERROR_PREFIX constant."""
    assert Messages.ERROR_PREFIX == '\n*** Error: '


# pylint: disable-next=unused-variable
def test_warning_prefix() -> None:
    """Test the contents of Messages.WARNING_PREFIX constant."""
    assert Messages.WARNING_PREFIX == '* Aviso: '


# pylint: disable-next=unused-variable
def test_error_indentation(configured_logger: pytest.CaptureFixture[str]) -> None:
    """Test `error()` indentation handling."""
    logger.indent()
    logger.indent()
    error('Heading\nFirst detail line\nSecond detail line')

    captured = configured_logger.readouterr()
    assert not captured.out

    heading_line, *continuation_lines = [line for line in captured.err.splitlines() if line]

    # The heading starts at column 0, so the logger indentation was reset.
    assert heading_line == f'{Messages.ERROR_PREFIX.lstrip()}heading'

    # Continuation lines go one column past the first space of the heading line.
    continuation_indentation = ' ' * (heading_line.index(' ') + 1)
    assert continuation_lines == [
        f'{continuation_indentation}First detail line',
        f'{continuation_indentation}Second detail line',
    ]


@pytest.mark.usefixtures('configured_logger')
# pylint: disable-next=unused-variable
def test_error_loglevel(caplog: pytest.LogCaptureFixture) -> None:
    """Test `error()` logs a single record with `ERROR` level."""
    error('Some message')
    assert [record.levelno for record in caplog.records] == [logging.ERROR]
    assert caplog.records[0].getMessage() == f'{Messages.ERROR_PREFIX}some message'


@pytest.mark.usefixtures('configured_logger')
# pylint: disable-next=unused-variable
def test_warning_loglevel(caplog: pytest.LogCaptureFixture) -> None:
    """Test `warning()` logs a single record with `WARNING` level."""
    warning('Some message')
    assert [record.levelno for record in caplog.records] == [logging.WARNING]
    assert caplog.records[0].getMessage() == f'{Messages.WARNING_PREFIX}some message'


@pytest.mark.usefixtures('configured_logger')
# pylint: disable-next=unused-variable
def test_log_exception_level(caplog: pytest.LogCaptureFixture) -> None:
    """Test `log_exception()` logs everything with `DEBUG` level."""
    get_logged_messages(caplog, ValueError('some message'))
    assert [record.levelno for record in caplog.records] == [logging.DEBUG, logging.DEBUG]


LOWERCASE_DEFAULT_ERROR_MESSAGE = lowercase_first_letter(Messages.DEFAULT_ERROR_MESSAGE)
INDENTATION = ' ' * (Messages.ERROR_PREFIX.strip().index(' ') + 1)
@pytest.mark.parametrize(('message', 'expected'), [
    pytest.param('Normal message', 'normal message', id='normal'),
    pytest.param('Heading\nMsg\nDetail', f'heading\n{INDENTATION}Msg\n{INDENTATION}Detail', id='multiline'),
    pytest.param('Heading\n\nDetail', f'heading\n\n{INDENTATION}Detail', id='holed_multiline'),
    pytest.param('Heading\n\n', 'heading', id='multiline_empty_tail'),
    pytest.param('', LOWERCASE_DEFAULT_ERROR_MESSAGE, id='empty'),
    pytest.param('  ', LOWERCASE_DEFAULT_ERROR_MESSAGE, id='spaces'),
    pytest.param('\t\t', LOWERCASE_DEFAULT_ERROR_MESSAGE, id='tabs'),
    pytest.param('\n\n', LOWERCASE_DEFAULT_ERROR_MESSAGE, id='newlines'),
    pytest.param(' \t\n \t\n', LOWERCASE_DEFAULT_ERROR_MESSAGE, id='whitespace_mix'),
])
# pylint: disable-next=unused-variable
def test_error_helper(configured_logger: pytest.CaptureFixture[str], message: str, expected: str) -> None:
    """Test `error()` helper."""
    error(message)
    captured = configured_logger.readouterr()
    assert not captured.out
    assert captured.err == f'{Messages.ERROR_PREFIX}{expected}\n'

@pytest.mark.parametrize(('message', 'expected'), [
    pytest.param('\nEmpty heading', f'\n{INDENTATION}Empty heading', id='empty_heading'),
    pytest.param('  \nWhitespace heading', f'\n{INDENTATION}Whitespace heading', id='whitespace_heading'),
])
# pylint: disable-next=unused-variable
def test_error_empty_heading(configured_logger: pytest.CaptureFixture[str], message: str, expected: str) -> None:
    """Test `error()` helper when an empty heading is used.

    Since the logger strips trailing whitespace from each line, with an
    empty heading this means the prefix loses its final space!
    """
    error(message)
    captured = configured_logger.readouterr()
    assert not captured.out
    assert captured.err == f'{Messages.ERROR_PREFIX.rstrip()}{expected}\n'


LOWERCASE_DEFAULT_WARNING_MESSAGE = lowercase_first_letter(Messages.DEFAULT_WARNING_MESSAGE)
@pytest.mark.parametrize(('message', 'expected'), [
    pytest.param('Normal message', 'normal message', id='normal'),
    pytest.param('', LOWERCASE_DEFAULT_WARNING_MESSAGE, id='empty'),
    pytest.param('  ', LOWERCASE_DEFAULT_WARNING_MESSAGE, id='spaces'),
    pytest.param('\t\t', LOWERCASE_DEFAULT_WARNING_MESSAGE, id='tabs'),
    pytest.param('\n\n', LOWERCASE_DEFAULT_WARNING_MESSAGE, id='newlines'),
    pytest.param(' \t\n \t\n', LOWERCASE_DEFAULT_WARNING_MESSAGE, id='whitespace_mix'),
    pytest.param('   Leading whitespace', '   leading whitespace', id='leading_whitespace'),
    pytest.param('Multiline message\nAnother line\nEnd.', 'multiline message\nAnother line\nEnd.', id='multiline'),
])
# pylint: disable-next=unused-variable
def test_warning_helper(configured_logger: pytest.CaptureFixture[str], message: str, expected: str) -> None:
    """Test `warning()` helper."""
    warning(message)
    captured = configured_logger.readouterr()
    assert not captured.out
    assert captured.err == f'{Messages.WARNING_PREFIX}{expected}\n'


class CustomError(Exception):
    """Exception subclass for testing the reported type name."""


def get_logged_messages(caplog: pytest.LogCaptureFixture, exception: Exception) -> list[str]:
    """Call `log_exception()` with *exception* and return the logged messages."""
    caplog.set_level(logging.DEBUG)
    caplog.clear()
    log_exception(exception)
    return [record.getMessage().rstrip() for record in caplog.records]


@pytest.mark.usefixtures('configured_logger')
@pytest.mark.parametrize(('exception', 'type_name'), [
    pytest.param(ValueError('some message'), 'ValueError', id='standard'),
    pytest.param(CustomError('some message'), 'CustomError', id='subclass'),
    pytest.param(KeyError(), 'KeyError', id='no_arguments'),
])
# pylint: disable-next=unused-variable
def test_log_exception_without_context(caplog: pytest.LogCaptureFixture, exception: Exception, type_name: str) -> None:
    """Test `log_exception()` with an exception which has no context."""
    assert get_logged_messages(caplog, exception) == [
        Debug.EXCEPTION_LOG.format(type_name),
        Debug.EXCEPTION_LOG_NO_CONTEXT,
    ]


@pytest.mark.usefixtures('configured_logger')
@pytest.mark.parametrize(('context', 'exc_name', 'representation', 'text'), [
    pytest.param(ValueError('message'), 'ValueError', "ValueError('message')", 'message', id='standard'),
    pytest.param(ValueError(), 'ValueError', 'ValueError()', '', id='empty_text'),
    pytest.param(CustomError('message'), 'CustomError', "CustomError('message')", 'message', id='subclass'),
])
# pylint: disable-next=unused-variable
def test_log_exception_with_context(
    caplog: pytest.LogCaptureFixture,
    context: Exception,
    exc_name: str,
    representation: str,
    text: str,
) -> None:
    """Test `log_exception()` with an exception which has a context."""
    try:
        raise context
    except type(context):
        try:
            raise KeyError('msg')  # ruff: ignore[TRY301,EM101]  # pylint: disable=raise-missing-from
        except KeyError as exc:
            assert get_logged_messages(caplog, exc) == [  # ruff: ignore[PT017]
                Debug.EXCEPTION_LOG.format('KeyError'),
                Debug.EXCEPTION_LOG_CONTEXT.format(exc_name, representation, text).rstrip(),
            ]


# pylint: disable-next=unused-variable
def test_loggerize_creates_logfiles(log_paths: LogPaths) -> None:
    """Test `loggerize()` creates both log files."""
    def decorated_function() -> ExitCodes:
        """Do nothing, successfully."""
        return ExitCodes.SUCCESS

    assert not log_paths.main.exists()
    assert not log_paths.full.exists()
    loggerize(decorated_function)()
    assert log_paths.main.is_file()
    assert log_paths.full.is_file()


@pytest.mark.usefixtures('log_paths')
@pytest.mark.parametrize('status', [pytest.param(member, id=member.name) for member in ExitCodes])
# pylint: disable-next=unused-variable
def test_loggerize_propagates_exitcode(status: ExitCodes) -> None:
    """Test `loggerize()` propagates function exitcode."""
    def decorated_function() -> ExitCodes:
        """Return the status under test."""
        return status

    assert loggerize(decorated_function)() is status


@pytest.mark.usefixtures('log_paths')
@pytest.mark.parametrize('arguments', [
    pytest.param((), id='no_arguments'),
    pytest.param(('first',), id='one_argument'),
    pytest.param(('first', 'second', 'third'), id='several_arguments'),
])
# pylint: disable-next=unused-variable
def test_loggerize_propagates_arguments(arguments: tuple[str, ...]) -> None:
    """Test `loggerize()` propagates arguments, in order."""
    received_arguments: tuple[str, ...] | None = None

    def decorated_function(*args: str) -> ExitCodes:
        """Record the received arguments."""
        nonlocal received_arguments
        received_arguments = args
        return ExitCodes.SUCCESS

    loggerize(decorated_function)(*arguments)
    assert received_arguments == arguments



# pylint: disable-next=unused-variable
def test_loggerize_main_log_contents(log_outputs: LogOutputs) -> None:
    """Test the main log has the proper contents by default."""
    assert log_outputs.main_log == [
        Messages.PROGRAM_BANNER,
        '',
        Messages.PROCESS_DONE,
    ]


# pylint: disable-next=unused-variable
def test_loggerize_full_log_contents(log_outputs: LogOutputs) -> None:
    """Test the full log has everything, including the debug messages."""
    dependency_lines = [
        f'DEBUG    | loggerize_wrapper() {Debug.DEPENDENCY_BANNER.format(package.replace('==', ' v'))}'
        for package in DEPENDENCIES
    ]
    assert log_outputs.full_log == [
        f'DEBUG    | loggerize_wrapper() {Debug.DEBUGGING_INIT}',
        f'INFO     | loggerize_wrapper() {Messages.PROGRAM_BANNER}',
        *dependency_lines,
        f'DEBUG    | loggerize_wrapper() {Debug.USER_AGENT_LABEL}',
        'INFO     | loggerize_wrapper()',
        f'INFO     | loggerize_wrapper() {Messages.PROCESS_DONE}',
        f'DEBUG    | loggerize_wrapper() {Debug.DEBUGGING_DONE}',
    ]


# pylint: disable-next=unused-variable
def test_loggerize_console_matches_main_log(log_outputs: LogOutputs) -> None:
    """Test the console shows the same lines as the main log, only through `stdout`."""
    assert not log_outputs.console_stderr
    assert log_outputs.console_stdout == log_outputs.main_log
