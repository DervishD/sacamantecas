#! /usr/bin/env python3
"""
Saca las Mantecas.

This program processes "Mantecas", which are URIs pointing to an entry within
some bibliographic catalogue where book metadata can be obtained, by accessing
the URI, getting that metadata and producing the proper output.

In short, it "saca las mantecas"…

The input can be:

- an Excel file (xls/xlsx), containing a list of book titles, each one with its
signature and Manteca. In this case the output will be another Excel file
containing the original data and extra columns with the retrieved metadata.

- a text file containing a list of Mantecas. In this mode of operation the
output file will be another text file containing the retrieved metadata for each
entry.

- a list of Manteca URIs provided as command line arguments. In this case the
metadata is directly written to the console and dumped to an output file.

In addition to this, if any of the sources is prepended with the fake URI scheme
"dump://", then the contents are not processed, but dumped to files so they can
be used as testing sources in the future.

A Manteca can be ANY kind of URI scheme supported by urllib.

The Mantecas are processed according to profiles, which indicate how to properly
process the retrieved contents from the URIs, depending on the bibliographic
catalogue which is being processed. The proper profile is inferred from the URI
itself and resides in the configuration file (sacamantecas.ini).
"""

__version__ = 'v4.4'

import configparser
import sys
from pathlib import Path
import errno
import logging
import atexit
from logging.config import dictConfig
import traceback as tb
from shutil import copy2
from urllib.request import urlopen, Request
from urllib.parse import urlparse, urlunparse, quote, unquote
from urllib.error import URLError
from http.client import HTTPException
import re
import time
import platform
from html.parser import HTMLParser
from msvcrt import getch, get_osfhandle
from ctypes import WinDLL, byref, c_uint, create_unicode_buffer, wintypes
from zipfile import BadZipFile
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.exceptions import SheetTitleException, InvalidFileException
from openpyxl.utils.cell import get_column_letter

TIMESTAMP = time.strftime('%Y%m%d_%H%M%S')
try:
    if getattr(sys, 'frozen', False):
        PROGRAM_PATH = sys.executable
    else:
        PROGRAM_PATH = __file__
except NameError:
    sys.exit('Error de inicialización del programa.')
PROGRAM_PATH = Path(PROGRAM_PATH).resolve()
PROGRAM_NAME = PROGRAM_PATH.stem + ' ' + __version__
INIFILE_PATH = PROGRAM_PATH.with_suffix('.ini')
USER_AGENT = f'{PROGRAM_NAME.replace(" v", "/")} +https://github.com/DervishD/sacamantecas'
USER_AGENT += f' (Windows {platform.version()}; {platform.architecture()[0]}; {platform.machine()})'
DUMPMODE_PREFIX = 'dump://'
EXITCODE_FAILURE = 1
EXITCODE_SUCCESS = 0


if sys.platform != 'win32':
    sys.exit(f'{PROGRAM_NAME} solo funciona en la plataforma Win32.')


# Needed for having VERY basic logging when the code is imported rather than run.
logging.basicConfig(level=logging.NOTSET, format='%(levelname).1s %(message)s', force=True)


# Reconfigure standard output streams so they use UTF-8 encoding, no matter if
# they are redirected to a file when running the program from a shell.
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


def wait_for_keypress():
    """Wait for a keypress to continue if sys.stdout is a real console AND the console is transient."""
    # If no console is attached, then the program must NOT pause.
    #
    # Since sys.stdout.isatty() returns True under Windows when sys.stdout is
    # redirected to NUL, another, more complicated method, is needed here.
    # The test below has been adapted from https://stackoverflow.com/a/33168697
    if not WinDLL('kernel32').GetConsoleMode(get_osfhandle(sys.stdout.fileno()), byref(c_uint())):
        return

    # If there is a console attached, the program must pause ONLY if that
    # console will automatically close when the program finishes, hiding
    # any messages printed by the program. In other words, pause only if
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
    elif console_title.find(PROGRAM_PATH.name) != -1:
        return

    print('\nPulse cualquier tecla para continuar...', end='', flush=True)
    getch()


def error(message):
    """Show the error message on stderr and the debug logfile."""
    print(f'\n*** Error en {PROGRAM_NAME}\n', file=sys.stderr)
    logging.error(message)


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
        message += PROGRAM_PATH.name if frame.name == '<module>' else frame.name
        message += ']'
        message += f': {frame.line}' if frame.line else ''
        message += '\n'
    error(message.rstrip())


