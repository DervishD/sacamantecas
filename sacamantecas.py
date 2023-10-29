#! /usr/bin/env python3
"""See "README.md" for details."""

__version__ = 'v5.0alpha'
__appname__ = f'sacamantecas {__version__}'


import atexit
import configparser
from ctypes import byref, c_uint, create_unicode_buffer, WinDLL, wintypes
from enum import auto, IntEnum, StrEnum
import errno
import logging
from logging.config import dictConfig
from msvcrt import get_osfhandle, getch
from pathlib import Path
import platform
import re
from shutil import copy2
import sys
import time
import traceback as tb
from types import SimpleNamespace
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter
from openpyxl.styles import Font, PatternFill


if sys.platform != 'win32':
    sys.exit(f'{__appname__} solo funciona en la plataforma Win32.')


# Computed as early as possible.
TIMESTAMP = time.strftime('%Y%m%d_%H%M%S')
USER_AGENT = ' '.join((
    f'{__appname__.replace(" v", "/")}',
    '+https://github.com/DervishD/sacamantecas',
    f'(Windows {platform.version()};',
    f'{platform.architecture()[0]};',
    f'{platform.machine()})'
))

class ExitCodes(IntEnum):
    """Standardized exit codes for the application. """
    SUCCESS = 0
    WARNING = 1
    KEYBOARD_INTERRUPT = 127
    ERROR_NO_ARGUMENTS = auto()
    ERROR_EMPTY_PROFILES = auto()
    ERROR_MISSING_PROFILES = auto()
    ERROR_PROFILES_WRONG_SYNTAX = auto()


 # Messages for the application.
Messages = SimpleNamespace()
Messages.APP_INIT = f'{__appname__.replace(" v", " versión ")}'
Messages.APP_DONE = '\nProceso finalizado.'
Messages.DEBUGGING_INIT = 'Registro de depuración iniciado.'
Messages.DEBUGGING_DONE = 'Registro de depuración finalizado.'
Messages.ERROR_HEADER = f'\n*** Error en {__appname__}\n'
Messages.WARNING_HEADER = '* Warning: '
Messages.INITIALIZATION_ERROR = 'Error de inicialización de la aplicación.'
Messages.USER_AGENT = f'User-Agent: {USER_AGENT}'
Messages.KEYBOARD_INTERRUPTION = '\nEl usuario interrumpión la operación de la aplicación.'
Messages.NO_ARGUMENTS = (
    'No se ha especificado un fichero de entrada para ser procesado.\n'
    '\n'
    'Arrastre y suelte un fichero de entrada sobre el icono de la aplicación, '
    'o proporcione el nombre del fichero como argumento.'
)
Messages.EMPTY_PROFILES = 'No hay perfiles definidos en el fichero de perfiles «%s».'
Messages.MISSING_PROFILES = 'No se encontró o no se pudo leer el fichero de perfiles «%s».'
Messages.PROFILES_WRONG_SYNTAX = 'Error de sintaxis «%s» leyendo el fichero de perfiles.\n%s'
Messages.SKIMMING_MARKER = '\nSacando las mantecas:'
Messages.UNSUPPORTED_SOURCE = 'La fuente «%s» no es de un tipo admitido.'
Messages.HANDLER_ERROR = 'Messages. ↪ ERROR, %s.'
Messages.INPUT_FILE_INVALID = 'El fichero de entrada es inválido (%s).'
Messages.INPUT_FILE_NOT_FOUND = 'No se encontró el fichero de entrada.'
Messages.INPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para leer el fichero de entrada.'
Messages.OUTPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para crear el fichero de salida.'


class HandlerErrors(StrEnum):
    """Errors for source handlers."""
    NO_METADATA = 'no hay metadatos'


try:
    if getattr(sys, 'frozen', False):
        SCRIPT_PATH = sys.executable
    else:
        SCRIPT_PATH = __file__
except NameError:
    sys.exit(Messages.INITIALIZATION_ERROR)
SCRIPT_PATH = Path(SCRIPT_PATH).resolve()
INIFILE_PATH = SCRIPT_PATH.with_suffix('.ini')
DEBUGFILE_PATH = Path(f'{SCRIPT_PATH.with_suffix("")}_debug_{TIMESTAMP}.txt')
LOGFILE_PATH = Path(f'{SCRIPT_PATH.with_suffix("")}_log_{TIMESTAMP}.txt')


