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
metadata is directly written to the console (it can be redirected and written
into a text file if desired.)

The Mantecas are processed according to profiles, which indicate how to properly
process the retrieved contents from the URIs, depending on the bibliographic
catalogue which is being processed. The proper profile is inferred from the URI
itself and resides in the configuration file (sacamantecas.ini).
"""

# Current version…
__version__ = 'v3.3'

# Imports
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
import re
import time
import platform
from html.parser import HTMLParser
from msvcrt import getch
from zipfile import BadZipFile
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.exceptions import SheetTitleException, InvalidFileException
from openpyxl.utils.cell import get_column_letter


# sys.modules[__name__].__file__ is used to determine the program's fully
# qualified directory and filename, so if it's not defined for some reason
# (which may happen...) it's better to break execution here.
try:
    if getattr(sys, 'frozen', False):
        PROGRAM_PATH = sys.executable
    else:
        PROGRAM_PATH = __file__
    PROGRAM_PATH = Path(PROGRAM_PATH).resolve()
    PROGRAM_NAME = PROGRAM_PATH.stem + ' ' + __version__
    INIFILE_PATH = PROGRAM_PATH.with_suffix('.ini')
except NameError:
    sys.exit('Error de inicialización del programa.')


# Check if platform is win32 or not.
if sys.platform != 'win32':
    sys.exit(f'{PROGRAM_NAME} solo funciona en la plataforma Win32.')

# Create a sane User-Agent.
USER_AGENT = f'{PROGRAM_NAME.replace(" v", "/")} +https://github.com/DervishD/sacamantecas'
USER_AGENT += f' (Windows {platform.version()}; {platform.architecture()[0]}; {platform.machine()})'

# Prefix for 'dump mode', where input sources are dumped, not processed.
DUMPMODE_PREFIX = 'dump://'

# Wait for a keypress on program exit.
atexit.register(lambda: (print('\nPulse cualquier tecla para continuar...', end='', flush=True), getch()))


# Helper for pretty-printing error messages to stderr and the debug logfile.
def error(message):
    """Show the error 'message' on stderr and the debug logfile."""
    print(f'\n*** Error en {PROGRAM_NAME}\n{message}', file=sys.stderr)
    logging.debug(message)


################################################################################################
#                                                                                              #
#                                                                                              #
#                                                888    888                        888         #
#                                                888    888                        888         #
#                                                888    888                        888         #
#     .d88b.  888  888  .d8888b .d88b.  88888b.  888888 88888b.   .d88b.   .d88b.  888  888    #
#    d8P  Y8b `Y8bd8P' d88P"   d8P  Y8b 888 "88b 888    888 "88b d88""88b d88""88b 888 .88P    #
#    88888888   X88K   888     88888888 888  888 888    888  888 888  888 888  888 888888K     #
#    Y8b.     .d8""8b. Y88b.   Y8b.     888 d88P Y88b.  888  888 Y88..88P Y88..88P 888 "88b    #
#     "Y8888  888  888  "Y8888P "Y8888  88888P"   "Y888 888  888  "Y88P"   "Y88P"  888  888    #
#                                       888                                                    #
#                                       888                                                    #
#                                       888                                                    #
#                                                                                              #
#                                                                                              #
################################################################################################
# Define the default exception hook.
def excepthook(exc_type, exc_value, exc_traceback):
    """Handle unhandled exceptions, default exception hook."""
    message = '✱ '
    if isinstance(exc_value, OSError):
        # Handle OSError differently by giving more details.
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
        message += f'Excepción sin gestionar.\n«{exc_type.__name__}»: {exc_value}.\n'
    message += '\n'
    current_filename = None
    for frame in tb.extract_tb(exc_traceback):
        if current_filename != frame.filename:
            message += f'▸ Fichero {frame.filename}\n'
            current_filename = frame.filename
        message += f'  Línea {frame.lineno} ['
        message += PROGRAM_PATH.name if frame.name == '<module>' else frame.name
        message += ']'
        message += f': {frame.line}' if frame.line else ''  # No source content when frozen…
        message += '\n'
    error(message.rstrip())


##############################################################################################################
#                                                                                                            #
#                                                                                                            #
#    888888b.                                            888                                                 #
#    888  "88b                                           888                                                 #
#    888  .88P                                           888                                                 #
#    8888888K.   8888b.  .d8888b   .d88b.        .d8888b 888  8888b.  .d8888b  .d8888b   .d88b.  .d8888b     #
#    888  "Y88b     "88b 88K      d8P  Y8b      d88P"    888     "88b 88K      88K      d8P  Y8b 88K         #
#    888    888 .d888888 "Y8888b. 88888888      888      888 .d888888 "Y8888b. "Y8888b. 88888888 "Y8888b.    #
#    888   d88P 888  888      X88 Y8b.          Y88b.    888 888  888      X88      X88 Y8b.          X88    #
#    8888888P"  "Y888888  88888P'  "Y8888        "Y8888P 888 "Y888888  88888P'  88888P'  "Y8888   88888P'    #
#                                                                                                            #
#                                                                                                            #
##############################################################################################################
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


########################################################################################
#                                                                                      #
#                                                                                      #
#    8888888888                           888       .d888 d8b 888                      #
#    888                                  888      d88P"  Y8P 888                      #
#    888                                  888      888        888                      #
#    8888888    888  888  .d8888b .d88b.  888      888888 888 888  .d88b.  .d8888b     #
#    888        `Y8bd8P' d88P"   d8P  Y8b 888      888    888 888 d8P  Y8b 88K         #
#    888          X88K   888     88888888 888      888    888 888 88888888 "Y8888b.    #
#    888        .d8""8b. Y88b.   Y8b.     888      888    888 888 Y8b.          X88    #
#    8888888888 888  888  "Y8888P "Y8888  888      888    888 888  "Y8888   88888P'    #
#                                                                                      #
#                                                                                      #
########################################################################################
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

        Returns a generator of (row, URI) tuples. Only the FIRST URI found in
        each row is considered and returned.
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
        # Keys are metadata names, values are the column where that metadata is stored.
        self.metadata_columns = {}
        # Style for cells on the header row.
        self.heading_style = {
            'font': Font(name='Calibri'),
            'fill': PatternFill(start_color='baddad', fill_type='solid'),
        }
        # NOTE: not all sheets are processed, only the first one because it is
        # (allegedly) the one where the Manteca URIs for the items are.
        self.sheet = self.workbook.worksheets[0]
        logging.debug('La hoja con la que se trabajará es «%s»".', self.sheet.title)
        logging.debug('Insertando fila de cabeceras.')
        self.sheet.insert_rows(1, 1)  # Insert one row before first row.

    def add_metadata(self, row, uri, metadata):
        """
        Add all specified 'metadata' to the default worksheet, at 'row'.

        The 'metadata' is a list of 'key'-'value' pairs.

        Each 'value' will be added in a new column if the 'key' doesn't already
        exists on the sheet, at the specified 'row'. The 'uri' is not used.

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
                # workbook. So a column of width '10' would fit exactly 10 zero
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
            # Add the value to the proper column.
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


