#! /usr/bin/env python3
"""See "README.md" for details."""

__v_major__ = '5'
__v_minor__ = '0'
__v_patch__ = '0'
__v_alpha__ = 'alpha'
__appname__ = f'sacamantecas v{__v_major__}.{__v_minor__}.{__v_patch__}-{__v_alpha__}'

import atexit
from collections import namedtuple
import configparser
from ctypes import byref, c_uint, create_unicode_buffer, WinDLL, wintypes
from enum import IntEnum, StrEnum
import errno
from http.client import HTTPException
from html.parser import HTMLParser
import logging
from logging.config import dictConfig
from msvcrt import get_osfhandle, getch
from pathlib import Path
import platform
import re
from shutil import copy2
import sys
from textwrap import dedent
import time
import traceback as tb
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse, urlunparse
from urllib.request import urlopen, Request
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter
from openpyxl.styles import Font, PatternFill


class Messages(StrEnum):
    """Messages for the application."""
    WRONG_PLATFORM_ERROR = f'\n*** Error, {__appname__} solo funciona en la plataforma Win32.'
    INITIALIZATION_ERROR = 'Error de inicialización de la aplicación.'

    PRESS_ANY_KEY = '\nPulse cualquier tecla para continuar...'
    KEYBOARD_INTERRUPT = 'El usuario interrumpió la operación de la aplicación.'
    NO_ARGUMENTS = dedent('''
        No se han especificado fuentes de entrada para ser procesadas.

        Arrastre y suelte un fichero de entrada sobre el icono de la aplicación,
        o bien proporcione los nombres de las fuentes de entrada como argumentos.
    ''').lstrip()

    DEBUGGING_INIT = 'Registro de depuración iniciado.'
    APP_BANNER = f'{__appname__.replace(" v", " versión ")}'
    PROCESS_DONE = '\nProceso finalizado.'
    DEBUGGING_DONE = 'Registro de depuración finalizado.'

    ERROR_HEADER = f'\n*** Error en {__appname__}\n'
    WARNING_HEADER = '* Advertencia: '
    ERROR_DETAILS_HEADING = '\nInformación adicional sobre el error:'
    ERROR_DETAILS_TAIL_CHAR = '·'

    UNEXPECTED_OSERROR = 'Error inesperado del sistema operativo.'
    UNHANDLED_EXCEPTION = 'Excepción sin gestionar.'

    EMPTY_PROFILES = 'No hay perfiles definidos en el fichero de perfiles «{}».'
    MISSING_PROFILES = 'No se encontró o no se pudo leer el fichero de perfiles «{}».'
    PROFILES_WRONG_SYNTAX = 'Error de sintaxis «{}» leyendo el fichero de perfiles.'
    PROFILES_WRONG_SYNTAX_DETAILS = 'Perfil «{}», {}:\n  {}{}{}\n  {:_<{}}^'
    INVALID_PROFILE = 'El perfil «{}» es inválido.'
    PROFILE_WITHOUT_URL = 'El perfil no incluye un patrón de URL.'
    UNKNOWN_URL_TYPE = 'El URL «{}» es de tipo desconocido.'
    NO_MATCHING_PROFILE = 'No se encontró un perfil para procesar el URL.'

    OSLIKE_URLERROR = 'Error de red {}: {}.'
    HTTP_PROTOCOL_URLERROR = 'Error de protocolo HTTP {}: {}.'
    GENERIC_URLERROR = 'Error de URL{}: {}.'
    URL_ACCESS_ERROR = 'No resultó posible acceder a la dirección especificada.'
    HTTP_RETRIEVAL_ERROR = 'No se obtuvieron contenidos.'
    CONNECTION_ERROR = 'Se produjo un error de conexión «{}» accediendo al URL.'
    NO_CONTENTS_ERROR = 'No se recibieron contenidos del URL.'

    SKIMMING_MARKER = '\nSacando las mantecas:\n'
    SOURCE_LABEL = 'Fuente: {}'
    UNSUPPORTED_SOURCE = 'La fuente no es de un tipo admitido.'
    INPUT_FILE_INVALID = 'El fichero de entrada es inválido ({}).'
    INPUT_FILE_NOT_FOUND = 'No se encontró el fichero de entrada.'
    INPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para leer el fichero de entrada.'
    OUTPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para crear el fichero de salida.'


class ExitCodes(IntEnum):
    """Standardized exit codes for the application."""
    SUCCESS = 0
    NO_ARGUMENTS = 1
    WARNING = 2
    ERROR = 3
    KEYBOARD_INTERRUPT = 127


# Computed as early as possible.
TIMESTAMP_FORMAT = '_%Y%m%d_%H%M%S'
TIMESTAMP_STEM = time.strftime(TIMESTAMP_FORMAT)
USER_AGENT = ' '.join(dedent(f'''
    {__appname__.replace(" v", "/")}
    +https://github.com/DervishD/sacamantecas
    (Windows {platform.version()};
    {platform.architecture()[0]};
    {platform.machine()})
''').splitlines()).lstrip()


# Just to avoid mistyping.
EMPTY_STRING = ''
ENDING_PERIOD = '.'
DOUBLE_QUOTE = '"'
MANDATORY_PLATFORM = 'win32'
MAIN_MODULE = '__main__'
TRACEBACK_TOPLEVEL = '<module>'
UTF8_ENCODING = 'utf-8'
ASCII_ENCODING = 'ascii'
LATIN1_ENCODING = 'iso-8859-1'
BUNDLED_EXE_MARKER = 'frozen'
CONFIG_FILE_SUFFIX = '.ini'
TEXT_FILE_SUFFIX = '.txt'
LOGFILE_STEM = '_log'
DEBUGFILE_STEM = '_debug'
EXCEPTION_SUFFIX = 'Error'
SINK_FILENAME_STEM_MARKER = '_out'
SINK_FILEMODE = 'w'