class MantecaSource():
    """Abstract class to define an interface for Manteca sources."""
    def __init__(self, source):
        self.source = source

    def get_mantecas(self):
        """ Pure virtual function: get Mantecas from source."""
        raise NotImplementedError()

    def close(self):
        """ Pure virtual function: close Manteca source."""
        raise NotImplementedError()


class SkimmedSink():
    """Abstract class to define an interface for Skimmed sinks."""
    def __init__(self, sink):
        self.sink = sink

    def add_metadata(self, row, uri, metadata):
        """Pure virtual function: add metadata to Skimmed sink."""
        raise NotImplementedError()

    def close(self):
        """ Pure virtual function: close Skimmed sink."""
        raise NotImplementedError()


class MantecaExcel(MantecaSource):
    """A class to represent Manteca Excel workbooks."""

    def __init__(self, *args, **kwargs):
        """Load the input Excel workbook."""
        super().__init__(*args, **kwargs)
        self.workbook = load_workbook(self.source)
        # NOTE: not all sheets are processed, only the first one because it is
        # (allegedly) the one where the Manteca URIs for the items are.
        self.sheet = self.workbook.worksheets[0]
        logging.debug('La hoja con la que se trabajará es «%s»".', self.sheet.title)

    def get_mantecas(self):
        """
        Get the Mantecas found in the default worksheet.

        Returns a generator of (row, URI) tuples.

        Only the FIRST URI found in each row is considered and returned.
        """
        for row in self.sheet.rows:
            logging.debug('Procesando fila %s.', row[0].row)
            for cell in row:
                if cell.data_type != 's':
                    logging.debug('La celda «%s» no es de tipo cadena, será ignorada.', cell.coordinate)
                    continue
                if urlparse(cell.value).scheme.startswith(('http', 'file')):
                    logging.debug('Se encontró un URI en la celda «%s»: %s', cell.coordinate, cell.value)
                    yield cell.row, cell.value
                    break

    def close(self):
        """Close the current workbook."""
        self.workbook.close()
        logging.debug('Fichero de Manteca cerrado.')


class SkimmedExcel(SkimmedSink):
    """A class to represent Skimmed (with 0% Manteca) Excel workbooks."""
    def __init__(self, *args, **kwargs):
        """Load the output Excel workbook."""
        super().__init__(*args, **kwargs)
        self.workbook = load_workbook(self.sink)
        self.metadata_columns = {}
        self.heading_style = {
            'font': Font(name='Calibri'),
            'fill': PatternFill(start_color='baddad', fill_type='solid'),
        }
        # NOTE: not all sheets are processed, only the first one because it is
        # (allegedly) the one where the Manteca URIs for the items are.
        self.sheet = self.workbook.worksheets[0]
        logging.debug('La hoja con la que se trabajará es «%s»".', self.sheet.title)
        logging.debug('Insertando fila de cabeceras.')
        self.sheet.insert_rows(1, 1)

    def add_metadata(self, row, uri, metadata):
        """
        Add all specified metadata to the default worksheet, at row.

        The metadata is a list of key-value pairs.

        Each value will be added in a new column if the key doesn't already
        exists on the sheet, at the specified row. The uri is not used.

        Adds the header and styles it, also, if it doesn't exist.

        NOTE: the styling is just a best effort, and it's fragile. It depends on
        the sheet having headers on the first row, and the style used is that of
        the FIRST header.
        """
        logging.debug('Añadiendo metadatos para «%s».', uri)
        for key, value in metadata.items():
            key = '[sm] ' + key
            if key not in self.metadata_columns:
                logging.debug('Se encontró un metadato nuevo, «%s».', key)
                column = self.sheet.max_column + 1
                self.metadata_columns[key] = column
                logging.debug('El metadato «%s» irá en la columna «%s».', key, get_column_letter(column))
                cell = self.sheet.cell(row=1, column=column, value=key)
                cell.font = self.heading_style['font']
                cell.fill = self.heading_style['fill']
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
                self.sheet.column_dimensions[get_column_letter(column)].width = 42
                # This is needed because sometimes Excel files are not properly
                # generated and the last column has a 'max' field too large, and
                # that has an unintended consequence: ANY change to the settings
                # of that column affects ALL the following ones whose index is
                # less than 'max'… So, it's better to fix that field.
                self.sheet.column_dimensions[get_column_letter(column)].max = column
            logging.debug('Añadiendo metadato «%s» con valor «%s».', key, value)
            # Since a heading row is inserted, the rows where metadata has to go
            # have now an +1 offset, as they have been displaced.
            self.sheet.cell(row+1, self.metadata_columns[key], value=value)

    def close(self):
        """Close the current workbook, saving it."""
        self.workbook.save(self.sink)
        self.workbook.close()
        logging.debug('Workbook Excel guardado.')
        logging.debug('Fichero sin Manteca cerrado.')