#################################################################################
#                                                                               #
#                                                                               #
#    88888888888                888          .d888 d8b 888                      #
#        888                    888         d88P"  Y8P 888                      #
#        888                    888         888        888                      #
#        888   .d88b.  888  888 888888      888888 888 888  .d88b.  .d8888b     #
#        888  d8P  Y8b `Y8bd8P' 888         888    888 888 d8P  Y8b 88K         #
#        888  88888888   X88K   888         888    888 888 88888888 "Y8888b.    #
#        888  Y8b.     .d8""8b. Y88b.       888    888 888 Y8b.          X88    #
#        888   "Y8888  888  888  "Y888      888    888 888  "Y8888   88888P'    #
#                                                                               #
#                                                                               #
#################################################################################
class MantecaText(MantecaSource):
    """A class to represent Manteca text files."""
    def __init__(self, *args, **kwargs):
        """Load the input text file."""
        super().__init__(*args, **kwargs)
        self.file = open(self.source, encoding='utf-8')  # pylint: disable=consider-using-with

    def get_mantecas(self):
        """
        Get the Mantecas found in the text file.

        Returns a generator of (row, URI) tuples, one per non empty file line.
        """
        for row, uri in enumerate(self.file.readlines(), start=1):
            uri = uri.strip()
            if uri:  # Do not return empty Mantecas.
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
        self.file = open(self.sink, 'w', encoding='utf-8')  # pylint: disable=consider-using-with

    def add_metadata(self, row, uri, metadata):
        """
        Add all specified 'metadata' to this Skimmed text file.

        The 'metadata' is a list of 'key'-'value' pairs.

        The 'row' parameter is not used as a location where the 'data' will be
        added, since those are the file lines, and will be consecutive anyway.
        The 'row' parameter will be added at the beginning of each line as a
        reference only, followed by 'uri'. Then, the metadata will be more or
        less pretty-printed.
        """
        logging.debug('Añadiendo metadatos para «%s».', uri)
        self.file.write(f'[{row}] {uri}\n')
        for key, value in metadata.items():
            self.file.write(f'    {key}: {value}\n')

    def close(self):
        """Close the file."""
        self.file.close()
        logging.debug('Fichero sin Manteca cerrado.')