if sys.platform != MANDATORY_PLATFORM:
    print(Messages.WRONG_PLATFORM_ERROR, file=sys.stderr)
    sys.exit(ExitCodes.ERROR)


try:
    if getattr(sys, BUNDLED_EXE_MARKER, False):
        SCRIPT_PATH = sys.executable
    else:
        SCRIPT_PATH = __file__
except NameError:
    print(Messages.INITIALIZATION_ERROR, file=sys.stderr)
    sys.exit(ExitCodes.ERROR)
SCRIPT_PATH = Path(SCRIPT_PATH).resolve()
INIFILE_PATH = SCRIPT_PATH.with_suffix(CONFIG_FILE_SUFFIX)
LOGFILE_PATH = SCRIPT_PATH.with_stem(f'{SCRIPT_PATH.stem}{LOGFILE_STEM}').with_suffix(TEXT_FILE_SUFFIX)
DEBUGFILE_PATH = SCRIPT_PATH.with_stem(f'{SCRIPT_PATH.stem}{DEBUGFILE_STEM}').with_suffix(TEXT_FILE_SUFFIX)
if sys.prefix == sys.base_prefix or not __v_alpha__:
    # Unless running and alpha version within a virtual environment,
    # add a timestamp marker to log and debug filenames.
    LOGFILE_PATH = LOGFILE_PATH.with_stem(f'{LOGFILE_PATH.stem}{TIMESTAMP_STEM}')
    DEBUGFILE_PATH = DEBUGFILE_PATH.with_stem(f'{DEBUGFILE_PATH.stem}{TIMESTAMP_STEM}')


# Needed for having VERY basic logging when the code is imported rather than run.
BASIC_LOGGING_FORMAT = '%(levelname).1s %(message)s'
logging.basicConfig(level=logging.NOTSET, format=BASIC_LOGGING_FORMAT, force=True)


# Reconfigure standard output streams so they use UTF-8 encoding, even if
# they are redirected to a file when running the application from a shell.
sys.stdout.reconfigure(encoding=UTF8_ENCODING)
sys.stderr.reconfigure(encoding=UTF8_ENCODING)


class BaseApplicationError(Exception):
    """Base class for all custom application exceptions."""
    # cSpell:ignore vararg
    def __init__ (self, message, details=EMPTY_STRING, *args, **kwargs):  # pylint: disable=keyword-arg-before-vararg
        self.details = details
        super().__init__(message, *args, **kwargs)

class ProfilesError(BaseApplicationError):
    """Raise for profile-related errors."""

class SourceError(BaseApplicationError):
    """Raise for source-related errors."""

class SkimmingError(BaseApplicationError):
    """Raise for skimming-related errors."""


Profile = namedtuple('Profile', ['url_pattern', 'parser', 'config'])


class BaseParser(HTMLParser):
    """Base class for catalogue parsers."""
    PARAMETERS = set()

    def __init__(self, *args, **kwargs):
        """Initialize object."""
        super().__init__(*args, **kwargs)
        self.config = {}
        for key in self.PARAMETERS:
            self.config[key] = None

    def reset(self):
        """Reset parser state. Called implicitly from __init__()."""
        super().reset()
        self.within_k = False
        self.within_v = False
        self.current_k = EMPTY_STRING
        self.current_v = EMPTY_STRING
        self.last_k = EMPTY_STRING
        self.retrieved_metadata = {}

    def configure(self, config):
        """
        Set up the parser with a different configuration, that is, a different
        set of values for the suppported parameters.

        Only supported config parameters are used, the rest are ignored.

        This operation also resets the parser.
        """
        self.reset()
        for key in config:
            if key not in self.PARAMETERS:
                continue
            self.config[key] = config[key]


class OldRegimeParser(BaseParser):  # pylint: disable=unused-variable
    """
    Parser for Old Regime catalogues which use different HTML class attributes
    to mark metadata keys and metadata values.

    This is inherently complex, specially when dealing with ill-formed HTML.

    So, in order to keep this parser as simple as possible, some assumptions are
    made. See the comments below to know which those are.
    """
    K_CLASS = 'k_class'
    V_CLASS = 'v_class'
    PARAMETERS = BaseParser.PARAMETERS | {K_CLASS, V_CLASS}


# cSpell:ignore Baratz
class BaratzParser(BaseParser):   # pylint: disable=unused-variable
    """
    Parser for catalogues whose contents have been generated by the new Baratz
    frontend, which does not use the class attributes to mark metadata keys and
    values. Instead they have an HTML element with acts as a start of metadata
    marker, containing the metadata as a list of <dt>/<dd> pairs.

    Within that list, the <dt> HTML element contains the metadata key, whereas
    the <dd> HTML element containing the metadata value.

    The HTML element which signals the start of a metadata block is defined by
    its HTML tag, the attribute containing the marker value and of course the
    marker value itself.
    """
    M_TAG = 'm_tag'
    M_ATTR = 'm_attr'
    M_VALUE = 'm_value'
    PARAMETERS = BaseParser.PARAMETERS | {M_TAG, M_ATTR, M_VALUE}


def error(message, details=EMPTY_STRING):
    """Helper for preprocessing error messages."""
    logging.indent(0)
    logging.error(Messages.ERROR_HEADER)
    logging.indent(len(Messages.ERROR_HEADER.split(' ')[0]))
    logging.error('%s', message)
    details = str(details)
    if details.strip():
        logging.error(Messages.ERROR_DETAILS_HEADING)
        logging.error('\n'.join(f'| {line}' for line in details.splitlines()))
        logging.error(Messages.ERROR_DETAILS_TAIL_CHAR)
    logging.indent(0)


