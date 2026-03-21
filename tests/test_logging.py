#! /usr/bin/env python3
"""Test suite for the logging system."""
import logging
from typing import NamedTuple, TYPE_CHECKING

import pytest

from sacamantecas import Constants, error, logger, Messages, warning
from tests.helpers import format_log_message, remove_logging_timestamps

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.helpers import LogPaths


def test_logging_paths_creation(log_paths: LogPaths) -> None:  # pylint: disable=unused-variable
    """Test that the logging paths are created propertly."""
    assert not log_paths.log.is_file()
    assert not log_paths.trace.is_file()

    logger.config(main_log_output=log_paths.log, full_log_output=log_paths.trace)

    logging.shutdown()

    assert log_paths.log.is_file()
    assert log_paths.trace.is_file()

# The 'expected' argument is a tuple containing four items:
#   - The expected main log file contents.
#   - The expected full log file contents.
#   - The expected stdout output.
#   - The expected stderr output.
class Expected(NamedTuple):
    """Expected output abstraction."""  # noqa: D204
    log: list[str]
    debug: list[str]
    out: list[str]
    err: list[str]
TEST_MESSAGE = 'Test message'
ERROR_PREFIX = Messages.ERROR_PREFIX
WARNING_PREFIX = Messages.WARNING_PREFIX
@pytest.mark.parametrize(('logfunc', 'expected'), [
    (logger.debug, Expected(
        [],
        format_log_message(TEST_MESSAGE, levelname='DEBUG'),
        [],
        [],
    )),
    (logger.info, Expected(
        format_log_message(TEST_MESSAGE),
        format_log_message(TEST_MESSAGE, levelname='INFO'),
        format_log_message(TEST_MESSAGE),
        [],
    )),
    (logger.warning, Expected(
        format_log_message(TEST_MESSAGE),
        format_log_message(TEST_MESSAGE, levelname='WARNING'),
        [],
        format_log_message(TEST_MESSAGE),
    )),
    (logger.error, Expected(
        format_log_message(TEST_MESSAGE),
        format_log_message(TEST_MESSAGE, levelname='ERROR'),
        [],
        format_log_message(TEST_MESSAGE),
    )),
    (warning, Expected(
        format_log_message(f'{WARNING_PREFIX}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}'),
        format_log_message(f'{WARNING_PREFIX}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}', levelname='WARNING'),
        [],
        format_log_message(f'{WARNING_PREFIX}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}'),
    )),
    (error, Expected(
        format_log_message(f'{ERROR_PREFIX}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}'),
        format_log_message(f'{ERROR_PREFIX}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}', levelname='ERROR'),
        [],
        format_log_message(f'{ERROR_PREFIX}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}'),
    )),
], ids=[
    'test_logger_debug',
    'test_logger_info',
    'test_logger_warning',
    'test_logger_error',
    'test_helper_warning',
    'test_helper_error',
])
# pylint: disable-next=unused-variable
def test_logging_functions(
    log_paths: LogPaths,
    capsys: pytest.CaptureFixture[str],
    logfunc: Callable[[str], None],
    expected: Expected,
) -> None:
    """Test all logging functions."""
    logger.config(main_log_output=log_paths.log, full_log_output=log_paths.trace)

    logfunc(TEST_MESSAGE)

    logging.shutdown()

    main_log_file_contents = remove_logging_timestamps(log_paths.log.read_text(encoding=Constants.UTF8).split('\n'))
    assert main_log_file_contents == [*expected.log, '']

    full_log_file_contents = remove_logging_timestamps(log_paths.trace.read_text(encoding=Constants.UTF8).split('\n'))
    assert full_log_file_contents == [*expected.debug, '']

    captured_output = capsys.readouterr()

    assert captured_output.out.split('\n') == [*expected.out, '']
    assert captured_output.err.split('\n') == [*expected.err, '']


@pytest.mark.parametrize('message', [
    'No whitespace.',
    '   Leading whitespace.',
    '\nLeading newline.',
    'Trailing newline.\n',
    '\bLeading and trailing newline.\n',
], ids=[
    'test_no_whitespace',
    'test_leading_whitespace',
    'test_leading_newline',
    'test_trailing_newline',
    'test_both_newlines',
])
# pylint: disable-next=unused-variable
def test_whitespace_honoring(log_paths: LogPaths, capsys: pytest.CaptureFixture[str], message: str) -> None:
    """Test whether whitespace is honored where it should."""
    terminator = '<TERMINATOR>'

    logger.config(main_log_output=log_paths.log, full_log_output=log_paths.trace)

    logging.StreamHandler.terminator, saved_terminator = terminator, logging.StreamHandler.terminator
    logger.info(message)
    logging.StreamHandler.terminator = saved_terminator

    logging.shutdown()

    captured_output = capsys.readouterr().out

    assert captured_output == message + terminator