################################################
#                                              #
#                                              #
#    888     888 8888888b.  8888888            #
#    888     888 888   Y88b   888              #
#    888     888 888    888   888              #
#    888     888 888   d88P   888  .d8888b     #
#    888     888 8888888P"    888  88K         #
#    888     888 888 T88b     888  "Y8888b.    #
#    Y88b. .d88P 888  T88b    888       X88    #
#     "Y88888P"  888   T88b 8888888 88888P'    #
#                                              #
#                                              #
################################################
class MantecaURI(MantecaSource):
    """A class to represent Manteca single URIs."""
    def get_mantecas(self):
        """
        Get the Mantecas found in the URI, that is… the URI itself.

        Returns a generator of (row, URI) tuples, but 'row' is always 1 and the
        generator stops after only one iteration, of course.
        """
        yield 1, self.source

    def close(self):
        """NOP"""


class SkimmedURI(SkimmedSink):
    """A class to represent Skimmed (with 0% Manteca) single URIs."""
    def add_metadata(self, row, uri, metadata):
        """
        Print specified 'metadata' to stdout.

        The 'metadata' is a list of 'key'-'value' pairs.

        The 'row' parameter is ignored, the rest of the metatata is somewhat
        pretty-printed after the URI itself.
        """
        logging.debug('Añadiendo metadatos para «%s».', uri)
        print(f'  Metadatos obtenidos para {uri}:')
        for key, value in metadata.items():
            print(f'    {key}: {value}')

    def close(self):
        """NOP"""