def warning(message):
    """Helper for prepending a header to warning messages."""
    message = str(message)
    logging.warning('%s%s', Messages.WARNING_HEADER, f'{message[0].lower()}{message[1:]}')


ACCEPTED_URL_SCHEMES = ('https', 'http', 'file')
def is_accepted_url(value):
    """Check if value is an accepted URL or not."""
    # The check is quite crude but works for the application's needs.
    try:
        return urlparse(value).scheme in ACCEPTED_URL_SCHEMES
    except ValueError:
        return False


def generate_sink_filename(base_filename):
    """
    Generate a filename usable as data sink, based upon base_filename.
    """
    return base_filename.with_stem(base_filename.stem + SINK_FILENAME_STEM_MARKER)


KERNEL32_DLL = 'kernel32'
def wait_for_keypress():
    """Wait for a keypress to continue if sys.stdout is a real console AND the console is transient."""
    # First of all, if this script is being imported rather than run,
    # then the application must NOT pause. Absolutely NOT.
    if __name__ != MAIN_MODULE:
        return

    # If no console is attached, then the application must NOT pause.
    #
    # Since sys.stdout.isatty() returns True under Windows when sys.stdout
    # is redirected to NUL, another (more complex) method, is needed here.
    # The test below has been adapted from https://stackoverflow.com/a/33168697
    if not WinDLL(KERNEL32_DLL).GetConsoleMode(get_osfhandle(sys.stdout.fileno()), byref(c_uint())):
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
    if not WinDLL(KERNEL32_DLL).GetConsoleTitleW(console_title, buffer_size):
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
    if getattr(sys, BUNDLED_EXE_MARKER, False):
        if console_title != sys.executable:
            return
    elif console_title.find(SCRIPT_PATH.name) != -1:
        return

    print(Messages.PRESS_ANY_KEY, end=EMPTY_STRING, flush=True)
    getch()


EXC_HOOK_OSERROR_DETAILS = 'type = {}\nerrno = {}\nwinerror = {}\nstrerror = {}\nfilename = {}\nfilename2 = {}'
EXC_HOOK_EXCEPTION_DETAILS = 'type = {}\nvalue = {}\nargs: {}'
EXC_HOOK_EXCEPTION_DETAILS_ARGS = '\n  [{}] {}'
EXC_HOOK_TRACEBACK = '\n\ntraceback:\n{}'
EXC_HOOK_TRACEBACK_FRAME = '▸ {}\n'
EXC_HOOK_TRACEBACK_FRAME_LINE = '  {}, {}: {}\n'
def excepthook(exc_type, exc_value, exc_traceback):
    """Handle unhandled exceptions, default exception hook."""
    if isinstance(exc_value, OSError):
        message = Messages.UNEXPECTED_OSERROR
        details = EXC_HOOK_OSERROR_DETAILS.format(
            exc_type.__name__,
            EMPTY_STRING if exc_value.errno is None else errno.errorcode[exc_value.errno],
            EMPTY_STRING if exc_value.winerror is None else exc_value.winerror,
            exc_value.strerror,
            EMPTY_STRING if exc_value.filename is None else exc_value.filename,
            EMPTY_STRING if exc_value.filename2 is None else exc_value.filename2,
        )
    else:
        message = Messages.UNHANDLED_EXCEPTION
        args = EMPTY_STRING
        for arg in exc_value.args:
            args += EXC_HOOK_EXCEPTION_DETAILS_ARGS.format(type(arg).__name__, arg)
        details = EXC_HOOK_EXCEPTION_DETAILS.format(exc_type.__name__, str(exc_value), args)
    current_filename = None
    traceback = EMPTY_STRING
    for frame in tb.extract_tb(exc_traceback):
        if current_filename != frame.filename:
            traceback += EXC_HOOK_TRACEBACK_FRAME.format(frame.filename)
            current_filename = frame.filename
        frame.name = SCRIPT_PATH.name if frame.name == TRACEBACK_TOPLEVEL else frame.name
        traceback += EXC_HOOK_TRACEBACK_FRAME_LINE.format(frame.lineno, frame.name, frame.line)
    details += EXC_HOOK_TRACEBACK.format(traceback) if traceback else EMPTY_STRING
    error(message, details)


def loggerize(function):
    """Decorator which enables logging for function."""
    def loggerize_wrapper(*args, **kwargs):
        setup_logging(LOGFILE_PATH, DEBUGFILE_PATH)

        logging.debug(Messages.DEBUGGING_INIT)
        logging.info(Messages.APP_BANNER)
        logging.debug(USER_AGENT)

        status = function(*args, **kwargs)

        logging.info(Messages.PROCESS_DONE)
        logging.debug(Messages.DEBUGGING_DONE)
        logging.shutdown()
        return status
    return loggerize_wrapper


