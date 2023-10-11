#! /usr/bin/env python3
"""See "README.md" for details."""

__version__ = 'v5.0alpha'

import configparser
import sys
from pathlib import Path
import errno
from enum import StrEnum, IntEnum, auto
import logging
import atexit
from logging.config import dictConfig
import traceback as tb
import re
import time
import platform
from abc import ABC as Abstract, abstractmethod
from msvcrt import getch, get_osfhandle
from ctypes import WinDLL, byref, c_uint, create_unicode_buffer, wintypes


# Computed as early as possible.
TIMESTAMP = time.strftime('%Y%m%d_%H%M%S')


class ExitCodes(IntEnum):
    """Standardized exit codes for the application. """
    SUCCESS = 0
    WARNING_BASE = 1
    WARNING_KEYBOARD_INTERRUPT = auto()
    WARNING_INVALID_SOURCE = auto()
    WARNING_MISSING_SOURCE = auto()
    ERRORS_BASE = 127
    ERROR_NO_ARGUMENTS = auto()
    ERROR_EMPTY_PROFILES = auto()
    ERROR_MISSING_PROFILES = auto()
    ERROR_PROFILES_WRONG_SYNTAX = auto()


class Messages(StrEnum):
    """Messages for the application."""
    INITIALIZATION_ERROR = 'Error de inicialización de la aplicación.'
    W32_ONLY_ERROR = '%s solo funciona en la plataforma Win32.'
    USER_AGENT = 'User-Agent: «%s»'
    KEYBOARD_INTERRUPTION = '\nEl usuario interrumpión la operación de la aplicación.'
    NO_ARGUMENTS = (
        'No se ha especificado un fichero de entrada para ser procesado.\n'
        '\n'
        'Arrastre y suelte un fichero de entrada sobre el icono de la aplicación, '
        'o proporcione el nombre del fichero como argumento.'
    )
    DEBUGGING_INIT = 'Registro de depuración iniciado.'
    EMPTY_PROFILES = 'No hay perfiles definidos en el fichero de perfiles «%s».'
    MISSING_PROFILES = 'No se encontró o no se pudo leer el fichero de perfiles «%s».'
    PROFILES_WRONG_SYNTAX = 'Error de sintaxis «%s» leyendo el fichero de perfiles.\n%s'
    SKIMMING_MARKER = '\nSacando las mantecas:'
    UNSUPPORTED_SOURCE = 'La fuente «%s» no es de un tipo admitido.'
    EOP = '\nProceso finalizado.'
    DEBUGGING_DONE = 'Registro de depuración finalizado.'


try:
    if getattr(sys, 'frozen', False):
        SCRIPT_PATH = sys.executable
    else:
        SCRIPT_PATH = __file__
except NameError:
    sys.exit(Messages.INITIALIZATION_ERROR)

SCRIPT_PATH = Path(SCRIPT_PATH).resolve()
APP_NAME = SCRIPT_PATH.stem + ' ' + __version__

INIFILE_PATH = SCRIPT_PATH.with_suffix('.ini')
DEBUGFILE_PATH = Path(f'{SCRIPT_PATH.with_suffix("")}_debug_{TIMESTAMP}.txt')
LOGFILE_PATH = Path(f'{SCRIPT_PATH.with_suffix("")}_log_{TIMESTAMP}.txt')

BANNER = f'{APP_NAME.replace(" v", " versión ")}'
USER_AGENT = f'{APP_NAME.replace(" v", "/")} +https://github.com/DervishD/sacamantecas'
USER_AGENT += f' (Windows {platform.version()}; {platform.architecture()[0]}; {platform.machine()})'

ERROR_HEADER = f'\n*** Error en {APP_NAME}\n'
WARNING_HEADER = '* Warning: '


if sys.platform != 'win32':
    sys.exit(Messages.W32_ONLY_ERROR % APP_NAME)


# Needed for having VERY basic logging when the code is imported rather than run.
logging.basicConfig(level=logging.NOTSET, format='%(levelname).1s %(message)s', force=True)


# Reconfigure standard output streams so they use UTF-8 encoding, even if
# they are redirected to a file when running the application from a shell.
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


# Custom errors.
class MissingProfilesError(Exception):
    """Raise when profiles configuration file is missing."""
    def __init__ (self, filename):
        self.filename = filename

class ProfilesSyntaxError(Exception):
    """Raise when profiles configuration file has syntax errors."""
    def __init__ (self, errortype, details):
        self.error = errortype
        self.details = details

