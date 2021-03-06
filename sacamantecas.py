#! /usr/bin/env python3
"""
Saca las Mantecas.

This program reads an Excel file (xls/xlsx), containing a list of book titles,
each one with its signature and Manteca, which is an URI pointing to an entry
within some bibliographic catalogue where the book metadata can be obtained,
gets that metadata and adds it to each book, producing an output Excel file.

The Mantecas are processed according to profiles, which indicate how to properly
process the retrieved contents from the URIs, depending on the bibliographic
catalogue which is being processed. The proper profile is inferred from the URI
itself and resides in a separate file.

In short, it saca las Mantecas…

If the input file is not an Excel file, it is assumed it contains a list of
Mantecas, that is, a list of URIs pointing to bibliographic entries. In this
mode of operation the output file will not be an Excel file but another text
file containing the retrieved metadata for each entry. This is by design, so
profiles can be tested separately without the need to process and write Excel
files, or when the need arrives to process a new kind of URI in order to create
a new Manteca processing profile.
"""

# Current version…
__version__ = 'v3.3'

# Imports
import configparser
import sys
import os.path
import errno
import logging
import atexit
from logging.config import dictConfig
import traceback as tb
from shutil import copy2
from urllib.request import urlopen, Request
from urllib.parse import urlparse, urlunparse
from urllib.error import URLError
import re
import time
import platform
from html.parser import HTMLParser
from msvcrt import getch
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
    PROGRAM_PATH = os.path.realpath(PROGRAM_PATH)
    PROGRAM_NAME = os.path.splitext(os.path.basename(PROGRAM_PATH))[0] + ' ' + __version__
    INIFILE_PATH = os.path.splitext(PROGRAM_PATH)[0] + '.ini'
except NameError:
    sys.exit('Error de inicialización del programa.')


# Check if platform is win32 or not.
if sys.platform != 'win32':
    sys.exit(f'{PROGRAM_NAME} solo funciona en la plataforma Win32.')

# Create a sane User-Agent.
USER_AGENT = f'{PROGRAM_NAME.replace(" v", "/")} +https://github.com/DervishD/sacamantecas'
USER_AGENT += f' (Windows {platform.version()}; {platform.architecture()[0]}; {platform.machine()})'

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
        message += os.path.basename(PROGRAM_PATH) if frame.name == '<module>' else frame.name
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
                if urlparse(cell.value).scheme.startswith('http'):
                    logging.debug('Se encontró un URI en la celda «%s»: %s', cell.coordinate, cell.value)
                    yield (cell.row, cell.value)
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
        exists on the sheet, at the specified 'row'. The 'URI' is not used.

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
                yield (row, uri)

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
        reference only, followed by 'URI'. Then, the metadata will be more or
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
        yield (1, self.source)

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
        print(f'Metadatos obtenidos para {uri}:')
        for key, value in metadata.items():
            print(f'  {key}: {value}')

    def close(self):
        """NOP"""


##############################################################################
#                                                                            #
#                                                                            #
#     .d8888b.  888      d8b                                                 #
#    d88P  Y88b 888      Y8P                                                 #
#    Y88b.      888                                                          #
#     "Y888b.   888  888 888 88888b.d88b.  88888b.d88b.   .d88b.  888d888    #
#        "Y88b. 888 .88P 888 888 "888 "88b 888 "888 "88b d8P  Y8b 888P"      #
#          "888 888888K  888 888  888  888 888  888  888 88888888 888        #
#    Y88b  d88P 888 "88b 888 888  888  888 888  888  888 Y8b.     888        #
#     "Y8888P"  888  888 888 888  888  888 888  888  888  "Y8888  888        #
#                                                                            #
#                                                                            #
##############################################################################
class MantecaSkimmer(HTMLParser):
    """HTML retriever/parser Manteca URIs, that is, web pages of library catalogues."""
    # In order to keep this parser as simple as possible, some assumptions are
    # made. See the comments below to know which those are.
    def __init__(self, profiles, *args, **kwargs):
        """Initialize object."""
        super().__init__(*args, **kwargs)
        self.within_k = False
        self.within_v = False
        self.profiles = profiles
        self.profile = None
        self.current_k = ''
        self.current_v = ''
        self.retrieved_metadata = {}

    def handle_starttag(self, tag, attrs):
        """Handle opening tags."""
        for attr in attrs:
            if attr[0] == 'class' and (match := self.profile['k_class'].fullmatch(attr[1])):
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
            if attr[0] == 'class' and (match := self.profile['v_class'].fullmatch(attr[1])):
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
            # Metadata is only stored after getting the full key/value pair.
            if self.current_k and self.current_v:
                self.retrieved_metadata[self.current_k] = self.current_v
            if not self.current_k or not self.current_k:
                logging.error('Metadato incompleto. K«%s» = V«%s».')
            self.current_k = ''
            self.current_v = ''
            return

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

    def skim(self, uri):  # pylint: disable=too-many-branches
        """
        Retrieve and process contents from 'uri'.

        This function resolves meta-refresh redirection for 'uri', then gets the
        contents and decodes them using the detected charset, or iso-8859-1 if
        none is detected.

        Then the contents are fed into the HTML parser and processed in order to
        skim the Manteca.

        NOTE about charset: if no charset is detected, then iso-8859-1 is used
        as default. Really, utf-8 should be a better default, because modern web
        pages may NOT specify any encoding if they are using utf-8 and it is
        identical to ascii in the 7-bit codepoints. The problem is that utf-8
        will fail for pages encoded with iso-8859-1, and the vast majority of
        web pages processed will in fact use iso-8859-1 anyway.
        """
        self.retrieved_metadata.clear()
        self.profile = None
        for profile in self.profiles:
            if self.profiles[profile]['u_match'].match(uri):
                logging.debug('Perfil detectado: «%s».', profile)
                self.profile = self.profiles[profile]
        if not self.profile:  # Ignore URIs if no profile exists for them.
            logging.debug('No se detectó un perfil para «%s», ignorando…', uri)
            return {}

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

        self.feed(contents.decode(charset))
        self.close()
        return self.retrieved_metadata

    def error(self, _):
        """Override ParserBase abstract method."""


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
    debugfile = f'{os.path.splitext(PROGRAM_PATH)[0]}_debug_{timestamp}.txt'
    logfile = f'{os.path.splitext(PROGRAM_PATH)[0]}_log_{timestamp}.txt'

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
        return []

    sources = []
    for arg in sys.argv:
        if arg.startswith('http'):
            sources.append(('URI', arg, None))
        elif arg.endswith('.xlsx'):
            sources.append(('XLS', arg, '_out'.join(os.path.splitext(arg))))
        elif arg.endswith('.txt'):
            sources.append(('TXT', arg, '_out'.join(os.path.splitext(arg))))
        else:
            logging.debug('La fuente «%s» es inválida.', arg)
    return sources


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
                # profiles[profile] = {key: re.compile(value, re.IGNORECASE) for
                # key, value in parser[profile].items()}
                try:
                    profiles[profile][key] = re.compile(value, re.IGNORECASE)
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