LOGGING_INDENTCHAR = ' '
LOGGING_FORMAT_STYLE = '{'
LOGGING_CUSTOM_INSTANCE = '()'
LOGGING_DEBUG_FORMAT = '{asctime}.{msecs:04.0f} {levelname}| {message}'
LOGGING_LOG_FORMAT = '{asctime} {message}'
LOGGING_CONSOLE_FORMAT = '{message}'
LOGGING_DATE_FORMAT = '%Y%m%d_%H%M%S'
LOGGING_LEVELNAME_FORMAT = f'{{:{len(max(logging.getLevelNamesMapping(), key=len))}}}'
LOGGING_FILE_MODE = 'w'
LOGGING_FILEHANDLER_CLASS = 'logging.FileHandler'
LOGGING_STREAMHANDLER_CLASS = 'logging.StreamHandler'
LOGGING_DEBUG_FORMATTER = 'debug_formatter'
LOGGING_LOG_FORMATTER = 'log_formatter'
LOGGING_CONSOLE_FORMATTER = 'console_formatter'
LOGGING_DEBUG_FILTER = 'debug_filter'
LOGGING_LOG_FILTER = 'log_filter'
LOGGING_STDOUT_FILTER = 'stdout_filter'
LOGGING_STDERR_FILTER = 'stderr_filter'
LOGGING_DEBUGFILE_HANDLER = 'debugfile_handler'
LOGGING_LOGFILE_HANDLER = 'logfile_handler'
LOGGING_STDOUT_HANDLER = 'stdout_handler'
LOGGING_STDERR_HANDLER = 'stderr_handler'
LOGGING_ROOT_LOGGER = ''
def setup_logging(log_filename, debug_filename):
    """
    Sets up logging system, disabling all existing loggers.

    With the current configuration ALL logging messages are sent to the debug
    file and messages with levels over logging.INFO are sent to the log file.

    Also, logging.INFO messages are sent to sys.stdout, without a timestamp.
    Finally, messages with levels over logging.INFO are sent to sys.stderr, also
    without a timestamp.
    """
    class CustomFormatter(logging.Formatter):
        """Simple custom formatter for logging messages."""
        def format(self, record):
            """
            Format multiline records so they look like multiple records.
            Indent message according to current indentation level.
            """
            message = super().format(record)
            preamble, message = message.partition(record.message)[:2]
            return '\n'.join([f'{preamble}{record.indent}{line.strip()}'.rstrip() for line in message.splitlines()])

    logging_configuration = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            LOGGING_DEBUG_FORMATTER: {
                LOGGING_CUSTOM_INSTANCE: CustomFormatter,
                'style': LOGGING_FORMAT_STYLE,
                'format': LOGGING_DEBUG_FORMAT,
                'datefmt': LOGGING_DATE_FORMAT,
            },
            LOGGING_LOG_FORMATTER: {
                LOGGING_CUSTOM_INSTANCE: CustomFormatter,
                'style': LOGGING_FORMAT_STYLE,
                'format': LOGGING_LOG_FORMAT,
                'datefmt': LOGGING_DATE_FORMAT,
            },
            LOGGING_CONSOLE_FORMATTER: {
                LOGGING_CUSTOM_INSTANCE: CustomFormatter,
                'style': LOGGING_FORMAT_STYLE,
                'format': LOGGING_CONSOLE_FORMAT,
            },
        },
        'filters': {
            LOGGING_DEBUG_FILTER: {
                LOGGING_CUSTOM_INSTANCE: lambda: lambda record: record.msg.strip() and record.levelno > logging.NOTSET
            },
            LOGGING_LOG_FILTER: {
                LOGGING_CUSTOM_INSTANCE: lambda: lambda record: record.msg.strip() and record.levelno >= logging.INFO
            },
            LOGGING_STDOUT_FILTER: {
                LOGGING_CUSTOM_INSTANCE: lambda: lambda record: record.msg.strip() and record.levelno == logging.INFO
            },
            LOGGING_STDERR_FILTER: {
                LOGGING_CUSTOM_INSTANCE: lambda: lambda record: record.msg.strip() and record.levelno > logging.INFO
            },
        },
        'handlers': {
            LOGGING_DEBUGFILE_HANDLER: {
                'level': logging.NOTSET,
                'formatter': LOGGING_DEBUG_FORMATTER,
                'filters': [LOGGING_DEBUG_FILTER],
                'class': LOGGING_FILEHANDLER_CLASS,
                'filename': debug_filename,
                'mode': LOGGING_FILE_MODE,
                'encoding': UTF8_ENCODING,
            },
            LOGGING_LOGFILE_HANDLER: {
                'level': logging.NOTSET,
                'formatter': LOGGING_LOG_FORMATTER,
                'filters': [LOGGING_LOG_FILTER],
                'class': LOGGING_FILEHANDLER_CLASS,
                'filename': log_filename,
                'mode': LOGGING_FILE_MODE,
                'encoding': UTF8_ENCODING,
            },
            LOGGING_STDOUT_HANDLER: {
                'level': logging.NOTSET,
                'formatter': LOGGING_CONSOLE_FORMATTER,
                'filters': [LOGGING_STDOUT_FILTER],
                'class': LOGGING_STREAMHANDLER_CLASS,
                'stream': sys.stdout,
            },
            LOGGING_STDERR_HANDLER: {
                'level': logging.NOTSET,
                'formatter': LOGGING_CONSOLE_FORMATTER,
                'filters': [LOGGING_STDERR_FILTER],
                'class': LOGGING_STREAMHANDLER_CLASS,
                'stream': sys.stderr,
            },
        },
        'loggers': {
            LOGGING_ROOT_LOGGER: {
                'level': logging.NOTSET,
                'handlers': [
                    LOGGING_DEBUGFILE_HANDLER,
                    LOGGING_LOGFILE_HANDLER,
                    LOGGING_STDOUT_HANDLER,
                    LOGGING_STDERR_HANDLER
                ],
                'propagate': False,
            },
        },
    }

    dictConfig(logging_configuration)

    setattr(logging.getLogger(), 'indentlevel', 0)

    current_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        """LogRecord factory which supports indentation."""
        record = current_factory(*args, **kwargs)
        record.indent = LOGGING_INDENTCHAR * logging.getLogger().indentlevel
        record.levelname = LOGGING_LEVELNAME_FORMAT.format(record.levelname)
        return record
    logging.setLogRecordFactory(record_factory)