class MantecaText(MantecaSource):
    """A class to represent Manteca text files."""
    def __init__(self, *args, **kwargs):
        """Load the input text file."""
        super().__init__(*args, **kwargs)
        self.file = open(self.source, encoding='utf-8')

    def get_mantecas(self):
        """
        Get the Mantecas found in the text file.

        Yield (row, URI) tuples, one per non empty file line.
        """
        for row, uri in enumerate(self.file.readlines(), start=1):
            uri = uri.strip()
            if uri:
                yield row, uri

    def close(self):
        """Close the file."""
        self.file.close()
        logging.debug('Fichero de Manteca cerrado.')


class SkimmedText(SkimmedSink):
    """A class to represent Skimmed (with 0% Manteca) text files."""
    def __init__(self, *args, **kwargs):
        """Create the output text file."""
        super().__init__(*args, **kwargs)
        self.file = open(self.sink, 'w', encoding='utf-8')

    def add_metadata(self, row, uri, metadata):
        """
        Add all specified metadata to this Skimmed text file.

        The metadata is a list of key-value pairs.

        The row parameter is not used as a location where the data will be
        added, since those are the file lines, and will be consecutive anyway.
        The row parameter will be added at the beginning of each line as a
        reference only, followed by uri.

        Then, more or less pretty-print the metadata.
        """
        logging.debug('Añadiendo metadatos para «%s».', uri)
        self.file.write(f'[{row}] {uri}\n')
        for key, value in metadata.items():
            self.file.write(f'    {key}: {value}\n')

    def close(self):
        """Close the file."""
        self.file.close()
        logging.debug('Fichero sin Manteca cerrado.')


class MantecaURI(MantecaSource):
    """A class to represent Manteca single URIs."""
    def get_mantecas(self):
        """
        Get the Mantecas found in the URI, that is… the URI itself.

        Yield (row, URI) tuples, but row is always 1 and the generator stops
        after only one iteration, of course.
        """
        yield 1, self.source

    def close(self):
        """NOP"""


class SkimmedURI(SkimmedSink):
    """A class to represent Skimmed (with 0% Manteca) single URIs."""
    def add_metadata(self, row, uri, metadata):
        """
        Print specified metadata to stdout.

        The metadata is a list of key-value pairs.

        The row parameter is ignored, the rest of the metatata is somewhat
        pretty-printed after the URI itself.

        In addition to this, the metadata is dumped to the output file, too.
        """
        logging.debug('Añadiendo metadatos para «%s».', uri)
        with open(self.sink, 'w', encoding='utf-8') as sink:
            logging.debug('Volcando metadatos a «%s».', self.sink)
            sink.write(f'{uri}\n')
            for key, value in metadata.items():
                message = f'    {key}: {value}'
                print(message)
                sink.write(f'{message}\n')

    def close(self):
        """NOP"""


