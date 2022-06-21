"""
General utilities for helper scripts.
"""
import sys
import subprocess


class RunError(BaseException):
    """Exception for errors happening when running commands."""
    def __init__(self, returncode, cmd, stdout, stderr, *args, **kwargs):
        """."""
        super().__init__(*args, **kwargs)
        self.returncode = returncode
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr


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
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RunError(0, command, None, f'File not found {command[0]}\n') from exc
    except subprocess.CalledProcessError as exc:
        raise RunError(exc.returncode, exc.cmd, exc.stdout, exc.stderr) from exc
