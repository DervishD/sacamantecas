#! /usr/bin/env python3
"""Test suite for the logging system."""
from collections.abc import Callable
import logging
from typing import NamedTuple

import pytest

from conftest import LogPaths
from sacamantecas import Constants, error, logger, Messages, warning

ERROR_HEADER = Messages.ERROR_HEADER
ERROR_DETAILS_HEADING = Messages.ERROR_DETAILS_HEADING
ERROR_DETAILS_PREAMBLE = Messages.ERROR_DETAILS_PREAMBLE
ERROR_DETAILS_TAIL = Messages.ERROR_DETAILS_TAIL
PAD = ' ' * Constants.ERROR_PAYLOAD_INDENT
WARNING_HEADER = Messages.WARNING_HEADER
LEVELNAME_SEPARATOR = Constants.LOGGING_LEVELNAME_SEPARATOR


def test_logging_files_creation(log_paths: LogPaths) -> None:  # pylint: disable=unused-variable
    """Test that the logging files are created propertly."""
    assert not log_paths.log.is_file()
    assert not log_paths.debug.is_file()

    logger.config(logfile=log_paths.log, debugfile=log_paths.debug)

    logging.shutdown()

    assert log_paths.log.is_file()
    assert log_paths.debug.is_file()

# The 'expected' argument is a tuple containing four items:
#   - The expected logging file contents.
#   - The expected debugging file contents.
#   - The expected stdout output.
#   - The expected stderr output.
TEST_MESSAGE = 'Test message'
class Expected(NamedTuple):
    """."""
    log: str
    debug: str
    out: str
    err: str
@pytest.mark.parametrize(('logfunc', 'expected'), [
    (logger.debug, Expected(
        '',
        f'DEBUG   {LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        '',
        '',
    )),
    (logger.info, Expected(
        TEST_MESSAGE,
        f'INFO    {LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        f'{TEST_MESSAGE}\n',
        '',
    )),
    (logger.warning, Expected(
        TEST_MESSAGE,
        f'WARNING {LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        '',
        f'{TEST_MESSAGE}\n',
    )),
    (logger.error, Expected(
        TEST_MESSAGE,
        f'ERROR   {LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        '',
        f'{TEST_MESSAGE}\n',
    )),
    (warning, Expected(
        f'{WARNING_HEADER}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}',
        f'WARNING {LEVELNAME_SEPARATOR}{WARNING_HEADER}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}',
        '',
        f'{WARNING_HEADER}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}\n',
    )),
    (error, Expected(
        '\n'.join((ERROR_HEADER, f'{PAD}{TEST_MESSAGE}'.rstrip())),
        '\n'.join((
            '\n'.join(f'ERROR   {LEVELNAME_SEPARATOR}{line}'.rstrip() for line in ERROR_HEADER.split('\n')),
            '\n'.join(f'ERROR   {LEVELNAME_SEPARATOR}{PAD}{line}'.rstrip() for line in TEST_MESSAGE.split('\n')),
        )),
        '',
        '\n'.join((ERROR_HEADER, f'{PAD}{TEST_MESSAGE}', '')),
    )),
])
# pylint: disable-next=unused-variable
def test_logging_functions(
    log_paths: LogPaths,
    capsys: pytest.CaptureFixture[str],
    logfunc: Callable[[str], None],
    expected: Expected,
) -> None:
    """Test all logging functions."""
    logger.config(logfile=log_paths.log, debugfile=log_paths.debug)

    logfunc(TEST_MESSAGE)

    logging.shutdown()

    log_file_contents = log_paths.log.read_text(encoding='utf-8').splitlines()
    log_file_contents = [' '.join(line.split(' ')[1:]) for line in log_file_contents]
    log_file_contents = '\n'.join(log_file_contents)

    assert log_file_contents == expected.log

    debug_file_contents = log_paths.debug.read_text(encoding='utf-8').splitlines()
    debug_file_contents = [' '.join(line.split(' ')[1:]) for line in debug_file_contents]
    debug_file_contents = '\n'.join(debug_file_contents)

    assert debug_file_contents == expected.debug

    captured_output = capsys.readouterr()

    assert captured_output.out == expected.out
    assert captured_output.err == expected.err


# pylint: disable-next=unused-variable
def test_error_details(log_paths: LogPaths, capsys: pytest.CaptureFixture[str]) -> None:
    """Test handling of details by the error() function."""
    logger.config(logfile=log_paths.log, debugfile=log_paths.debug)

    details = 'Additional details in multiple lines.'.replace(' ', '\n')
    error(TEST_MESSAGE, details)

    logging.shutdown()

    expected = '\n'.join((
        ERROR_HEADER,
        '\n'.join(f'{PAD}{line}'.rstrip() for line in (
            TEST_MESSAGE.split('\n') +
            ERROR_DETAILS_HEADING.split('\n') +
            [f'{ERROR_DETAILS_PREAMBLE}{line}' for line in details.split('\n')] +
            ERROR_DETAILS_TAIL.split('\n')
        )),
        '',
    ))

    log_file_contents = log_paths.log.read_text(encoding='utf-8').split('\n')
    log_file_contents = [' '.join(line.split(' ')[1:]) for line in log_file_contents]
    log_file_contents = '\n'.join(log_file_contents)

    assert log_file_contents == expected

    debug_file_contents = log_paths.debug.read_text(encoding='utf-8').split('\n')
    debug_file_contents = [line.split(LEVELNAME_SEPARATOR, maxsplit=1)[1:] for line in debug_file_contents]
    debug_file_contents = [''.join(line) for line in debug_file_contents]
    debug_file_contents = '\n'.join(debug_file_contents)

    assert debug_file_contents == expected

    captured_output = capsys.readouterr()

    assert not captured_output.out
    assert captured_output.err == expected


@pytest.mark.parametrize('message', [
    'No whitespace.',
    '   Leading whitespace.',
    '\nLeading newline.',
    'Trailing newline.\n',
    '\bLeading and trailing newline.\n',
])
# pylint: disable-next=unused-variable
def test_whitespace_honoring(log_paths: LogPaths, capsys: pytest.CaptureFixture[str], message: str) -> None:
    """Test whether whitespace is honored where it should."""
    terminator = '<TERMINATOR>'

    logger.config(logfile=log_paths.log, debugfile=log_paths.debug)

    logging.StreamHandler.terminator, saved_terminator = terminator, logging.StreamHandler.terminator
    logger.info(message)
    logging.StreamHandler.terminator = saved_terminator

    logging.shutdown()

    captured_output = capsys.readouterr().out

    assert captured_output == message + terminator