INDENTLEVEL_INC = '+'
INDENTLEVEL_DEC = '-'
def set_logging_indent_level(level):
    """
    Set current indentation level.
    If level is INDENTLEVEL_INC, current indentation level is increased.
    If level is INDENTLEVEL_DEC, current indentation level is decreased.
    For any other value, indentation level is set to the provided value.
    """
    if level == INDENTLEVEL_INC:
        logging.getLogger().indentlevel += 1
        return
    if level == INDENTLEVEL_DEC:
        logging.getLogger().indentlevel -= 1
        return
    logging.getLogger().indentlevel = level
# Both logging.indent() and logging.dedent() support a parameter specifying an
# exact FINAL indentation level, not an indentation increment/decrement!
# These two helpers are provided in order to improve readability, since the
# set_logging_indent_level() function can be used directly.
logging.indent = lambda level = None: set_logging_indent_level(INDENTLEVEL_INC if level is None else level)
logging.dedent = lambda level = None: set_logging_indent_level(INDENTLEVEL_DEC if level is None else level)


def keyboard_interrupt_handler(function):
    """Decorator which wraps function with a simple KeyboardInterrupt handler."""
    def handle_keyboard_interrupt_wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except KeyboardInterrupt:
            warning(Messages.KEYBOARD_INTERRUPT)
            return ExitCodes.KEYBOARD_INTERRUPT
    return handle_keyboard_interrupt_wrapper


PROFILE_BADREGEX = 'BadRegex'
PROFILE_K_V_SEPARATOR = ' = '
PROFILE_URL_KEY = 'url'
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
    config = configparser.ConfigParser()
    logging.debug('Obteniendo perfiles desde «%s».', filename)
    try:
        with open(filename, encoding=UTF8_ENCODING) as inifile:
            config.read_file(inifile)
    except (FileNotFoundError, PermissionError) as exc:
        raise ProfilesError(Messages.MISSING_PROFILES.format(exc.filename)) from exc
    except configparser.Error as exc:
        errorname = type(exc).__name__.removesuffix(EXCEPTION_SUFFIX)
        raise ProfilesError(Messages.PROFILES_WRONG_SYNTAX.format(errorname), exc) from exc

    profiles = {}
    parsers = [parser() for parser in BaseParser.__subclasses__()]
    for section in config.sections():
        if not config[section]:
            continue
        options = {}
        for key, value in config[section].items():
            if not value:
                continue
            try:
                options[key] = re.compile(value, re.IGNORECASE)
            except re.error as exc:
                details = Messages.PROFILES_WRONG_SYNTAX_DETAILS.format(
                    section, exc.msg,
                    key, PROFILE_K_V_SEPARATOR, exc.pattern,
                    EMPTY_STRING, exc.pos + len(key) + len(PROFILE_K_V_SEPARATOR)
                )
                raise ProfilesError(Messages.PROFILES_WRONG_SYNTAX.format(PROFILE_BADREGEX), details) from exc
        url_pattern = options.pop(PROFILE_URL_KEY, None)
        if url_pattern is None:
            raise ProfilesError(Messages.INVALID_PROFILE.format(section), Messages.PROFILE_WITHOUT_URL)
        for parser in parsers:
            if options.keys() == parser.PARAMETERS:
                break
        else:
            raise ProfilesError(Messages.INVALID_PROFILE.format(section))
        profiles[section] = Profile(url_pattern, parser, options)
    return profiles


TEXTFILE_SOURCE_SUFFIX = '.txt'
SPREADSHEET_SOURCE_SUFFIX = '.xlsx'
def parse_arguments(*args):
    """
    Parse each argument in args to check if it is a valid source, identify its
    type and build the corresponding handler.

    Yield tuple containing the source and its corresponding handler, which will
    be None for unsupported sources.
    """
    for arg in args:
        logging.debug('Procesando argumento «%s».', arg)
        if is_accepted_url(arg):
            logging.debug('El argumento es una fuente de tipo single_url.')
            handler = single_url_handler(arg)
        elif arg.endswith(TEXTFILE_SOURCE_SUFFIX):
            logging.debug('El argumento es una fuente de tipo textfile.')
            handler = textfile_handler(Path(arg))
        elif arg.endswith(SPREADSHEET_SOURCE_SUFFIX):
            logging.debug('El argumento es una fuente de tipo spreadsheet.')
            handler = spreadsheet_handler(Path(arg))
        else:
            logging.debug('El argumento no es un tipo de fuente admitido.')
            handler = None
        yield arg, handler


# NOTE: the handlers below have to be generators for two reasons. First one, the
# list of URLs gathered by the handler from the source can be potentially large.
# So, using a generator is more efficient. Second one, this allows the caller to
# use the handler in two separate stages, first getting the URL so the handler
# keep processing it, and then sending the metadata obtained for the URL back to
# the handler. So, the handler is acting as both a coroutine and a generator.
#
# Since the metadata is sent back to the handler, it triggers another iteration
# so a double yield is needed. The first one is the one that yields the URLs and
# the second one yields a response to the caller after when the metadata is sent
# back to the handler.
#
# The first 'yield True' expression in the handlers is for signalling successful
# initialization after priming the generator/coroutine.