class BaseParser(HTMLParser):
    """Base class for catalogue parsers."""
    URI_REGEX = 'uri'
    NEEDED_KEYS = set()
    METADATA_SEPARATOR = ' === '
    EMPTY_KEY_LABEL = '[vacío]'

    @classmethod
    def is_parser_for_profile(cls, profile):
        """
        Check if this parser can parse profile.

        For now, a parser can parse a profile if its NEEDED_KEYS set is exactly
        the same as the profile.keys(), ignoring URI_REGEX key as it is unused
        in the parsers but present in all of the profiles anyway.
        """
        return (cls.NEEDED_KEYS | {BaseParser.URI_REGEX}) == profile.keys()

    def __init__(self, profile, *args, **kwargs):
        """Initialize object."""
        super().__init__(*args, **kwargs)
        self.profile = profile
        self.within_k = False
        self.within_v = False
        self.current_k = ''
        self.current_v = ''
        self.last_k = ''
        self.retrieved_metadata = {}

    def handle_starttag(self, tag, attrs):
        """Handle opening tags."""
        logging.debug('➜ HTML <%s%s%s>', tag, ' ' * bool(attrs), ' '.join((f'{k}="{v}"' for k, v in attrs)))

    def handle_data(self, data):
        """Handle data."""
        if self.within_k or self.within_v:
            # Clean up the received data by removing superfluous whitespace
            # characters, including newlines, carriage returns, etc.
            data = ' '.join(data.split())
            if not data:
                return
        if self.within_k:
            logging.debug('Se encontró la clave «%s».', data)
            self.current_k += data.rstrip(':')
            self.last_k = self.current_k
            return
        if self.within_v:
            logging.debug('Se encontró un valor «%s».', data)
            if self.current_v:
                self.current_v += ' / '
            self.current_v += data
            return

    def store_metadata(self):
        """Store found metadata, handling missing parts."""
        if not self.current_k and not self.current_v:
            logging.debug('Metadato vacío.')
        if self.current_k and not self.current_v:
            logging.debug('Metadato «%s» incompleto, ignorando.', self.current_k)
        if not self.current_k and self.current_v:
            self.current_k = self.last_k if self.last_k else BaseParser.EMPTY_KEY_LABEL
        if self.current_k and self.current_v:
            if self.current_k not in self.retrieved_metadata:
                self.retrieved_metadata[self.current_k] = []
            # A set is not used instead of the code below, to preserve order.
            if self.current_v not in self.retrieved_metadata[self.current_k]:
                self.retrieved_metadata[self.current_k].append(self.current_v)
        self.current_k = ''
        self.current_v = ''

    def get_metadata(self):
        """Get retrieved metadata so far."""
        metadata = {}
        for key, value in self.retrieved_metadata.items():
            metadata[key] = BaseParser.METADATA_SEPARATOR.join(value)
        return metadata

    def error(self, _):
        """Override ParserBase abstract method."""


class OldRegimeParser(BaseParser):
    """
    Parser for Old Regime Manteca URIs which use different HTML class attributes
    to mark metadata keys and metadata values.

    This is inherently complex, specially when dealing with ill-formed HTML.

    So, in order to keep this parser as simple as possible, some assumptions are
    made. See the comments below to know which those are.
    """
    K_CLASS_REGEX = 'k_class'
    V_CLASS_REGEX = 'v_class'
    NEEDED_KEYS = {K_CLASS_REGEX, V_CLASS_REGEX}

    def __init__(self, *args, **kwargs):
        """Initialize object."""
        super().__init__(*args, **kwargs)
        self.current_k_tag = None
        self.current_v_tag = None

    def handle_starttag(self, tag, attrs):
        """Handle opening tags."""
        super().handle_starttag(tag, attrs)
        for attr in attrs:
            if attr[0] == 'class' and (match := self.profile[self.K_CLASS_REGEX].search(attr[1])):
                logging.debug('Se encontró una marca de clave «%s».', match.group(0))
                self.within_k = True
                self.current_k = ''
                self.current_k_tag = tag
                if self.within_v:
                    # If still processing a value, notify about the nesting error
                    # but reset parser so everything starts afresh, like if a new
                    # key had been found.
                    logging.debug('Problema de anidación (clave dentro de valor), restableciendo parser.')
                    self.within_v = False
                    self.current_v = ''
                    self.current_v_tag = None
                break
            if attr[0] == 'class' and (match := self.profile[self.V_CLASS_REGEX].search(attr[1])):
                logging.debug('Se encontró una marca de valor «%s».', match.group(0))
                self.within_v = True
                self.current_v = ''
                self.current_v_tag = tag
                if self.within_k:
                    # If still processing a key, the nesting error can still be
                    # recovered up to a certain point. If some data was obtained
                    # for the key, the parser is put in within_v mode to get the
                    # corresponding value. Otherwise the parser is reset.
                    logging.debug('Problema de anidación (valor dentro de clave), restableciendo parser.')
                    self.within_k = False
                    self.current_k_tag = None
                    if not self.current_k:
                        self.within_v = False
                        self.current_v_tag = None
                break

    def handle_endtag(self, tag):
        """Handle closing tags."""
        if self.within_k and tag == self.current_k_tag:
            self.within_k = False
            self.current_k_tag = None
            return
        if self.within_v and tag == self.current_v_tag:
            self.within_v = False
            self.current_v_tag = None
            self.store_metadata()
            return