# Accepted set of URL schemes
ACCEPTED_URL_SCHEMES = ('https', 'http', 'file')

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
    """Raise when an input source has an unsupported type."""
    def __init__ (self, source):
        self.source = source

class InvalidSourceError(Exception):
    """Raise when an input source is invalid, damaged, etc."""
    def __init__ (self, reason):
        self.reason = reason


def error(message, *args, **kwargs):
    """Helper for prepending a header to error messages."""
    logging.error(f'{Messages.ERROR_HEADER}{message}', *args, **kwargs)


def warning(message, *args, **kwargs):
    """Helper for prepending a header to warning messages."""
    logging.warning(f'{Messages.WARNING_HEADER}{message}', *args, **kwargs)


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
    return Path(re.sub(r'\W', '_', url, re.ASCII))  # Quite crude but it works.


def is_accepted_url(value):
    """Check if value is an accepted URL or not."""
    # The check is quite crude but works for the application's needs.
    try:
        return urlparse(value).scheme in ACCEPTED_URL_SCHEMES
    except ValueError:
        return False


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


def single_url_handler(url):
    """
    Handle single URLs.

    The metadata for the URL is logged with INFO level, so it will be printed on
    stdout and the corresponding log files, and it is also written into a dump
    file named after the URL (properly sanitized), as key-value pairs.

    The output file has UTF-8 encoding.
    """
    if is_accepted_url(url):
        metadata = yield url
        yield
        if metadata:
            sink_filename = url_to_filename(url).with_suffix('.txt')
            with open(sink_filename, 'w+', encoding='utf-8') as sink:
                logging.debug('Volcando metadatos a «%s».', sink_filename)
                sink.write(f'{url}\n')
                for key, value in metadata.items():
                    message = f'      {key}: {value}'
                    logging.info(message)  # Output allowed here because it is part of the handler.
                    sink.write(f'{message}\n')


def textfile_handler(source_filename):
    """
    Handle text files containing URLs, one per line.

    The metadata for each URL is dumped into another text file, named after the
    source file: first the URL is written, then the metadata as key-value pairs.
    Barely pretty-printed, but it is more than enough for a dump.

    All files are assumed to have UTF-8 encoding.
    """
    sink_filename = source_filename.with_stem(source_filename.stem + '_out')
    with open(source_filename, encoding='utf-8') as source:
        with open(sink_filename, 'w', encoding='utf-8') as sink:
            logging.debug('Volcando metadatos a «%s».', sink_filename)
            for url in source.readlines():
                url = url.strip()
                if not is_accepted_url(url):
                    continue
                metadata = yield url
                yield
                if metadata:
                    sink.write(f'{url}\n')
                    for key, value in metadata.items():
                        logging.debug('Añadiendo metadato «%s» con valor «%s».', key, value)
                        sink.write(f'  {key}: {value}\n')
                    sink.write('\n')


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
    sink_filename = source_filename.with_stem(source_filename.stem + '_out')
    logging.debug('Copiando workbook a «%s».', sink_filename)

    copy2(source_filename, sink_filename)
    try:
        source_workbook = load_workbook(source_filename)
    except (KeyError, BadZipFile) as exc:
        details = str(exc).strip('"')
        details = details[0].lower() + details[1:]
        logging.error('Invalid spreadsheet file (%s): %s.', type(exc).__name__, details)
        raise InvalidSourceError(type(exc).__name__) from exc
    sink_workbook = load_workbook(sink_filename)

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


def get_url_from_row(row):
    """Find first URL in row."""
    url = None
    for cell in row:
        if cell.data_type != 's':
            logging.debug('La celda «%s» no es de tipo cadena, será ignorada.', cell.coordinate)
            continue
        if is_accepted_url(cell.value):
            logging.debug('Se encontró un URL en la celda «%s»: %s', cell.coordinate, cell.value)
            url = cell.value
            break  # Only the FIRST URL found in each row is considered.
    return url


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
        key = '[sm] ' + key
        if key not in static.known_metadata:
            logging.debug('Se encontró un metadato nuevo, «%s».', key)
            column = sheet.max_column + 1
            static.known_metadata[key] = column
            logging.debug('El metadato «%s» irá en la columna «%s».', key, get_column_letter(column))
            cell = sheet.cell(row=1, column=column, value=key)
            cell.font = Font(name='Calibri')
            cell.fill = PatternFill(start_color='baddad', fill_type='solid')
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