##############################################################
#                                                            #
#                                                            #
#    888888b.                                                #
#    888  "88b                                               #
#    888  .88P                                               #
#    8888888K.   8888b.  .d8888b   .d88b.                    #
#    888  "Y88b     "88b 88K      d8P  Y8b                   #
#    888    888 .d888888 "Y8888b. 88888888                   #
#    888   d88P 888  888      X88 Y8b.                       #
#    8888888P"  "Y888888  88888P'  "Y8888                    #
#                                                            #
#    8888888b.                                               #
#    888   Y88b                                              #
#    888    888                                              #
#    888   d88P 8888b.  888d888 .d8888b   .d88b.  888d888    #
#    8888888P"     "88b 888P"   88K      d8P  Y8b 888P"      #
#    888       .d888888 888     "Y8888b. 88888888 888        #
#    888       888  888 888          X88 Y8b.     888        #
#    888       "Y888888 888      88888P'  "Y8888  888        #
#                                                            #
#                                                            #
##############################################################
class BaseParser(HTMLParser):
    """Base class for catalogue parsers."""
    URI_REGEX = 'uri'
    NEEDED_KEYS = set()

    @classmethod
    def is_parser_for_profile(cls, profile):
        """
        Check if this parser can parse 'profile'.

        For now, a parser can parse a 'profile' if its 'NEEDED_KEYS' set is
        exactly the same as the profile.keys(), ignoring 'URI_REGEX' key as it
        is unused in the parsers but present in all of the profiles anyway.
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
        self.retrieved_metadata = {}

    def handle_data(self, data):
        """Handle data."""
        if self.within_k or self.within_v:
            # Clean up the received data by removing superfluous whitespace
            # characters, including newlines, carriage returns, etc.
            data = ' '.join(data.split())
            if not data:  # Ignore empty data
                return
        if self.within_k:
            logging.debug('Se encontró la clave «%s».', data)
            self.current_k += data.rstrip(':')
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
            logging.error('Metadato vacío.')
        if self.current_k and not self.current_v:
            logging.error('Metadato «%s» incompleto, ignorando.', self.current_k)
        if not self.current_k and self.current_v:  # Empty key, generate a name.
            self.current_k = '[vacío]'
        if self.current_k and self.current_v:
            self.retrieved_metadata[self.current_k] = self.current_v
        self.current_k = ''
        self.current_v = ''

    def get_metadata(self):
        """Get retrieved metadata so far."""
        return self.retrieved_metadata

    def error(self, _):
        """Override ParserBase abstract method."""


#########################################################################################
#                                                                                       #
#                                                                                       #
#     .d88888b.  888      888 8888888b.                   d8b                           #
#    d88P" "Y88b 888      888 888   Y88b                  Y8P                           #
#    888     888 888      888 888    888                                                #
#    888     888 888  .d88888 888   d88P .d88b.   .d88b.  888 88888b.d88b.   .d88b.     #
#    888     888 888 d88" 888 8888888P" d8P  Y8b d88P"88b 888 888 "888 "88b d8P  Y8b    #
#    888     888 888 888  888 888 T88b  88888888 888  888 888 888  888  888 88888888    #
#    Y88b. .d88P 888 Y88b 888 888  T88b Y8b.     Y88b 888 888 888  888  888 Y8b.        #
#     "Y88888P"  888  "Y88888 888   T88b "Y8888   "Y88888 888 888  888  888  "Y8888     #
#                                                     888                               #
#                                                Y8b d88P                               #
#                                                 "Y88P"                                #
#                                                                                       #
#    8888888b.                                                                          #
#    888   Y88b                                                                         #
#    888    888                                                                         #
#    888   d88P 8888b.  888d888 .d8888b   .d88b.  888d888                               #
#    8888888P"     "88b 888P"   88K      d8P  Y8b 888P"                                 #
#    888       .d888888 888     "Y8888b. 88888888 888                                   #
#    888       888  888 888          X88 Y8b.     888                                   #
#    888       "Y888888 888      88888P'  "Y8888  888                                   #
#                                                                                       #
#                                                                                       #
#########################################################################################
class OldRegimeParser(BaseParser):  # pylint: disable=unused-variable
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

    def handle_starttag(self, tag, attrs):
        """Handle opening tags."""
        for attr in attrs:
            if attr[0] == 'class' and (match := self.profile[self.K_CLASS_REGEX].search(attr[1])):
                # Key mark found.
                logging.debug('Se encontró una marca de clave «%s».', match.group(0))
                self.within_k = True
                self.current_k = ''
                if self.within_v:
                    # If still processing a value, notify about the nesting
                    # error but reset parser so everything starts afresh, like
                    # if a new key had been found.
                    logging.error('Error de anidación (clave dentro de valor), restableciendo parser.')
                    self.within_v = False
                    self.current_v = ''
                break
            if attr[0] == 'class' and (match := self.profile[self.V_CLASS_REGEX].search(attr[1])):
                # Value mark found.
                logging.debug('Se encontró una marca de valor «%s».', match.group(0))
                self.within_v = True
                self.current_v = ''
                if self.within_k:
                    # If still processing a key, the nesting error can still be
                    # recovered to a certain point. If some data was obtained
                    # for the key, the parser is put in 'within_v' mode to get
                    # the corresponding value. Otherwise the parser is reset.
                    logging.error('Error de anidación (valor dentro de clave), restableciendo parser.')
                    self.within_k = False
                    if not self.current_k:
                        self.within_v = False
                break

    def handle_endtag(self, tag):
        """Handle closing tags."""
        if self.within_k:
            self.within_k = False
            return
        if self.within_v:
            self.within_v = False
            self.store_metadata()
            return


##############################################################
#                                                            #
#                                                            #
#    888888b.                            888                 #
#    888  "88b                           888                 #
#    888  .88P                           888                 #
#    8888888K.   8888b.  888d888 8888b.  888888 88888888     #
#    888  "Y88b     "88b 888P"      "88b 888       d88P      #
#    888    888 .d888888 888    .d888888 888      d88P       #
#    888   d88P 888  888 888    888  888 Y88b.   d88P        #
#    8888888P"  "Y888888 888    "Y888888  "Y888 88888888     #
#                                                            #
#    8888888b.                                               #
#    888   Y88b                                              #
#    888    888                                              #
#    888   d88P 8888b.  888d888 .d8888b   .d88b.  888d888    #
#    8888888P"     "88b 888P"   88K      d8P  Y8b 888P"      #
#    888       .d888888 888     "Y8888b. 88888888 888        #
#    888       888  888 888          X88 Y8b.     888        #
#    888       "Y888888 888      88888P'  "Y8888  888        #
#                                                            #
#                                                            #
##############################################################
class BaratzParser(BaseParser):  # pylint: disable=unused-variable
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
        if not self.within_meta:
            if not self.profile[self.M_TAG].fullmatch(tag):
                return
            for attr in attrs:
                if self.profile[self.M_ATTR].fullmatch(attr[0]) and self.profile[self.M_VALUE].search(attr[1]):
                    logging.debug('Se encontró una marca de metadato «%s».', attr[1])
                    self.within_meta = True
                    return
        else:  # We are now processing the key, value pairs.
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


#################################################################################################################
#                                                                                                               #
#                                                                                                               #
#                      888                              888                            d8b                      #
#                      888                              888                            Y8P                      #
#                      888                              888                                                     #
#    .d8888b   .d88b.  888888 888  888 88888b.          888  .d88b.   .d88b.   .d88b.  888 88888b.   .d88b.     #
#    88K      d8P  Y8b 888    888  888 888 "88b         888 d88""88b d88P"88b d88P"88b 888 888 "88b d88P"88b    #
#    "Y8888b. 88888888 888    888  888 888  888         888 888  888 888  888 888  888 888 888  888 888  888    #
#         X88 Y8b.     Y88b.  Y88b 888 888 d88P         888 Y88..88P Y88b 888 Y88b 888 888 888  888 Y88b 888    #
#     88888P'  "Y8888   "Y888  "Y88888 88888P" 88888888 888  "Y88P"   "Y88888  "Y88888 888 888  888  "Y88888    #
#                                      888                                888      888                   888    #
#                                      888                           Y8b d88P Y8b d88P              Y8b d88P    #
#                                      888                            "Y88P"   "Y88P"                "Y88P"     #
#                                                                                                               #
#                                                                                                               #
#################################################################################################################
def setup_logging():
    """
    Sets up logging system, disabling all existing loggers.

    With the current configuration ALL logging messages are sent to the debug
    file, logging.INFO messages are sent to the log file (timestamped), and the
    console (but not timestamped in this case).
    """
    # Get timestamp as soon as possible.
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    debugfile = f'{PROGRAM_PATH.with_suffix("")}_debug_{timestamp}.txt'
    logfile = f'{PROGRAM_PATH.with_suffix("")}_log_{timestamp}.txt'

    class MultilineFormatter(logging.Formatter):
        """Simple multiline formatter for logging messages."""
        def format(self, record):
            """Format multiline records so they look like multiple records."""
            message = super().format(record)  # Default formatting first.

            if record.message.strip() == '':  # Should not happen, ever, but…
                # Ignore empty messages.
                return ''
            # Get the preamble so it can be reproduced on each line.
            preamble = message.split(record.message)[0]
            # Return cleaned message: no multiple newlines, no trailing spaces,
            # and the preamble is inserted at the beginning of each line.
            return f'↲\n{preamble}'.join([line.rstrip() for line in message.splitlines() if line.strip()])

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
            'info': {
                '()': lambda: lambda log_record: log_record.msg.strip() and log_record.levelno == logging.INFO
            },
            'debug': {
                '()': lambda: lambda log_record: log_record.msg.strip() and log_record.levelno != logging.INFO
            }
        },
        'handlers': {},
        'loggers': {
            '': {  # root logger.
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
        'filename': debugfile,
        'mode': 'w',
        'encoding': 'utf8'
    }

    logging_configuration['handlers']['logfile'] = {
        'level': 'NOTSET',
        'formatter': 'log',
        'filters': ['info'],
        'class': 'logging.FileHandler',
        'filename': logfile,
        'mode': 'w',
        'encoding': 'utf8'
    }

    logging_configuration['handlers']['console'] = {
        'level': 'NOTSET',
        'formatter': 'console',
        'filters': ['info'],
        'class': 'logging.StreamHandler',
    }

    logging_configuration['loggers']['']['handlers'].append('debugfile')
    logging_configuration['loggers']['']['handlers'].append('logfile')
    logging_configuration['loggers']['']['handlers'].append('console')

    dictConfig(logging_configuration)


################################################################################################################
#                                                                                                              #
#                                                                                                              #
#    88888b.  888d888 .d88b.   .d8888b .d88b.  .d8888b  .d8888b            8888b.  888d888 .d88b.  888  888    #
#    888 "88b 888P"  d88""88b d88P"   d8P  Y8b 88K      88K                   "88b 888P"  d88P"88b 888  888    #
#    888  888 888    888  888 888     88888888 "Y8888b. "Y8888b.          .d888888 888    888  888 Y88  88P    #
#    888 d88P 888    Y88..88P Y88b.   Y8b.          X88      X88          888  888 888    Y88b 888  Y8bd8P     #
#    88888P"  888     "Y88P"   "Y8888P "Y8888   88888P'  88888P' 88888888 "Y888888 888     "Y88888   Y88P      #
#    888                                                                                       888             #
#    888                                                                                  Y8b d88P             #
#    888                                                                                   "Y88P"              #
#                                                                                                              #
#                                                                                                              #
################################################################################################################
def process_argv():
    """
    Process command line arguments.

    For each argument, identify the type of Manteca source, and signal the
    invalid ones.

    Returns a list of valid sources (can be empty).
    """
    sys.argv.pop(0)  # Remove program name from sys.argv.
    if len(sys.argv) == 0:
        # The input source should be provided automatically if the program is
        # used as a drag'n'drop target, which is in fact the intended method of
        # operation.
        #
        # But the program can be also run by hand from a command prompt, so it
        # is better to give the end user a warning (well, error...) if the input
        # source is missing.
        error(
            'No se ha especificado un fichero de entrada para ser procesado.\n'
            '\n'
            'Arrastre y suelte un fichero de entrada sobre el icono del programa, '
            'o proporcione el nombre del fichero como argumento.'
        )
        return

    for arg in sys.argv:
        logging.debug('Procesando fuente de Manteca «%s».', arg)
        dumpmode = arg.startswith(DUMPMODE_PREFIX)
        arg = arg.removeprefix(DUMPMODE_PREFIX)
        if dumpmode:
            logging.debug('La fuente de Manteca «%s» será volcada, no procesada.', arg)
        try:
            if re.match(r'(?:https?|file)://', arg):
                logging.debug('La fuente es un URI.')
                source = MantecaURI(arg)
                sink = None if dumpmode else SkimmedURI(None)
            elif arg.endswith('.txt'):
                arg = Path(arg)
                logging.debug('La fuente es un fichero de texto.')
                source = MantecaText(arg)
                sink = None if dumpmode else SkimmedText(arg.with_stem(arg.stem + '_out'))
            elif arg.endswith('.xlsx'):
                logging.debug('La fuente es un fichero Excel.')
                arg = Path(arg)
                source = arg
                sink = arg.with_stem(arg.stem + '_out')
                if not dumpmode:
                    logging.debug('Copiando workbook a «%s».', sink)
                    copy2(source, sink)
                try:
                    source = MantecaExcel(source)
                    sink = None if dumpmode else SkimmedExcel(sink)
                except (InvalidFileException, SheetTitleException, BadZipFile):
                    error('El fichero Excel de entrada es inválido.')
                    continue
            else:
                logging.debug('La fuente «%s» es inválida.', arg)
                continue
        except FileNotFoundError:
            error('No se encontró el fichero de entrada.')
            continue
        except PermissionError as exc:
            message = 'No hay permisos suficientes para '
            message += 'leer ' if exc.filename == str(arg) else 'crear '
            message += 'el fichero de '
            message += 'entrada.' if exc.filename == str(arg) else 'salida.'
            error(message)
            continue
        yield source, sink


###########################################################################################################
#                                                                                                         #
#                                                                                                         #
#    888                        888                                    .d888 d8b 888                      #
#    888                        888                                   d88P"  Y8P 888                      #
#    888                        888                                   888        888                      #
#    888  .d88b.   8888b.   .d88888          88888b.  888d888 .d88b.  888888 888 888  .d88b.  .d8888b     #
#    888 d88""88b     "88b d88" 888          888 "88b 888P"  d88""88b 888    888 888 d8P  Y8b 88K         #
#    888 888  888 .d888888 888  888          888  888 888    888  888 888    888 888 88888888 "Y8888b.    #
#    888 Y88..88P 888  888 Y88b 888          888 d88P 888    Y88..88P 888    888 888 Y8b.          X88    #
#    888  "Y88P"  "Y888888  "Y88888 88888888 88888P"  888     "Y88P"  888    888 888  "Y8888   88888P'    #
#                                            888                                                          #
#                                            888                                                          #
#                                            888                                                          #
#                                                                                                         #
#                                                                                                         #
###########################################################################################################
def load_profiles(filename):
    """
    Load the profiles from 'filename'.

    Returns the preprocessed list of profiles as a dictionary whose keys are the
    found profiles and the values are dictionaries containing the corresponding
    profile configuration items as key-value pairs.

    The returned list can be empty.
    """
    profiles = {}
    parser = configparser.ConfigParser()
    logging.debug('Obteniendo perfiles desde «%s».', filename)
    try:
        with open(filename, encoding='utf-8') as inifile:
            parser.read_file(inifile)
    except FileNotFoundError as exc:
        if exc.filename != filename:
            raise
        error('No se encontró el fichero de perfiles.')
    except configparser.Error as exc:
        error('Problema de sintaxis al leer el fichero de perfiles.')
        logging.debug('Error «%s» leyendo el fichero de perfiles:\n%s.', type(exc).__name__, exc)
    else:
        # Translate ConfigParser contents to a better suited format.
        #
        # To wit, a REAL dictionary whose keys are profile names and the values
        # are dictionaries containing the profile configuration.
        for profile in parser.sections():
            profiles[profile] = {}
            for key, value in parser[profile].items():
                try:
                    profiles[profile][key] = re.compile(value, re.IGNORECASE) if value else None
                except re.error as exc:
                    message = 'Problema de sintaxis al leer el fichero de perfiles.\n'
                    message += f'Perfil «{profile}»: {exc.msg[0].upper() + exc.msg[1:]}.\n'
                    message += f'  {key} = {exc.pattern}\n'
                    message += '  ' + '_' * (exc.pos + len(key) + len(' = ')) + '^'
                    error(message)
                    return None
        if not profiles:
            error('No hay perfiles definidos en el fichero de perfiles.')
        else:
            logging.debug('Se obtuvieron los siguientes perfiles: %s.', list(profiles.keys()))
    return profiles


###################################################################################################
#                                                                                                 #
#                                                                                                 #
#                    888            d8b                                                    d8b    #
#                    888            Y8P                                                    Y8P    #
#                    888                                                                          #
#    888d888 .d88b.  888888 888d888 888  .d88b.  888  888  .d88b.         888  888 888d888 888    #
#    888P"  d8P  Y8b 888    888P"   888 d8P  Y8b 888  888 d8P  Y8b        888  888 888P"   888    #
#    888    88888888 888    888     888 88888888 Y88  88P 88888888        888  888 888     888    #
#    888    Y8b.     Y88b.  888     888 Y8b.      Y8bd8P  Y8b.            Y88b 888 888     888    #
#    888     "Y8888   "Y888 888     888  "Y8888    Y88P    "Y8888 88888888 "Y88888 888     888    #
#                                                                                                 #
#                                                                                                 #
###################################################################################################
def retrieve_uri(uri):
    """
    Retrieve contents from 'uri'.

    This function resolves meta-refresh redirection for 'uri', then gets the
    contents and decodes them using the detected charset, or iso-8859-1 if no
    charset is detected.

    Returns a tuple whose first element are the decoded contents and the second
    element is the charset detected (or the default one if none is found).

    NOTE about charset: if no charset is detected, then iso-8859-1 is used as
    default. Really, utf-8 should be a better default, because modern web pages
    may NOT specify any encoding if they are using utf-8 and it is identical to
    ascii in the 7-bit codepoints. The problem is that utf-8 will fail for pages
    encoded with iso-8859-1, and the vast majority of web pages processed which
    does not specify a charset in fact will be using iso-8859-1 anyway.
    """
    # Allow relative file: URIs.
    if uri.startswith('file://'):
        uri = urlparse(uri)
        # If there is no host, the URI may be a relative path. Resolve it.
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
                logging.debug('Usando charset por defecto.')
    else:
        logging.debug('Charset detectado en las cabeceras.')
    logging.debug('Contenidos codificados con charset «%s».', charset)

    return contents.decode(charset), charset


###################################################################################
#                                                                                 #
#                                                                                 #
#                                             888                                 #
#                                             888                                 #
#                                             888                                 #
#    .d8888b   8888b.   .d8888b  8888b.       888  8888b.  .d8888b                #
#    88K          "88b d88P"        "88b      888     "88b 88K                    #
#    "Y8888b. .d888888 888      .d888888      888 .d888888 "Y8888b.               #
#         X88 888  888 Y88b.    888  888      888 888  888      X88               #
#     88888P' "Y888888  "Y8888P "Y888888      888 "Y888888  88888P'               #
#                                                                                 #
#                                    888                                          #
#                                    888                                          #
#                                    888                                          #
#    88888b.d88b.   8888b.  88888b.  888888 .d88b.   .d8888b  8888b.  .d8888b     #
#    888 "888 "88b     "88b 888 "88b 888   d8P  Y8b d88P"        "88b 88K         #
#    888  888  888 .d888888 888  888 888   88888888 888      .d888888 "Y8888b.    #
#    888  888  888 888  888 888  888 Y88b. Y8b.     Y88b.    888  888      X88    #
#    888  888  888 "Y888888 888  888  "Y888 "Y8888   "Y8888P "Y888888  88888P'    #
#                                                                                 #
#                                                                                 #
###################################################################################
def saca_las_mantecas(source, sink, profiles):  # pylint: disable=too-many-branches,too-many-locals
    """
    Saca las Mantecas (skims) from each 'source' dumping metadata to 'sink'.

    The 'profiles' are used to properly perform the skimming, since that process
    depends on the particular profile matched by the Manteca being skimmed.

    The full process is to obtain the list of Mantecas from each 'source', then
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
            logging.debug('No se detectó un perfil, ignorando «%s».', uri)
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
            logging.debug('Error de conexión accediendo a «%s».', uri)
            bad_metadata.append((uri, 'No se pudo conectar'))
        except URLError as exc:
            logging.debug('Error accediendo a «%s»: %s.', uri, exc.reason)
            bad_metadata.append((uri, 'No se pudo acceder'))
        if not contents:
            logging.debug('No se recibieron contenidos de «%s».', uri)
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