# cSpell:ignore Baratz
class BaratzParser(BaseParser):
    """
    Parser for Manteca URIs whose contents have been generated by the new Baratz
    frontend, which does not use HTML class attributes to mark metadata keys and
    values. Instead they have a <dl> HTML element with a particular class, which
    contains the metadata as a list of <dt>/<dd> pairs.

    Within that list, the <dt> HTML element contains the metadata key, whereas
    the <dd> HTML element containing the metadata value.
    """
    M_TAG = 'm_tag'
    M_ATTR = 'm_attr'
    M_VALUE = 'm_value'
    NEEDED_KEYS = {M_TAG, M_ATTR, M_VALUE}

    def __init__(self, *args, **kwargs):
        """Initialize object."""
        super().__init__(*args, **kwargs)
        self.within_meta = False

    def handle_starttag(self, tag, attrs):
        """Handle opening tags."""
        super().handle_starttag(tag, attrs)
        if not self.within_meta:
            if not self.profile[self.M_TAG].fullmatch(tag):
                return
            for attr in attrs:
                if self.profile[self.M_ATTR].fullmatch(attr[0]) and self.profile[self.M_VALUE].search(attr[1]):
                    logging.debug('Se encontró una marca de metadato «%s».', attr[1])
                    self.within_meta = True
                    return
        else:
            if tag == 'dt':
                self.within_k = True
                logging.debug('Se encontró un elemento de clave «%s».', tag)
                return
            if tag == 'dd':
                self.within_v = True
                logging.debug('Se encontró un elemento de valor «%s».', tag)
                return

    def handle_endtag(self, tag):
        """Handle closing tags."""
        if self.within_meta and self.profile[self.M_TAG].fullmatch(tag):
            self.within_meta = False
            return
        if self.within_k and tag == 'dt':
            self.within_k = False
            return
        if self.within_v and tag == 'dd':
            self.within_v = False
            self.store_metadata()
            return


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

            if record.message.strip() == '':
                return message.strip()

            preamble = message.split(record.message)[0]
            # Return cleaned up message: no multiple newlines, no trailing spaces,
            # and the preamble is inserted at the beginning of each line.
            return f'\n{preamble}'.join([line.rstrip() for line in message.splitlines() if line.strip()])

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
                'format': '{message}',
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


def parse_sources(sources):
    """
    Process arguments contained in the argv list.

    For each argument identify the type of source and generate the corresponding
    manteca source and skimmed sink names taking into account if the source must
    be dumped or processed normally.

    The source is 'munged' in the returned tuple, that is, preprocessed and
    normalized so it resembles a normal source instead of a 'dumpable' one.

    Yield (source_type, source_name, sink_name, dumpmode) tuples.

    For invalid sources the tuple is (None, source_name, None, dumpmode).
    """
    for source in sources:
        logging.debug('Procesando fuente de Manteca «%s».', source)

        dumpmode = source.startswith(DUMPMODE_PREFIX)
        source = source.removeprefix(DUMPMODE_PREFIX)

        source_type = None
        source_name = source
        sink_name = None
        if re.match(r'(?:https?|file)://', source):
            logging.debug('La fuente es un URI.')
            source_type = 'uri'
            source_name = Path(source)
            sink_name = Path(re.sub(r'\W', '_', source, re.ASCII) + '.txt')
        elif source.endswith('.txt'):
            logging.debug('La fuente es un fichero de texto.')
            source_type = 'txt'
            source_name = Path(source)
            sink_name = Path(source)
        elif source.endswith('.xlsx'):
            logging.debug('La fuente es un fichero Excel.')
            source_type = 'xls'
            source_name = Path(source)
            sink_name = Path(source)
        sink_name = None if sink_name is None else sink_name.with_stem(sink_name.stem + '_out')
        yield source_type, source_name, sink_name, dumpmode