SINGLE_URL_HEADER = '{}\n'
SINGLE_URL_METADATA = '{}: {}\n'
SINGLE_URL_FOOTER = '\n'
def single_url_handler(url):
    """
    Handle single URLs.

    The metadata for the URL is logged with INFO level, so it will be printed on
    stdout and the corresponding log files, and it is also written into a dump
    file named after the URL (properly sanitized), as key-value pairs.

    The output file has UTF-8 encoding.
    """
    sink_filename = generate_sink_filename(url_to_filename(url).with_suffix(TEXT_FILE_SUFFIX))
    with open(sink_filename, SINK_FILEMODE, encoding=UTF8_ENCODING) as sink:
        logging.debug('Volcando metadatos a «%s».', sink_filename)
        yield True  # Successful initialization.
        if is_accepted_url(url):
            metadata = yield url
            yield
            if metadata:
                sink.write(SINGLE_URL_HEADER.format(url))
                for key, value in metadata.items():
                    message = SINGLE_URL_METADATA.format(key, value)
                    logging.indent()
                    logging.info(message)  # Output allowed here because it is part of the handler.
                    logging.dedent()
                    sink.write(message)
                sink.write(SINGLE_URL_FOOTER)


FILESYSTEM_UNSAFE_RE = r'\W'
FILESYSTEM_SAFE_CHAR = '_'
def url_to_filename(url):
    """Convert the given URL to a valid filename."""
    return Path(re.sub(FILESYSTEM_UNSAFE_RE, FILESYSTEM_SAFE_CHAR, url, re.ASCII))  # Quite crude but it works.


TEXTFILE_HEADER = '{}\n'
TEXTFILE_METADATA = '  {}: {}\n'
TEXTFILE_FOOTER = '\n'
def textfile_handler(source_filename):
    """
    Handle text files containing URLs, one per line.

    The metadata for each URL is dumped into another text file, named after the
    source file: first the URL is written, then the metadata as key-value pairs.
    Barely pretty-printed, but it is more than enough for a dump.

    All files are assumed to have UTF-8 encoding.
    """
    sink_filename = generate_sink_filename(source_filename)
    with open(source_filename, encoding=UTF8_ENCODING) as source:
        with open(sink_filename, SINK_FILEMODE, encoding=UTF8_ENCODING) as sink:
            logging.debug('Volcando metadatos a «%s».', sink_filename)
            yield True  # Successful initialization.
            for url in source.readlines():
                url = url.strip()
                if not is_accepted_url(url):
                    continue
                metadata = yield url
                yield
                if metadata:
                    sink.write(TEXTFILE_HEADER.format(url))
                    for key, value in metadata.items():
                        logging.debug('Añadiendo metadato «%s» con valor «%s».', key, value)
                        sink.write(TEXTFILE_METADATA.format(key, value))
                    sink.write(TEXTFILE_FOOTER)


SPREADSHEET_CELL_FONT = 'Calibri'
SPREADSHEET_CELL_COLOR = 'baddad'
SPREADSHEET_CELL_FILL = 'solid'
def spreadsheet_handler(source_filename):
    """
    Handle spreadsheets containing URLs, one per row. Ish.

    The metadata obtained for each URL is dumped into another spreadsheet, named
    after the source file, which is not created anew, it is just a copy of the
    source spreadsheet.

    The metadata is added to the spreadsheet in new columns, one per key. These
    columns are marked with a prefix as being added by the application.

    NOTE: not all sheets are processed, only the first one because it is the one
    where the URLs for the items are. Allegedly…
    """
    sink_filename = generate_sink_filename(source_filename)
    logging.debug('Copiando workbook a «%s».', sink_filename)

    copy2(source_filename, sink_filename)
    try:
        source_workbook = load_workbook(source_filename)
    except (KeyError, BadZipFile) as exc:
        details = str(exc).strip(DOUBLE_QUOTE)
        details = details[0].lower() + details[1:]
        raise SourceError(Messages.INPUT_FILE_INVALID.format(type(exc).__name__)) from exc
    sink_workbook = load_workbook(sink_filename)
    yield True  # Successful initialization.

    source_sheet = source_workbook.worksheets[0]
    logging.debug('La hoja con la que se trabajará es «%s»".', source_sheet.title)

    sink_sheet = sink_workbook.worksheets[0]
    logging.debug('Insertando fila de cabeceras.')
    sink_sheet.insert_rows(1, 1)

    for row in source_sheet.rows:
        logging.debug('Procesando fila %s.', row[0].row)
        if (url := get_url_from_row(row)) is None:
            continue
        metadata = yield url
        yield
        store_metadata_in_sheet(sink_sheet, row, metadata)
    sink_workbook.save(sink_filename)
    sink_workbook.close()
    source_workbook.close()


STRING_CELL_TYPE = 's'
def get_url_from_row(row):
    """Find first URL in row."""
    url = None
    for cell in row:
        if cell.data_type != STRING_CELL_TYPE:
            logging.debug('La celda «%s» no es de tipo cadena, será ignorada.', cell.coordinate)
            continue
        if is_accepted_url(cell.value):
            logging.debug('Se encontró un URL en la celda «%s»: %s', cell.coordinate, cell.value)
            url = cell.value
            break  # Only the FIRST URL found in each row is considered.
    return url