###########################################################
#                                                         #
#                                                         #
#                           d8b            .d88 88b.      #
#                           Y8P           d88P" "Y88b     #
#                                        d88P     Y88b    #
#    88888b.d88b.   8888b.  888 88888b.  888       888    #
#    888 "888 "88b     "88b 888 888 "88b 888       888    #
#    888  888  888 .d888888 888 888  888 Y88b     d88P    #
#    888  888  888 888  888 888 888  888  Y88b. .d88P     #
#    888  888  888 "Y888888 888 888  888   "Y88 88P"      #
#                                                         #
#                                                         #
###########################################################
def main():
    """."""
    # Install the default exception hook first.
    sys.excepthook = excepthook

    try:
        # Initialize logging system ASAP.
        setup_logging()
        logging.debug(PROGRAM_NAME)
        logging.debug('Registro de depuración iniciado.')
        logging.debug('User-Agent: «%s».', USER_AGENT)

        logging.info(PROGRAM_NAME)

        profiles = load_profiles(INIFILE_PATH)
        if not profiles:
            raise SystemExit

        # Loop over the sources and skim them.
        print()
        logging.info('Sacando las mantecas:')
        bad_metadata = []
        for source, sink in process_argv():
            result = saca_las_mantecas(source, sink, profiles)
            if result is not None:
                bad_metadata.extend(result)
        if bad_metadata:
            print()
            logging.info('Se encontraron problemas en los siguientes enlaces:')
            for uri, problem in bad_metadata:
                logging.info('  [%s] %s.', uri, problem)
    except SystemExit:
        pass
    except KeyboardInterrupt:
        print()
        logging.info('El usuario interrumpió la operación del programa.')

    print()
    logging.info('Proceso terminado.')
    logging.debug('Registro de depuración finalizado.')
    logging.shutdown()


if __name__ == '__main__':
    sys.exit(main())