class UnsupportedSourceError(Exception):
    """Raise when an input source has an unsupported type"""
    def __init__ (self, source):
        self.source = source


class BaseURLSource(Abstract):
    """
    Base abstract class to define an interface for URL sources.
    """
    def __init__(self, source):
        self.source = source

    @abstractmethod
    def get_urls(self):
        """
        Pure virtual function: yield URLs found in source.

        Must be a generator which closes used resources when exhausted.
        """


class ExcelURLSource(BaseURLSource):
    """."""
    def get_urls(self):
        """."""


class TextURLSource(BaseURLSource):
    """."""
    def get_urls(self):
        """."""


class SingleURLSource(BaseURLSource):
    """Handle single URLs."""
    def get_urls(self):
        """
        Yield the URLs found in the URL, that is… the URL itself.

        The generator stops after only one iteration, of course.
        """
        yield self.source


def error(message, *args, **kwargs):
    """Helper for prepending a header to error messages."""
    logging.error(f'{ERROR_HEADER}{message}', *args, **kwargs)


def warning(message, *args, **kwargs):
    """Helper for prepending a header to warning messages."""
    logging.warning(f'{WARNING_HEADER}{message}', *args, **kwargs)


def wait_for_keypress():
    """Wait for a keypress to continue if sys.stdout is a real console AND the console is transient."""
    # First of all, if this script is being imported rather than run,
    # then the application must NOT pause. Absolutely NOT.
    if __name__ != '__main__':
        return

    # If no console is attached, then the application must NOT pause.
    #
    # Since sys.stdout.isatty() returns True under Windows when sys.stdout
    # is redirected to NUL, another (more complex) method, is needed here.
    # The test below has been adapted from https://stackoverflow.com/a/33168697
    if not WinDLL('kernel32').GetConsoleMode(get_osfhandle(sys.stdout.fileno()), byref(c_uint())):
        return

    # If there is a console attached, the application must pause ONLY if that
    # console will automatically close when the application finishes, hiding
    # any messages printed by the application. In other words, pause only if
    # the console is transient.
    #
    # Determining if a console is transient is not easy as there is no
    # bulletproof method available for every possible circumstance.
    #
    # There are TWO main scenarios: a frozen executable and a .py file.
    # In both cases, the console title has to be obtained.
    buffer_size = wintypes.MAX_PATH + 1
    console_title = create_unicode_buffer(buffer_size)
    if not WinDLL('kernel32').GetConsoleTitleW(console_title, buffer_size):
        return
    console_title = console_title.value

    # If the console is not transient, return, do not pause.
    #
    # For a frozen executable, it is more or less easy: if the console title
    # is not equal to sys.executable, then the console is NOT transient.
    #
    # For a .py file, it is a bit more complicated, but in most cases if the
    # console title contains the name of the .py file, the console is NOT a
    # transient console.
    if getattr(sys, 'frozen', False):
        if console_title != sys.executable:
            return
    elif console_title.find(SCRIPT_PATH.name) != -1:
        return

    print('\nPulse cualquier tecla para continuar...', end='', flush=True)
    getch()


def excepthook(exc_type, exc_value, exc_traceback):
    """Handle unhandled exceptions, default exception hook."""
    message = '✱ '
    if isinstance(exc_value, OSError):
        message += f'Error inesperado del sistema operativo.\n{exc_type.__name__}'
        if exc_value.errno is not None:
            message += f'/{errno.errorcode[exc_value.errno]}'
        if exc_value.winerror is not None:
            message += f'/Win{exc_value.winerror}'
        message += f': {exc_value.strerror}.\n'
        if exc_value.filename is not None:
            message += 'Fichero'
            if exc_value.filename2 is not None:
                message += f' de origen:  «{exc_value.filename}».\n'
                message += f'Fichero de destino: «{exc_value.filename2}».\n'
            else:
                message += f': «{exc_value.filename}».\n'
    else:
        message += f'Excepción sin gestionar.\n«{exc_type.__name__}»'
        message += f': {exc_value}.' if str(exc_value) else ''
        message += '\n'
    message += '\n'
    current_filename = None
    for frame in tb.extract_tb(exc_traceback):
        if current_filename != frame.filename:
            message += f'▸ Fichero {frame.filename}\n'
            current_filename = frame.filename
        message += f'  Línea {frame.lineno} ['
        message += SCRIPT_PATH.name if frame.name == '<module>' else frame.name
        message += ']'
        message += f': {frame.line}' if frame.line else ''
        message += '\n'
    error(message.rstrip())


