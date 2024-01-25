#! /usr/bin/env python3
"""Test suite for the logging system."""
from collections import namedtuple
import logging

import pytest

from sacamantecas import Config, error, Messages, setup_logging, warning


ERROR_HEADER = Messages.ERROR_HEADER
ERROR_DETAILS_HEADING = Messages.ERROR_DETAILS_HEADING
ERROR_DETAILS_TAIL = Messages.ERROR_DETAILS_TAIL
PAD = ' ' * Config.ERROR_PAYLOAD_INDENT
WARNING_HEADER = Messages.WARNING_HEADER
LOGGING_LEVELNAME_SEPARATOR = Config.LOGGING_LEVELNAME_SEPARATOR


def test_logging_files_creation(log_paths):  # pylint: disable=unused-variable
    """Test that the logging files are created propertly."""
    assert not log_paths.log.is_file()
    assert not log_paths.debug.is_file()

    setup_logging(log_paths.log, log_paths.debug)
    logging.shutdown()

    assert log_paths.log.is_file()
    assert log_paths.debug.is_file()

# The 'expected' argument is a tuple containing four items:
#   - The expected logging file contents.
#   - The expected debugging file contents.
#   - The expected stdout output.
#   - The expected stderr output.
TEST_MESSAGE = 'Test message'
Expected = namedtuple('Expected', ['log', 'debug', 'out','err'])
@pytest.mark.parametrize('logfunc, expected', [
    (logging.debug, Expected(
        '',
        f'DEBUG   {LOGGING_LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        '',
        ''
    )),
    (logging.info, Expected(
        TEST_MESSAGE,
        f'INFO    {LOGGING_LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        f'{TEST_MESSAGE}\n',
        ''
    )),
    (logging.warning, Expected(
        TEST_MESSAGE,
        f'WARNING {LOGGING_LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        '',
        f'{TEST_MESSAGE}\n'
    )),
    (logging.error, Expected(
        TEST_MESSAGE,
        f'ERROR   {LOGGING_LEVELNAME_SEPARATOR}{TEST_MESSAGE}',
        '',
        f'{TEST_MESSAGE}\n'
    )),
    (warning, Expected(
        f'{WARNING_HEADER}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}',
        f'WARNING {LOGGING_LEVELNAME_SEPARATOR}{WARNING_HEADER}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}',
        '',
        f'{WARNING_HEADER}{TEST_MESSAGE[0].lower()}{TEST_MESSAGE[1:]}\n'
    )),
    (error, Expected(
        '\n'.join((ERROR_HEADER, f'{PAD}{TEST_MESSAGE}')),
        '\n'.join((
            '\n'.join(f'ERROR   {LOGGING_LEVELNAME_SEPARATOR}{line}' for line in ERROR_HEADER.split('\n')),
            '\n'.join(f'ERROR   {LOGGING_LEVELNAME_SEPARATOR}{PAD}{line}' for line in TEST_MESSAGE.split('\n'))
        )),
        '',
        '\n'.join((ERROR_HEADER, f'{PAD}{TEST_MESSAGE}', '')),
    ))
])
def test_logging_functions(log_paths, capsys, logfunc, expected):  # pylint: disable=unused-variable
    """Test all logging functions."""
    setup_logging(log_paths.log, log_paths.debug)
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


def test_error_details(log_paths, capsys):  # pylint: disable=unused-variable
    """Test handling of details by the error() function."""
    details = 'Additional details in multiple lines.'.replace(' ', '\n')
    setup_logging(log_paths.log, log_paths.debug)
    error(TEST_MESSAGE, details)
    logging.shutdown()

    expected = '\n'.join((
        ERROR_HEADER,
        '\n'.join(f'{PAD}{line}' for line in (
            TEST_MESSAGE.split('\n') +
            ERROR_DETAILS_HEADING.split('\n') +
            list(f'{LOGGING_LEVELNAME_SEPARATOR}{line}' for line in details.split('\n')) +
            ERROR_DETAILS_TAIL.split('\n')
        )),
        ''
    ))

    log_file_contents = log_paths.log.read_text(encoding='utf-8').split('\n')
    log_file_contents = [' '.join(line.split(' ')[1:]) for line in log_file_contents]
    log_file_contents = '\n'.join(log_file_contents)
    assert log_file_contents == expected

    debug_file_contents = log_paths.debug.read_text(encoding='utf-8').split('\n')
    debug_file_contents = [line.split(LOGGING_LEVELNAME_SEPARATOR, maxsplit=1)[1:] for line in debug_file_contents]
    debug_file_contents = [''.join(line) for line in debug_file_contents]
    debug_file_contents = '\n'.join(debug_file_contents)
    assert debug_file_contents == expected

    captured_output = capsys.readouterr()
    assert not captured_output.out
    assert captured_output.err == expected


@pytest.mark.parametrize('message', [
    'No whitespace.',
    '   Leading whitespace.',
    'Trailing whitespace.   ',
    '   Leading and trailing whitespace.   ',
    '\nLeading newline.',
    'Trailing newline.\n',
    '\bLeading and trailing newline.\n',
])
def test_whitespace_honoring(log_paths, capsys, message):  # pylint: disable=unused-variable
    "Test whether leading and trailing whitespace are honored."
    terminator = '<TERMINATOR>'
    setup_logging(log_paths.log, log_paths.debug)
    logging.StreamHandler.terminator, saved_terminator = terminator, logging.StreamHandler.terminator
    logging.info(message)
    logging.StreamHandler.terminator = saved_terminator
    logging.shutdown()

    captured_output = capsys.readouterr().out
    assert captured_output == message + terminator