def retrieve_uri(uri):
    """
    Retrieve contents from uri.

    First resolve meta-refresh redirection for uri, then get the contents and
    decode them using the detected charset, or iso-8859-1 if no charset is
    detected.

    Return a tuple whose first element are the decoded contents and the second
    element is the charset detected (or the default one if none is found).

    NOTE about charset: if no charset is detected, then iso-8859-1 is used as
    default. Really, utf-8 should be a better default, because modern web pages
    may NOT specify any encoding if they are using utf-8 and it is identical to
    ascii in the 7-bit codepoints. The problem is that utf-8 will fail for pages
    encoded with iso-8859-1, and the vast majority of web pages processed which
    does not specify a charset in fact will be using iso-8859-1 anyway.
    """
    if uri.startswith('file://'):
        uri = urlparse(uri)
        if not uri.netloc:
            # Remember that uri.path ALWAYS starts with '/', must be ignored.
            uri = uri._replace(path=quote(str(Path(unquote(uri.path[1:])).resolve().as_posix()), safe=':/'))
        uri = urlunparse(uri)
    try:
        with urlopen(Request(uri, headers={'User-Agent': USER_AGENT})) as request:
            # First, check if any redirection is needed and get the charset the easy way.
            logging.debug('Procesando URI «%s».', uri)
            contents = request.read()
            charset = request.headers.get_content_charset()
            match = re.search(rb'<meta http-equiv="refresh" content="[^;]+;\s*url=([^"]+)"', contents, re.I)
            if match:
                uri = urlparse(uri)
                uri = urlunparse((uri.scheme, uri.netloc, match.group(1).decode('ascii'), '', '', ''))
                logging.debug('Redirección -> «%s».', uri)
                with urlopen(Request(uri, headers={'User-Agent': USER_AGENT})) as redirected_request:
                    contents = redirected_request.read()
                    charset = redirected_request.headers.get_content_charset()
            else:
                logging.debug('El URI no está redirigido.')
    except ValueError as exc:
        if str(exc).startswith('unknown url type:'):
            raise URLError(f"El URI '{uri}' es de tipo desconocido.") from exc
        raise

    # In this point, we have the contents as a byte string.
    # If the charset is None, it has to be determined the hard way.
    if charset is None:
        # Next best thing, from the meta http-equiv="content-type".
        match = re.search(rb'<meta http-equiv="content-type".*charset=([^"]+)"', contents, re.I)
        if match:
            logging.debug('Charset detectado mediante meta http-equiv.')
            charset = match.group(1).decode('ascii')
        else:
            # Last resort, from some meta charset, if any…
            match = re.search(rb'<meta charset="([^"]+)"', contents, re.I)
            if match:
                logging.debug('Charset detectado mediante meta charset.')
                charset = match.group(1).decode('ascii')
            else:
                charset = 'iso-8859-1'
                logging.error('Usando charset por defecto.')
    else:
        logging.debug('Charset detectado en las cabeceras.')
    logging.debug('Contenidos codificados con charset «%s».', charset)

    return contents.decode(charset), charset


def saca_las_mantecas(source, sink, profiles):
    """
    Saca las Mantecas (skims) from each source dumping metadata to sink.

    The profiles are used to properly perform the skimming, since that process
    depends on the particular profile matched by the Manteca being skimmed.

    The full process is to obtain the list of Mantecas from each source, then
    retrieving the contents from each URI and then get the metadata (that is,
    skim the Manteca) using the proper parser depending on the particular URI.
    """
    bad_metadata = []
    for row, uri in source.get_mantecas():
        logging.info('  %s', uri)
        profile_name = profile = None
        for profile_name, profile in profiles.items():
            if profile[BaseParser.URI_REGEX].search(uri):
                logging.debug('Perfil detectado: «%s».', profile_name)
                break
        else:
            logging.warning('No se detectó un perfil para «%s», ignorando.', uri)
            bad_metadata.append((uri, 'No existe perfil'))
            continue

        for child_parser in BaseParser.__subclasses__():
            if child_parser.is_parser_for_profile(profile):
                parser = child_parser(profile)
                logging.debug('Parser encontrado: «%s».', child_parser.__name__)
                break
        else:
            logging.debug('No se detectó un parser para el perfil «%s», ignorando «%s».', profile_name, uri)
            continue

        contents = None
        try:
            contents, charset = retrieve_uri(uri)
        except ConnectionError:
            logging.error('Error de conexión accediendo a «%s».', uri)
            bad_metadata.append((uri, 'No se pudo conectar'))
            continue
        except URLError as exc:
            logging.error('Error accediendo a «%s»: %s.', uri, exc.reason)
            bad_metadata.append((uri, 'No se pudo acceder'))
            continue
        except HTTPException as exc:
            logging.error('Error de descarga accediendo a «%s»: %s.', uri, type(exc).__name__)
            bad_metadata.append((uri, 'No se pudo descargar'))
            continue

        if not contents:
            logging.error('No se recibieron contenidos de «%s».', uri)
            bad_metadata.append((uri, 'No se recibieron contenidos'))
            continue

        if sink is None:  # Source must be dumped, not processed.
            dumpfilename = re.sub(r'\W', '_', uri, re.ASCII) + '.html'
            logging.debug('El fichero de volcado es «%s».', dumpfilename)
            with open(dumpfilename, 'wt', encoding=charset) as dumpfile:
                dumpfile.write(contents)
            logging.info('  Contenido volcado.')
        else:
            parser.feed(contents)
            parser.close()
            metadata = parser.get_metadata()
            if not metadata:
                bad_metadata.append((uri, 'No se obtuvieron metadatos'))
            else:
                sink.add_metadata(row, uri, metadata)
    source.close()
    if sink:
        sink.close()
    return bad_metadata