def setup_logging(log_filename, debug_filename):
    """
    Sets up logging system, disabling all existing loggers.

    With the current configuration ALL logging messages are sent to the debug
    file and messages with levels over logging.INFO are sent to the log file.

    Also, logging.INFO messages are sent to sys.stdout, without a timestamp.
    Finally, messages with levels over logging.INFO are sent to sys.stderr, also
    without a timestamp.
    """
    class MultilineFormatter(logging.Formatter):
        """Simple multiline formatter for logging messages."""
        def format(self, record):
            """Format multiline records so they look like multiple records."""
            message = super().format(record)
            preamble, message = message.partition(record.message)[:2]
            preamble = preamble.rstrip()
            message = [f' {line.rstrip()}' if line.strip() else '' for line in message.splitlines()]
            return '\n'.join([f'{preamble}{line}' for line in message])


    logging_configuration = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'debug': {
                '()': MultilineFormatter,
                'style': '{',
                'format': '{asctime}.{msecs:04.0f} [{levelname}] {message}',
                'datefmt': '%Y%m%d_%H%M%S'
            },
            'log': {
                '()': MultilineFormatter,
                'style': '{',
                'format': '{asctime} {message}',
                'datefmt': '%Y%m%d_%H%M%S'
            },
            'console': {
                'style': '{',
                'format': '{message}'
            },
        },
        'filters': {
            'debug': {
                '()': lambda: lambda log_record: log_record.msg.strip() and log_record.levelno > logging.NOTSET
            },
            'info': {
                '()': lambda: lambda log_record: log_record.msg.strip() and log_record.levelno >= logging.INFO
            },
            'stdout': {
                '()': lambda: lambda log_record: log_record.msg.strip() and log_record.levelno == logging.INFO
            },
            'stderr': {
                '()': lambda: lambda log_record: log_record.msg.strip() and log_record.levelno > logging.INFO
            },
        },
        'handlers': {},
        'loggers': {
            '': {
                'level': 'NOTSET',
                'handlers': [],
                'propagate': False,
            },
        },
    }

    logging_configuration['handlers']['debugfile'] = {
        'level': 'NOTSET',
        'formatter': 'debug',
        'filters': ['debug'],
        'class': 'logging.FileHandler',
        'filename': debug_filename,
        'mode': 'w',
        'encoding': 'utf8'
    }

    logging_configuration['handlers']['logfile'] = {
        'level': 'NOTSET',
        'formatter': 'log',
        'filters': ['info'],
        'class': 'logging.FileHandler',
        'filename': log_filename,
        'mode': 'w',
        'encoding': 'utf8'
    }

    logging_configuration['handlers']['stdout'] = {
        'level': 'NOTSET',
        'formatter': 'console',
        'filters': ['stdout'],
        'class': 'logging.StreamHandler',
        'stream': sys.stdout
    }

    logging_configuration['handlers']['stderr'] = {
        'level': 'NOTSET',
        'formatter': 'console',
        'filters': ['stderr'],
        'class': 'logging.StreamHandler',
        'stream': sys.stderr
    }

    logging_configuration['loggers']['']['handlers'].append('debugfile')
    logging_configuration['loggers']['']['handlers'].append('logfile')
    logging_configuration['loggers']['']['handlers'].append('stdout')
    logging_configuration['loggers']['']['handlers'].append('stderr')

    dictConfig(logging_configuration)


def load_profiles(filename):
    """
    Load the profiles from filename.

    Return the preprocessed list of profiles as a dictionary where the keys are
    the profiles which were found in filename and the values are dictionaries
    containing the corresponding profile configuration items as key-value pairs.

    Raise MissingProfilesError if filename cannot be opened or read.

    Raise ProfilesSyntaxError if there is any syntax error in filename.

    The returned dictionary will be empty if no profiles or only empty profiles
    are present in filename.
    """
    parser = configparser.ConfigParser()
    logging.debug('Obteniendo perfiles desde «%s».', filename)
    try:
        with open(filename, encoding='utf-8') as inifile:
            parser.read_file(inifile)
    except (FileNotFoundError, PermissionError) as exc:
        raise MissingProfilesError(exc.filename) from exc
    except configparser.Error as exc:
        raise ProfilesSyntaxError(type(exc).__name__.removesuffix('Error'), exc) from exc

    profiles = {}
    for profile in parser.sections():
        profiles[profile] = {}
        for key, value in parser[profile].items():
            try:
                profiles[profile][key] = re.compile(value, re.IGNORECASE) if value else None
            except re.error as exc:
                message = f'Perfil «{profile}»: {exc.msg[0].upper() + exc.msg[1:]}.\n'
                message += f'  {key} = {exc.pattern}\n'
                message += '  ' + '_' * (exc.pos + len(key) + len(' = ')) + '^'
                raise ProfilesSyntaxError('BadRegex', message) from exc
    return {key: value for key, value in profiles.items() if value}


