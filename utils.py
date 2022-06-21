"""
General utilities for helper scripts.
"""
import sys
import subprocess


def error(message):  # pylint: disable=unused-variable
    """Pretty-print 'message' to sys.stderr."""
    message = message.splitlines()
    message[0] = f'*** Error {message[0]}\n'
    message[1:] = [f'    {line}\n' for line in message[1:]]
    sys.stderr.writelines(message)
    sys.stderr.flush()


def run(command):  # pylint: disable=unused-variable
    """Helper for running commands and capturing the output."""
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        args = {
            'returncode': 0,
            'cmd': command,
            'output': None,
            'stderr': f'File not found {command[0]}\n',
        }
        raise subprocess.CalledProcessError(**args) from exc
    return result