SPREADSHEET_METADATA_COLUMN = '[sm] {}'
def store_metadata_in_sheet(sheet, row, metadata, static = SimpleNamespace(known_metadata = {})):
    """
    Store metadata in provided sheet at given row.

    For new metadata, a new column is added to the sheet.
    For already existing metadata, the value is added to the existing column.
    """
    # NOTE: since default parameters are evaluated just once, a typical trick
    # for simulating static variables in functions is using a 'fake' default
    # parameter and using SimpleNamespace: https://stackoverflow.com/a/51437838
    if not metadata:
        return
    for key, value in metadata.items():
        key = SPREADSHEET_METADATA_COLUMN.format(key)
        if key not in static.known_metadata:
            logging.debug('Se encontró un metadato nuevo, «%s».', key)
            column = sheet.max_column + 1
            static.known_metadata[key] = column
            logging.debug('El metadato «%s» irá en la columna «%s».', key, get_column_letter(column))
            cell = sheet.cell(row=1, column=column, value=key)
            cell.font = Font(name=SPREADSHEET_CELL_FONT)
            cell.fill = PatternFill(start_color=SPREADSHEET_CELL_COLOR, fill_type=SPREADSHEET_CELL_FILL)
                # Set column width.
                #
                # As per Excel specification, the width units are the width of
                # the zero character of the font used by the Normal style for a
                # workbook. So a column of width 10 would fit exactly 10 zero
                # characters in the font specified by the Normal style.
                #
                # No, no kidding.
                #
                # Since this width units are, IMHO, totally arbitrary, let's
                # choose an arbitrary column width. To wit, the Answer to the
                # Ultimate Question of Life, the Universe, and Everything.
            sheet.column_dimensions[get_column_letter(column)].width = 42
                # This is needed because sometimes Excel files are not properly
                # generated and the last column has a 'max' field too large, and
                # that has an unintended consequence: ANY change to the settings
                # of that column affects ALL the following ones whose index is
                # less than 'max'… So, it's better to fix that field.
            sheet.column_dimensions[get_column_letter(column)].max = column
        logging.debug('Añadiendo metadato «%s» con valor «%s».', key, value)
            # Since a heading row is inserted, the rows where metadata has to go
            # have now an +1 offset, as they have been displaced.
        sheet.cell(row[0].row + 1, static.known_metadata[key], value=value)


def bootstrap(handler):
    """Bootstrap (prime) and handle initialization errors for handler."""
    if handler is None:
        raise SourceError(Messages.UNSUPPORTED_SOURCE)

    try:
        handler.send(None)
    except FileNotFoundError as exc:
        raise SourceError(Messages.INPUT_FILE_NOT_FOUND) from exc
    except PermissionError as exc:
        if Path(exc.filename).stem.endswith(SINK_FILENAME_STEM_MARKER):
            raise SourceError(Messages.OUTPUT_FILE_NO_PERMISSION) from exc
        raise SourceError(Messages.INPUT_FILE_NO_PERMISSION) from exc


def get_parser(url, profiles):
    """Find and return parser for url according to its maching profile."""
    for profile_name, profile in profiles.items():
        if profile.url_pattern.search(url):
            logging.debug('Perfil detectado: «%s».', profile_name)
            parser = profile.parser
            return parser
    return None


UNKNOWN_ERRNO = 'desconocido'
HTTPEXCEPTION_DETAILS = '{}: {}.'
CONNECTIONERROR_DETAILS = '{}.'
def saca_las_mantecas(url, parser):
    """
    Saca las mantecas from the provided url, that is, retrieve its contents,
    parse them using parser, and obtain library catalogue metadata, if any.

    Return obtained metadata as a dictionary.
    """
    try:
        contents = retrieve_url(url)
    except URLError as exc:
        # Depending on the particular error which happened, the reason attribute
        # of the URLError exception can be a simple error message, an instance
        # of some OSError derived Exception, etc. So, in order to have useful
        # messages, some discrimination has to be done here.
        if isinstance(exc.reason, OSError):
            try:
                error_code = errno.errorcode[exc.reason.errno]
            except KeyError:
                error_code = exc.reason.errno
            except AttributeError:
                error_code = UNKNOWN_ERRNO
            error_reason = exc.reason.strerror
            details = Messages.OSLIKE_URLERROR
        elif isinstance(exc, HTTPError):
            error_code = exc.code
            error_reason = exc.reason.lower()
            details = Messages.HTTP_PROTOCOL_URLERROR
        else:
            error_code = EMPTY_STRING
            error_reason = exc.reason
            details = Messages.GENERIC_URLERROR
        error_reason = (error_reason[0].lower() + error_reason[1:]).rstrip(ENDING_PERIOD)
        raise SkimmingError(Messages.URL_ACCESS_ERROR, details.format(error_code, error_reason)) from exc
    # Apparently, HTTPException, ConnectionError and derived exceptions are
    # masked or wrapped by urllib, and documentation is not very informative.
    # So, just in case something weird happen, it is better to handle these
    # exception types as well.
    except HTTPException as exc:
        details = HTTPEXCEPTION_DETAILS.format(type(exc).__name__, exc)
        raise SkimmingError(Messages.HTTP_RETRIEVAL_ERROR, details) from exc
    except ConnectionError as exc:
        try:
            error_code = errno.errorcode[exc.errno]
        except (AttributeError, KeyError):
            error_code = UNKNOWN_ERRNO
        details = CONNECTIONERROR_DETAILS.format(exc.strerror.capitalize().rstrip(ENDING_PERIOD))
        raise SkimmingError(Messages.CONNECTION_ERROR.format(error_code), details) from exc

    if not contents:
        raise SkimmingError(Messages.NO_CONTENTS_ERROR)

    parser.feed(contents)
    parser.close()
    return {'key_1': 'value_1', 'key_2': 'value_2', 'key_3': 'value_3'}


FILE_URL_SCHEME = 'file://'
USER_AGENT_HEADER = 'User-Agent'
def retrieve_url(url):
    """
    Retrieve contents from url.

    First resolve any meta http-equiv="Refresh" redirection for url and then get
    the contents as a byte string.

    The contents are decoded using the detected charset.

    Return the decoded contents as a string.

    """
    if not is_accepted_url(url):
        raise URLError(Messages.UNKNOWN_URL_TYPE.format(url))

    if url.startswith(FILE_URL_SCHEME):
        url = resolve_file_url(url)

    while url:
        logging.debug('Procesando URL «%s».', url)
        with urlopen(Request(url, headers={USER_AGENT_HEADER: USER_AGENT})) as response:
            # First, check if any redirection is needed and get the charset the easy way.
            contents = response.read()
            charset = response.headers.get_content_charset()
        url = get_redirected_url(url, contents)

    # In this point, we have the contents as a byte string.
    # If the charset is None, it has to be determined the hard way.
    if charset is None:
        charset = detect_html_charset(contents)
    else:
        logging.debug('Charset detectado en las cabeceras.')
    logging.debug('Contenidos codificados con charset «%s».', charset)

    return contents.decode(charset)