def loggerize(function):
    """Decorator which enables logging for function."""
    def loggerize_wrapper(*args, **kwargs):
        TIMESTAMP = ''
        debug_filename = f'{PROGRAM_PATH.with_suffix("")}_debug_{TIMESTAMP}.txt'
        log_filename = f'{PROGRAM_PATH.with_suffix("")}_log_{TIMESTAMP}.txt'

        setup_logging(log_filename, debug_filename)

        logging.info(PROGRAM_NAME)
        logging.debug(MESSAGES.DEBUGGING_INIT)
        logging.debug('User-Agent: «%s».', USER_AGENT)

        status = function(*args, **kwargs)

        logging.info('\nProceso terminado.')
        logging.debug('Registro de depuración finalizado.')
        logging.shutdown()
        return status
    return loggerize_wrapper


def keyboard_interrupt_handler(function):
    """Wraps function with a simple KeyboardInterrupt handler."""
    def handle_keyboard_interrupt_wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except KeyboardInterrupt:
            logging.warning('\nEl usuario interrumpió la operación del programa.')
            return EXITCODE_FAILURE
    return handle_keyboard_interrupt_wrapper


@loggerize
@keyboard_interrupt_handler
def main():
    """."""
    atexit.register(wait_for_keypress)

    sys.argv.pop(0)
    if len(sys.argv) == 0:
        # The input source should be provided automatically if the program
        # is used as a drag'n'drop target which is, in fact, the intended
        # method of operation.
        #
        # But the program can be also run by hand from a command prompt, so
        # it is better to signal the end user with an error and explanation
        # if the input source is missing, as soon as possible.
        error(
            'No se ha especificado un fichero de entrada para ser procesado.\n'
            '\n'
            'Arrastre y suelte un fichero de entrada sobre el icono del programa, '
            'o proporcione el nombre del fichero como argumento.'
        )
        return EXITCODE_FAILURE

    try:
        profiles = load_profiles(INIFILE_PATH)
        if not profiles:
            error('No hay perfiles definidos en el fichero de perfiles «{exc.filename}».')
            return EXITCODE_FAILURE
        logging.debug('Se obtuvieron los siguientes perfiles: %s.', list(profiles.keys()))
    except MissingProfilesError as exc:
        error(f'No se encontró o no se pudo leer el fichero de perfiles «{exc.filename}».')
        return EXITCODE_FAILURE
    except ProfilesSyntaxError as exc:
        error(f'Error de sintaxis «{exc.error}» leyendo el fichero de perfiles.\n{exc.details}')
        return EXITCODE_FAILURE

    logging.info('\nSacando las mantecas:')
    for source_type, source_name, sink_name, dumpmode in parse_sources(sys.argv):
        if dumpmode:
            logging.debug('La fuente de Manteca «%s» será volcada, no procesada.', source_name)
        print(source_type, source_name, sink_name, dumpmode)
        if source_type is None:
            logging.warning('La fuente «%s» no es de un tipo admitido.', source_name)
            continue


            logging.warning('Se encontraron problemas en los siguientes enlaces:')
    #         for uri, problem in bad_metadata:
                # logging.warning(f'  [{uri}] {problem}.')

    return EXITCODE_SUCCESS


sys.excepthook = excepthook
if __name__ == '__main__':
    sys.exit(main())