def resolve_file_url(url):
    """Resolve relative paths in file: url."""
    parsed_url = urlparse(url)
    resolved_path = unquote(parsed_url.path[1:])
    resolved_path = Path(resolved_path).resolve().as_posix()
    resolved_path = quote(resolved_path, safe=':/')
    return parsed_url._replace(path=resolved_path).geturl()


def get_redirected_url(base_url, contents):
    """
    Get redirected URL from a meta http-equiv="refresh" pragma if that pragma is
    in contents. Use base_url as base URL for redirection, if some URL parts are
    missing in the URL specified by the refresh pragma.
    """
    if match := re.search(META_REFRESH_RE, contents, re.I):
        base_url = urlparse(base_url)
        redirected_url = urlparse(match.group(1).decode('ascii'))
        for field in redirected_url._fields:
            value = getattr(redirected_url, field)
            # If not specified in the redirected URL, both the scheme and netloc
            # will be reused from the base URL. Any other field will be obtained
            # from the redirected URL and used, no matter if it is empty.
            if value or field not in ('scheme', 'netloc'):
                base_url = base_url._replace(**{field: value})
        base_url = urlunparse(base_url)
    return base_url


def saca_las_mantecas(url):
    """."""
    return {'key_1': 'value_1', 'key_2': 'value_2', 'key_3': 'value_3'}


def parse_sources(sources):
    """
    Parse each argument in args to check if it is a valid source, identify its
    type and build the corresponding handler.

    Yield built source object.

    Raises UnsupportedSourceError(source) for unsupported sources types.
    """
    for source in sources:
        logging.debug('Procesando argumento «%s».', source)

        handler = None
        if is_accepted_url(source):
            logging.debug('La fuente es un URL.')
            handler = single_url_handler(source)
        elif source.endswith('.txt'):
            logging.debug('La fuente es un fichero de texto.')
            handler = textfile_handler(Path(source))
        elif source.endswith('.xlsx'):
            logging.debug('La fuente es una hoja de cálculo.')
            handler = spreadsheet_handler(Path(source))
        else:
            logging.debug('El argumento no es un tipo de fuente admitido.')
            raise UnsupportedSourceError(source)
        yield source, handler


def loggerize(function):
    """Decorator which enables logging for function."""
    def loggerize_wrapper(*args, **kwargs):
        setup_logging(LOGFILE_PATH, DEBUGFILE_PATH)

        logging.debug(Messages.DEBUGGING_INIT)
        logging.info(Messages.APP_INIT)
        logging.debug(Messages.USER_AGENT)

        status = function(*args, **kwargs)

        logging.info(Messages.APP_DONE)
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
            return ExitCodes.KEYBOARD_INTERRUPT
    return handle_keyboard_interrupt_wrapper


@loggerize
@keyboard_interrupt_handler
def main(sources):
    """."""
    exitcode = ExitCodes.SUCCESS

    if len(sources) == 0:
        # The input sources should be provided automatically if the application
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
        for source, handler in parse_sources(sources):
            logging.info('  Fuente: %s', source)
            try:
                for url in handler:
                    logging.info('    %s', url)
                    metadata = saca_las_mantecas(url)
                    handler.send(metadata)
                    if metadata is None:
                        logging.info(Messages.HANDLER_ERROR, HandlerErrors.NO_METADATA)
                        logging.debug('ERROR, %s.', HandlerErrors.NO_METADATA)
            except InvalidSourceError as exc:
                warning(Messages.INPUT_FILE_INVALID, exc.reason)
                exitcode = ExitCodes.WARNING
    except UnsupportedSourceError as exc:
        warning(Messages.UNSUPPORTED_SOURCE, exc.source)
        exitcode = ExitCodes.WARNING
    except FileNotFoundError:
        warning(Messages.INPUT_FILE_NOT_FOUND)
        exitcode = ExitCodes.WARNING
    except PermissionError as exc:
        if exc.filename == str(source):
            warning(Messages.INPUT_FILE_NO_PERMISSION)
        else:
            warning(Messages.OUTPUT_FILE_NO_PERMISSION)
        exitcode = ExitCodes.WARNING

    return exitcode


atexit.register(wait_for_keypress)
sys.excepthook = excepthook
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