def url_to_filename(url):
    """Convert the given URL to a valid filename."""
    return re.sub(r'\W', '_', url, re.ASCII)  # Quite crude but it works.


def parse_arguments(args):
    """
    Parse each argument in args to check if it is a valid source, identify its
    type and build the corresponding handler.

    Yield built source object.

    Raises UnsupportedSourceError(source) for unsupported sources types.
    """
    for arg in args:
        logging.debug('Procesando argumento «%s».', arg)

        source = None
        if re.match(r'(?:https?|file)://', arg):
            logging.debug('La fuente es un URL.')
            source = SingleURLSource(arg)
        elif arg.endswith('.txt'):
            logging.debug('La fuente es un fichero de texto.')
            source = TextURLSource(Path(arg))
        elif arg.endswith('.xlsx'):
            logging.debug('La fuente es una hoja de cálculo.')
            source = ExcelURLSource(Path(arg))
        else:
            logging.debug('El argumento no es un tipo de fuente admitido.')
            raise UnsupportedSourceError(arg)
        yield source


def loggerize(function):
    """Decorator which enables logging for function."""
    def loggerize_wrapper(*args, **kwargs):
        setup_logging(LOGFILE_PATH, DEBUGFILE_PATH)

        logging.debug(Messages.DEBUGGING_INIT)
        logging.debug(Messages.USER_AGENT, USER_AGENT)

        status = function(*args, **kwargs)

        logging.info(Messages.EOP)
        logging.debug(Messages.DEBUGGING_DONE)
        logging.shutdown()
        return status
    return loggerize_wrapper


def keyboard_interrupt_handler(function):
    """Decorator which wraps function with a simple KeyboardInterrupt handler."""
    def handle_keyboard_interrupt_wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except KeyboardInterrupt:
            warning(Messages.KEYBOARD_INTERRUPTION)
            return ExitCodes.WARNING_KEYBOARD_INTERRUPT
    return handle_keyboard_interrupt_wrapper


@loggerize
@keyboard_interrupt_handler
def main(args):
    """."""
    logging.info(BANNER)

    exitcode = ExitCodes.SUCCESS

    if len(args) == 0:
        # The input source should be provided automatically if the application
        # is used as a drag'n'drop target which is in fact the intended method
        # of operation.
        #
        # But the application can be also run by hand from a command prompt, so
        # it is better to signal the end user with an error and explanation if
        # the input source is missing, as soon as possible.
        error(Messages.NO_ARGUMENTS)
        return ExitCodes.ERROR_NO_ARGUMENTS

    try:
        profiles = load_profiles(INIFILE_PATH)
        if not profiles:
            error(Messages.EMPTY_PROFILES, INIFILE_PATH)
            return ExitCodes.ERROR_EMPTY_PROFILES
        logging.debug('Se obtuvieron los siguientes perfiles: %s.', list(profiles.keys()))
    except MissingProfilesError as exc:
        error(Messages.MISSING_PROFILES, exc.filename)
        return ExitCodes.ERROR_MISSING_PROFILES
    except ProfilesSyntaxError as exc:
        error(Messages.PROFILES_WRONG_SYNTAX, exc.error, exc.details)
        return ExitCodes.ERROR_PROFILES_WRONG_SYNTAX

    logging.info(Messages.SKIMMING_MARKER)
    try:
        for handler in parse_arguments(args):
            for url in handler.get_urls():
                print(url)
    except UnsupportedSourceError as exc:
        warning(Messages.UNSUPPORTED_SOURCE, exc.source)
        exitcode = ExitCodes.WARNING_BASE

    return exitcode


atexit.register(wait_for_keypress)
sys.excepthook = excepthook
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