#################################################################
#                                                               #
#                                                               #
#             888      d8b                    d8b 888    888    #
#             888      Y8P                    Y8P 888    888    #
#             888                                 888    888    #
#    .d8888b  888  888 888 88888b.d88b.       888 888888 888    #
#    88K      888 .88P 888 888 "888 "88b      888 888    888    #
#    "Y8888b. 888888K  888 888  888  888      888 888    Y8P    #
#         X88 888 "88b 888 888  888  888      888 Y88b.   "     #
#     88888P' 888  888 888 888  888  888      888  "Y888 888    #
#                                                               #
#                                                               #
#################################################################
def saca_las_mantecas(manteca_spec, skimmer):
    """
    Saca las Mantecas (skims) from 'manteca_spec' using 'skimmer'.

    The 'manteca_spec' is a tuple (kind, source, sink).
    """
    kind, source, sink = manteca_spec
    logging.debug('Procesando fuente de Manteca «%s».', source)
    logging.debug('La fuente está en formato «%s».', kind)

    try:
        if kind == 'XLS':
            logging.debug('Copiando workbook a «%s».', sink)
            copy2(source, sink)
            try:
                manteca_source = MantecaExcel(source)
                skimmed_sink = SkimmedExcel(sink)
            except (InvalidFileException, SheetTitleException):
                error('El fichero Excel de entrada es inválido.')
                return []
        elif kind == 'TXT':
            manteca_source = MantecaText(source)
            skimmed_sink = SkimmedText(sink)
        else:
            manteca_source = MantecaURI(source)
            skimmed_sink = SkimmedURI(sink)
    except FileNotFoundError:
        error('No se encontró el fichero de entrada.')
        return []
    except PermissionError as exc:
        message = 'No hay permisos suficientes para '
        message += 'leer ' if exc.filename == source else 'crear '
        message += 'el fichero de '
        message += 'entrada.' if exc.filename == source else 'salida.'
        error(message)
        return []

    bad_metadata = []
    for row, uri in manteca_source.get_mantecas():
        logging.info('  %s', uri)
        try:
            metadata = skimmer.skim(uri)
            if not metadata:
                bad_metadata.append((uri, 'No se obtuvieron metadatos'))
            else:
                skimmed_sink.add_metadata(row, uri, metadata)
        except ConnectionError:
            logging.debug('Error de conexión accediendo a «%s».', uri)
            bad_metadata.append((uri, 'No se pudo conectar'))
        except URLError as exc:
            logging.debug('Error accediendo a «%s»: %s.', uri, exc.reason)
            bad_metadata.append((uri, 'No se pudo acceder'))
    manteca_source.close()
    skimmed_sink.close()
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

        manteca_specs = process_argv()
        if not manteca_specs:
            raise SystemExit

        profiles = load_profiles(INIFILE_PATH)
        if not profiles:
            raise SystemExit

        # Create skimmer. It will be reused for each source.
        skimmer = MantecaSkimmer(profiles)

        # Loop over the sources and skim them.
        print()
        logging.info('Sacando las mantecas:')
        bad_metadata = []
        for manteca_spec in manteca_specs:
            result = saca_las_mantecas(manteca_spec, skimmer)
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
