#! /usr/bin/env python3
"""Test suite for setup_logging()."""
from collections import namedtuple
import logging

import pytest

from sacamantecas import error, Messages, setup_logging, warning


ERROR_HEADER = Messages.ERROR_HEADER
WARNING_HEADER = Messages.WARNING_HEADER


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
        f'DEBUG   | {TEST_MESSAGE}',
        '',
        ''
    )),
    (logging.info, Expected(
        TEST_MESSAGE,
        f'INFO    | {TEST_MESSAGE}',
        f'{TEST_MESSAGE}\n',
        ''
    )),
    (logging.warning, Expected(
        TEST_MESSAGE,
        f'WARNING | {TEST_MESSAGE}',
        '',
        f'{TEST_MESSAGE}\n'
    )),
    (logging.error, Expected(
        TEST_MESSAGE,
        f'ERROR   | {TEST_MESSAGE}',
        '',
        f'{TEST_MESSAGE}\n'
    )),
    (warning, Expected(
        f'{WARNING_HEADER}{TEST_MESSAGE}',
        f'WARNING | {WARNING_HEADER}{TEST_MESSAGE}',
        '',
        f'{WARNING_HEADER}{TEST_MESSAGE}\n'
    )),
    (error, Expected(
        f'{ERROR_HEADER}    {TEST_MESSAGE}',
        '\n'.join((
            'ERROR   |',
            f'ERROR   | {ERROR_HEADER.strip()}',
            '\n'.join(f'ERROR   |{"     " if line else ""}{line}' for line in TEST_MESSAGE.splitlines())
        )),
        '',
        f'{ERROR_HEADER}    {TEST_MESSAGE}\n'
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