QUOTING_SAFE_CHARS = ':/'
def resolve_file_url(url):
    """Resolve relative paths in file: url."""
    parsed_url = urlparse(url)
    resolved_path = unquote(parsed_url.path[1:])
    resolved_path = Path(resolved_path).resolve().as_posix()
    resolved_path = quote(resolved_path, safe=QUOTING_SAFE_CHARS)
    return parsed_url._replace(path=resolved_path).geturl()


META_REFRESH_RE = rb'<meta http-equiv="refresh" content="(?:[^;]+;\s+)?URL=([^"]+)"'
REPLACEABLE_FIELDS = ('scheme', 'netloc')
def get_redirected_url(base_url, contents):
    """
    Get redirected URL from a meta http-equiv="refresh" pragma in contents. Use
    base_url as base URL for redirection, if some parts are missing in the URL
    specified by the pragma.

    Return redirected URL, or None if there is no redirection pragma.
    """
    if match := re.search(META_REFRESH_RE, contents, re.I):
        base_url = urlparse(base_url)
        redirected_url = urlparse(match.group(1).decode(ASCII_ENCODING))
        for field in base_url._fields:
            value = getattr(base_url, field)
            # If not specified in the redirected URL, both the scheme and netloc
            # will be reused from the base URL. Any other field will be obtained
            # from the redirected URL and used, no matter if it is empty.
            if field in REPLACEABLE_FIELDS and not getattr(redirected_url, field):
                redirected_url = redirected_url._replace(**{field: value})
        redirected_url = urlunparse(redirected_url)
        logging.debug('URL redirigido a «%s».', redirected_url)
        return redirected_url
    return None


META_HTTP_EQUIV_CHARSET_RE = rb'<meta http-equiv="content-type".*charset="([^"]+)"'
META_CHARSET_RE = rb'<meta charset="([^"]+)"'
def detect_html_charset(contents):
    """
    Detect contents charset from HTML tags, if any, and return it.

    If the charset can not be determined, iso-8859-1 is used as fallback even
    though utf-8 may look as a much better fallback. Modern web pages may NOT
    specify any encoding if they are using utf-8 and it is identical to ascii
    for 7-bit codepoints. The problem is that utf-8 will fail for pages whose
    encoding is iso-8859-1, AND most if not all of the web pages processed by
    this application which does not specify a charset will in fact be using
    iso-8859-1 anyway, so in the end that is a safer fallback.
    """
    charset = LATIN1_ENCODING
    if match := re.search(META_HTTP_EQUIV_CHARSET_RE, contents, re.I):
        # Next best thing, from the meta http-equiv="content-type".
        logging.debug('Charset detectado mediante meta http-equiv.')
        charset = match.group(1).decode(ASCII_ENCODING)
    elif match := re.search(META_CHARSET_RE, contents, re.I):
        # Last resort, from some meta charset, if any…
        logging.debug('Charset detectado mediante meta charset.')
        charset = match.group(1).decode(ASCII_ENCODING)
    else:
        logging.debug('Charset not detectado, usando valor por defecto.')
    return charset


@loggerize
@keyboard_interrupt_handler
def main(*args):
    """."""
    exitcode = ExitCodes.SUCCESS

    if not args:
        # Input arguments should be provided automatically to the application if
        # it is used as a drag'n'drop target which is actually the intended way
        # of operation, generally speaking.
        #
        # But the application can be also run by hand from a command prompt, so
        # it is better to signal the end user with an error and explanation if
        # no input arguments are provided, as soon as possible.
        error(Messages.NO_ARGUMENTS)
        return ExitCodes.NO_ARGUMENTS

    try:
        profiles = load_profiles(INIFILE_PATH)
        if not profiles:
            raise ProfilesError(Messages.EMPTY_PROFILES.format(INIFILE_PATH))
        logging.debug('Se obtuvieron los siguientes perfiles: %s.', list(profiles.keys()))
    except ProfilesError as exc:
        error(exc, exc.details)
        return ExitCodes.ERROR

    logging.info(Messages.SKIMMING_MARKER)
    logging.indent()
    for source, handler in parse_arguments(*args):
        logging.info(Messages.SOURCE_LABEL.format(source))
        try:
            bootstrap(handler)
        except SourceError as exc:
            logging.indent()
            warning(exc)
            logging.dedent()
            exitcode = ExitCodes.WARNING
            continue

        logging.indent()
        for url in handler:
            logging.info(url)
            metadata = {}
            try:
                if (parser := get_parser(url, profiles)) is None:
                    raise SkimmingError(Messages.NO_MATCHING_PROFILE)
                metadata = saca_las_mantecas(url, parser)
            except SkimmingError as exc:
                logging.indent()
                warning(exc)
                logging.debug(exc.details)
                logging.dedent()
                exitcode = ExitCodes.WARNING
            finally:
                # No matter if metadata has actual contents or not, the handler
                # has to be 'advanced' to the next URL, so the metadata it is
                # expecting has to be sent to the handler.
                handler.send(metadata)
        logging.dedent()
    logging.dedent()
    return exitcode


atexit.register(wait_for_keypress)
sys.excepthook = excepthook
if __name__ == MAIN_MODULE:
    sys.exit(main(*sys.argv[1:]))
