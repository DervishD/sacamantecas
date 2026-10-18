"""See 'README.md' for details."""
import sys

if sys.platform != 'win32':
    sys.stdout.write('\nThis program is compatible only with the Win32 platform.\n')
    sys.stdout.flush()
    sys.exit(None)

# pylint: disable=wrong-import-position
from abc import ABC, abstractmethod
import configparser
from enum import IntEnum, StrEnum
import errno
from functools import wraps
from html.parser import HTMLParser
from http.client import HTTPException
import logging
from pathlib import Path
import re
from shutil import copy2
import time
from typing import ClassVar, final, NamedTuple, TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse, urlunparse
from urllib.request import Request, urlopen
from zipfile import BadZipFile

from legion import ensure_utf8_output, format_message, get_logger
from openpyxl import load_workbook
from openpyxl.cell.cell import Cell, MergedCell, TYPE_STRING as CELLTYPE_STRING
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.cell import get_column_letter

from .about import BUILD, DEPENDENCIES, DEVELOPMENT_MODE, PROGRAM_NAME, REPOSITORY, VERSION

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from openpyxl.worksheet.worksheet import Worksheet


type MetadataKey = str
type MetadataValue = str
type Metadata = dict[MetadataKey, MetadataValue]
type RawMetadata = dict[MetadataKey, list[MetadataValue]]

type Url = str
type SkimResults = dict[Url, Metadata]
type ParserConfig = dict[str, re.Pattern[str]]


USER_AGENT = f'{PROGRAM_NAME}/{VERSION} (bot; +{REPOSITORY})'

URL_PATTERN = re.compile(r'[a-z][a-z0-9+.-]+://', re.IGNORECASE)

TIMESTAMP_STEM = time.strftime('_%Y%m%d_%H%M%S')

TEXTFILE_SUFFIX = '.txt'
SPREADSHEET_SUFFIX = '.xlsx'


class Paths:  # pylint: disable=too-few-public-methods
    """Program paths."""

    ROOT = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
    MAIN_LOG = ROOT / f'{PROGRAM_NAME}_log{"" if DEVELOPMENT_MODE else TIMESTAMP_STEM}{TEXTFILE_SUFFIX}'
    FULL_LOG = ROOT / f'{PROGRAM_NAME}_trace{"" if DEVELOPMENT_MODE else TIMESTAMP_STEM}{TEXTFILE_SUFFIX}'
    INIFILE = ROOT / f'{PROGRAM_NAME}.ini'


class Messages(StrEnum):
    """End-user messages."""

    # Helpers.
    ERROR_PREFIX = '\n*** Error: '
    WARNING_PREFIX = '* Aviso: '
    STEP_MARKER = '·'

    # General messages.
    PRESS_ANY_KEY = '\nPulse cualquier tecla para continuar...'
    PROGRAM_BANNER = f'{PROGRAM_NAME} versión {BUILD} ({REPOSITORY})'
    PROCESS_DONE = 'Proceso finalizado'

    # Main loop messages.
    GATEWAY_LABEL = 'Fuente: {}'
    STEP_LOADING_URLS = f'{STEP_MARKER}Obteniendo URLs'
    STEP_PROCESSING_URLS = f'{STEP_MARKER}Sacando las mantecas'
    URLS_RESULT = '=> {}'
    URLS_RESULT_NONE = 'Ninguna URL procesada de un total de {1}'
    URLS_RESULT_ONE = '1 URL procesada de un total de {1}'
    URLS_RESULT_MANY = '{0} URLs procesadas de un total de {1}'
    STEP_SAVING_RESULTS = f'{STEP_MARKER}Guardando metadatos'

    # Warning messages.
    WARNING_KEYBOARD_INTERRUPT = 'El usuario interrumpió la operación de la aplicación.'
    WARNING_GATEWAY_EMPTY = 'La fuente no contiene ningún URL'

    # Generic error messages:
    ERROR_UNHANDLED_EXCEPTION = 'Excepción sin gestionar'
    ERROR_NO_ARGUMENTS = (
        'No se han especificado fuentes de entrada para ser procesadas.\n'
        '\n'
        'Arrastre y suelte un fichero de entrada sobre el icono de la aplicación,\n'
        'o bien proporcione los nombres de las fuentes de entrada como argumentos.'
    )

    # Profile handling errors.
    PROFILES_ERROR_MISSING_PROFILES = 'No se encontró o no se pudo leer el fichero de perfiles «{}»'
    PROFILES_ERROR_PROFILES_WRONG_SYNTAX = 'Sintaxis incorrecta en el fichero de perfiles [{}]'
    PROFILES_ERROR_PROFILE_WITHOUT_URL = 'El perfil «{}» no incluye un patrón de URL'
    PROFILES_ERROR_PROFILE_WRONG_PARAMETERS = 'El perfil «{}» no contiene parámetros correctos'
    PROFILES_ERROR_EMPTY_PROFILES = 'No hay perfiles definidos en el fichero de perfiles «{}»'
    PROFILES_ERROR_WRONG_REGEX = (
        'Expresión regular incorrecta en el fichero de perfiles\n'
        'Perfil «{}», clave «{}»:\n'
        '  {}\n'
        '  {:_<{}}^\n'
        '  [{}: {}]\n'
    )

    # Gateway errors.
    GATEWAY_ERROR_UNSUPPORTED_GATEWAY = 'La fuente no es de un tipo admitido'
    GATEWAY_ERROR_INPUT_FILE_NOT_FOUND = 'No se encontró el fichero de entrada'
    GATEWAY_ERROR_OUTPUT_FILE_NOT_FOUND = 'No se encontró el fichero de salida'
    GATEWAY_ERROR_INPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para leer el fichero de entrada'
    GATEWAY_ERROR_OUTPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para crear el fichero de salida'
    GATEWAY_ERROR_NO_RESULTS_TO_SAVE = 'No hay metadatos para esta fuente'
    GATEWAY_ERROR_INPUT_TEXT_FILE_NOT_UTF_8 = 'El fichero de entrada no está codificado en UTF-8'
    GATEWAY_ERROR_SOURCE_SHEET_IS_INVALID = 'La hoja de entrada es inválida'

    # Skimming errors.
    SKIMMING_ERROR_NO_MATCHING_PROFILE = 'No se encontró un perfil para procesar el URL'
    SKIMMING_ERROR_URL_ACCESS = 'No resultó posible acceder a la dirección especificada ({})'
    URL_ACCESS_REASON_OSLIKE_ERROR = '{}'
    URL_ACCESS_REASON_HTTP_ERROR = 'respuesta HTTP {}'
    URL_ACCESS_REASON_UNEXPECTED_ERROR = 'error inesperado'
    SKIMMING_ERROR_ERROR_HTTP_RETRIEVAL = 'No se obtuvieron contenidos, error de protocolo HTTP «{}»'
    SKIMMING_ERROR_CONNECTION_FAILED = 'Se produjo un error de conexión «{}» accediendo al URL'
    SKIMMING_ERROR_CONNECTION_FAILED_UNKNOWN_REASON = 'Se produjo un error de conexión desconocido accediendo al URL'
    SKIMMING_ERROR_NO_CONTENTS = 'No se recibieron contenidos del URL'
    SKIMMING_ERROR_NO_METADATA_FOUND = 'No se obtuvieron metadatos'


class Debug(StrEnum):
    """Trace (debugging) messages."""

    # General messages.
    DEBUGGING_INIT = 'Registro de depuración iniciado'
    DEBUGGING_DONE = 'Registro de depuración finalizado'
    DEPENDENCY_BANNER = 'Usando paquete {}'

    # Exception logging.
    EXCEPTION_LOG = 'Se lanzó una excepción «{}»'
    EXCEPTION_LOG_NO_CONTEXT = 'La excepción no contiene contexto'
    EXCEPTION_LOG_CONTEXT = (
        '  __context__ -> «{}»\n'
        '  __repr__    -> {}\n'
        '  __str__     -> {}\n'
    )

    # Argument parsing.
    PROCESSING_ARG = 'Procesando argumento «{}»'
    ARG_IS_SINGLE_URL = 'El argumento es de tipo single_url'
    ARG_IS_TEXTFILE = 'El argumento es de tipo textfile'
    ARG_IS_SPREADSHEET = 'El argumento es de tipo spreadsheet'
    ARG_IS_UNSUPPORTED = 'El argumento no es de un tipo admitido'

    # Profiles handling.
    LOADING_PROFILES = 'Obteniendo perfiles desde «{}»'
    FOUND_PROFILES = 'Se obtuvieron los siguientes perfiles: {}'
    PROFILE_ID = 'Perfil y tipo de catálogo: «{}»/«{}»'

    # URL retrieval.
    PROCESSING_URL = 'Procesando URL «{}»'
    REDIRECTED_URL = 'URL redirigido a «{}»'
    CHARSET_NOT_IN_HEADERS = 'Charset no detectado en las cabeceras'
    CHARSET_FROM_HTTP_EQUIV = 'Charset detectado mediante meta http-equiv'
    CHARSET_FROM_META_CHARSET = 'Charset detectado mediante meta charset'
    CHARSET_FROM_DEFAULT = 'Charset no detectado, usando valor por defecto'
    CHARSET_IN_HEADERS = 'Charset detectado en las cabeceras'
    CONTENTS_ENCODING = 'Contenidos codificados con charset «{}»'

    # Gateways.
    DUMPING_METADATA_TO_SINK = 'Volcando metadatos a «{}»'
    DUMPING_METADATA_K_V = 'Añadiendo metadato «{}» con valor «{}»'
    WORKING_SHEET = 'La hoja con la que se trabajará es «{}»'
    PROCESSING_ROW = 'Procesando fila {}'
    COPYING_WORKBOOK = 'Copiando workbook a «{}»'
    INSERTING_HEADING_ROW = 'Insertando fila de cabeceras'
    NONSTRING_CELL = 'La celda «{}» no es de tipo cadena, será ignorada'
    URL_FOUND_IN_CELL = 'Se encontró un URL en la celda «{}»: {}'
    NEW_METADATA_FOUND = 'Se encontró un metadato nuevo, «{}»'
    METADATA_STORED_IN_COLUMN = 'El metadato «{}» irá en la columna «{}»'

    # Parsers.
    HTML_START_TAG = '➜ HTML <{}{}{}>'
    METADATA_KEY_FOUND = 'Se encontró la clave «{}»'
    METADATA_VALUE_FOUND = 'Se encontró el valor «{}»'
    METADATA_IS_EMPTY = 'Metadato vacío'
    METADATA_MISSING_VALUE = 'Metadato «{}» incompleto, ignorando'
    METADATA_MISSING_KEY = 'No se encontró una clave, usando «{}»'
    METADATA_OK = 'Metadato correcto «{}: {}»'
    METADATA_KEY_MARKER_FOUND = 'Se encontró una marca de clave «{}»'
    METADATA_VALUE_MARKER_FOUND = 'Se encontró una marca de valor «{}»'
    METADATA_MARKER_FOUND = 'Se encontró una marca de metadato «{}»'
    PARSER_NESTING_ERROR_K_IN_V = 'Problema de anidación (clave dentro de valor), restableciendo parser'
    PARSER_NESTING_ERROR_V_IN_K = 'Problema de anidación (valor dentro de clave), restableciendo parser'


class ExitCodes(IntEnum):
    """Standardized exit codes."""  # noqa: D204
    SUCCESS = 0
    NO_ARGUMENTS = 1
    WARNING = 2
    ERROR = 3
    KEYBOARD_INTERRUPT = 127


logger = get_logger(PROGRAM_NAME)


class ProfilesError(Exception):
    """Raise for profile-related errors."""

class GatewayError(Exception):
    """Raise for gateway-related errors."""

class SkimmingError(Exception):
    """Raise for skimming-related errors."""


class BaseParser(HTMLParser):
    """Base class for catalogue parsers."""

    PARAMETERS: ClassVar[set[str]] = set()
    DEFAULT_K: MetadataKey = ''
    DEFAULT_V: MetadataValue = ''
    EMPTY_KEY_PLACEHOLDER = '[vacío]'
    MULTIDATA_SEPARATOR = ' / '
    MULTIVALUE_SEPARATOR = ' === '
    METADATA_KEY_TERMINATOR = ':'

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize object."""
        self.within_k: bool
        self.within_v: bool
        self.current_k: MetadataKey
        self.current_v: MetadataValue
        self.last_k: MetadataKey
        self.retrieved_metadata: RawMetadata
        self.config: ParserConfig
        super().__init__(*args, **kwargs)

    def reset(self) -> None:
        """Reset parser state. Called implicitly from `__init__()`."""
        super().reset()
        self.within_k = self.within_v = False
        self.current_k = self.DEFAULT_K
        self.current_v = self.DEFAULT_V
        self.last_k = self.DEFAULT_K
        self.retrieved_metadata = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle opening tags."""
        logger.debug(Debug.HTML_START_TAG.format(tag, ' ' * bool(attrs), ' '.join((f'{k}="{v}"' for k, v in attrs))))

    def handle_data(self, data: str) -> None:
        """Handle data."""
        if self.within_k or self.within_v:
            # Clean up received data by removing superfluous whitespace
            # characters, including newlines, carriage returns, etc.
            data = ' '.join(data.split())
            if not data:
                return
        if self.within_k:
            logger.debug(Debug.METADATA_KEY_FOUND.format(data))
            self.current_k += data.rstrip(self.METADATA_KEY_TERMINATOR)
            self.last_k = self.current_k
            return
        if self.within_v:
            logger.debug(Debug.METADATA_VALUE_FOUND.format(data))
            self.current_v += f'{self.MULTIDATA_SEPARATOR if self.current_v else ''}{data}'
            return

    def configure(self, config: ParserConfig) -> None:
        """Configure parser.

        Set up parser with configuration from *config*, that is, a set
        of values for the supported parser parameters.

        Only supported configuration parameters are used, the rest are
        silently ignored.

        This operation also resets the parser.
        """
        self.reset()
        self.config = {key: value for key, value in config.items() if key in self.PARAMETERS}

    def store_metadata(self) -> None:
        """Store found metadata, handling missing parts."""
        if not self.current_k and not self.current_v:
            logger.debug(Debug.METADATA_IS_EMPTY)
        if self.current_k and not self.current_v:
            logger.debug(Debug.METADATA_MISSING_VALUE.format(self.current_k))
        if not self.current_k and self.current_v:
            self.current_k = self.last_k or self.EMPTY_KEY_PLACEHOLDER
            logger.debug(Debug.METADATA_MISSING_KEY.format(self.current_k))
        if self.current_k and self.current_v:
            if self.current_k not in self.retrieved_metadata:
                self.retrieved_metadata[self.current_k] = []
            # A set is not used below, to preserve order.
            if self.current_v not in self.retrieved_metadata[self.current_k]:
                self.retrieved_metadata[self.current_k].append(self.current_v)
            logger.debug(Debug.METADATA_OK.format(self.current_k, self.current_v))
        self.current_k = self.DEFAULT_K
        self.current_v = self.DEFAULT_V

    def get_metadata(self) -> Metadata:
        """Get the metadata retrieved so far."""
        processed_metadata: Metadata = {}
        for key, value in self.retrieved_metadata.items():
            processed_metadata[key] = self.MULTIVALUE_SEPARATOR.join(value)
        return processed_metadata


# pylint: disable-next=unused-variable
class OldRegimeParser(BaseParser):
    """Parser for *Old Regime* catalogues.

    Parser for *Old Regime* catalogues, which use different HTML `class`
    attributes to mark metadata keys and metadata values.

    This is inherently complex, specially when dealing with ill-formed
    HTML, so in order to keep this parser as simple as possible, some
    assumptions are made.

    See the comments below to know which those assumptions are.
    """

    K_CLASS = 'k_class'
    V_CLASS = 'v_class'
    PARAMETERS = BaseParser.PARAMETERS | {K_CLASS, V_CLASS}
    CLASS_ATTR = 'class'

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize object."""
        self.current_k_tag = None
        self.current_v_tag = None
        super().__init__(*args, **kwargs)

    def reset(self) -> None:
        """Reset parser state. Called implicitly from `__init__()`."""
        super().reset()
        self.current_k_tag = self.current_v_tag = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle opening tags."""
        super().handle_starttag(tag, attrs)
        for attr in attrs:
            if attr[1] is None:
                continue
            if attr[0] == self.CLASS_ATTR and (match := self.config[self.K_CLASS].search(attr[1])):
                logger.debug(Debug.METADATA_KEY_MARKER_FOUND.format(match.group(0)))
                self.within_k = True
                self.current_k = self.DEFAULT_K
                self.current_k_tag = tag
                if self.within_v:
                    # If still processing a value, log about the nesting
                    # error but reset parser so everything starts afresh
                    # like if a new key had been found.
                    logger.debug(Debug.PARSER_NESTING_ERROR_K_IN_V)
                    self.within_v = False
                    self.current_v = self.DEFAULT_V
                    self.current_v_tag = None
                break
            if attr[0] == self.CLASS_ATTR and (match := self.config[self.V_CLASS].search(attr[1])):
                logger.debug(Debug.METADATA_VALUE_MARKER_FOUND.format(match.group(0)))
                self.within_v = True
                self.current_v = self.DEFAULT_V
                self.current_v_tag = tag
                if self.within_k:
                    # If a new key is found but a previous one is still
                    # being processed, this nesting error is not fatal
                    # and can still be recovered, up to a certain point.
                    # If some data was got for the key, the parser will
                    # be left in 'within_v' mode to try to get the value
                    # if possible. Otherwise the parser is reset.
                    logger.debug(Debug.PARSER_NESTING_ERROR_V_IN_K)
                    self.within_k = False
                    self.current_k_tag = None
                    if not self.current_k:
                        self.within_v = False
                        self.current_v_tag = None
                break

    def handle_endtag(self, tag: str) -> None:
        """Handle closing tags."""
        super().handle_endtag(tag)
        if self.within_k and tag == self.current_k_tag:
            self.within_k = False
            self.current_k_tag = None
            return
        if self.within_v and tag == self.current_v_tag:
            self.within_v = False
            self.current_v_tag = None
            self.store_metadata()
            return


# pylint: disable-next=unused-variable
class BaratzParser(BaseParser):
    """Parser for *Baratz* catalogues.

    Parser for catalogues whose contents have been generated by the new
    *Baratz* frontend, which does not use the HTML `class` attributes to
    mark metadata keys and values. Instead a particular HTML element is
    used as a kind of marker for the start of metadata blocks, which in
    turn contain the metadata as a list of `<dt>/<dd>` pairs.

    Within that list, the `<dt>` HTML element contains the metadata key,
    whereas the `<dd>` HTML element containing the metadata value.

    The element which acts as the marker for a metadata block is defined
    by its HTML tag, the attribute which contains the marker value, and
    of course the marker value itself.
    """

    M_TAG = 'm_tag'
    M_ATTR = 'm_attr'
    M_VALUE = 'm_value'
    PARAMETERS = BaseParser.PARAMETERS | {M_TAG, M_ATTR, M_VALUE}
    K_TAG = 'dt'
    V_TAG = 'dd'

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize object."""
        self.within_meta: bool
        super().__init__(*args, **kwargs)

    def reset(self) -> None:
        """Reset parser state. Called implicitly from `__init__()`."""
        super().reset()
        self.within_meta = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: C901
        """Handle opening tags."""
        super().handle_starttag(tag, attrs)
        if not self.within_meta:
            if not self.config[self.M_TAG].fullmatch(tag):
                return
            for attr in attrs:
                if attr[1] is None:
                    return
                if self.config[self.M_ATTR].fullmatch(attr[0]) and self.config[self.M_VALUE].search(attr[1]):
                    logger.debug(Debug.METADATA_MARKER_FOUND.format(attr[1]))
                    self.within_meta = True
                    return
        else:
            if tag == self.K_TAG:
                logger.debug(Debug.METADATA_KEY_MARKER_FOUND.format(tag))
                self.within_k = True
                if self.within_v:
                    # If still processing a value, log about the nesting
                    # error but reset parser so everything starts afresh
                    # like if a new key had been found.
                    logger.debug(Debug.PARSER_NESTING_ERROR_K_IN_V)
                    self.within_v = False
                    self.current_v = self.DEFAULT_V
                return
            if tag == self.V_TAG:
                logger.debug(Debug.METADATA_VALUE_MARKER_FOUND.format(tag))
                self.within_v = True
                if self.within_k:
                    # If a new key is found but a previous one is still
                    # being processed, this nesting error is not fatal
                    # and can still be recovered, up to a certain point.
                    # If some data was got for the key, the parser will
                    # be left in 'within_v' mode to try to get the value
                    # if possible. Otherwise the parser is reset.
                    logger.debug(Debug.PARSER_NESTING_ERROR_V_IN_K)
                    self.within_k = False
                    if not self.current_k:
                        self.within_v = False
                return

    def handle_endtag(self, tag: str) -> None:
        """Handle closing tags."""
        super().handle_endtag(tag)
        if self.within_meta and self.config[self.M_TAG].fullmatch(tag):
            self.within_meta = False
            return
        if self.within_k and tag == self.K_TAG:
            self.within_k = False
            return
        if self.within_v and tag == self.V_TAG:
            self.within_v = False
            self.store_metadata()
            return


class Profile(NamedTuple):
    """Abstraction for profiles."""  # noqa: D204
    url_pattern: re.Pattern[str]
    parser: BaseParser
    parser_config: ParserConfig


def error(message: str) -> None:
    """Preprocess and log error *message*.

    First, the initial letter of *message* is lowercased. Then, a fixed
    prefix is prepended. Finally, the resulting string is formatted by
    using `legion.format_message()`, that is, if *message* has multiple
    lines, then the first one is considered a heading, and the remaining
    lines are indented.

    The result is logged using `logger.error()`.
    """
    heading, _, remaining = message.partition('\n')
    heading = f'{Messages.ERROR_PREFIX}{heading[0].lower()}{heading[1:]}'
    logger.error(format_message(heading, remaining, indentation=' ' * Messages.ERROR_PREFIX.index(' ')))


def log_exception(exc: Exception) -> None:
    """Log *exc* with `logger.debug()`.

    If *exc* has `__context__` it is dumped, too.
    """
    logger.debug(Debug.EXCEPTION_LOG.format(type(exc).__name__))
    if exc.__context__:
        message = Debug.EXCEPTION_LOG_CONTEXT.format(
            type(exc.__context__).__name__,
            repr(exc.__context__),
            str(exc.__context__),
        )
    else:
        message = Debug.EXCEPTION_LOG_NO_CONTEXT
    logger.debug(message)


def warning(message: str) -> None:
    """Preprocess and log warning *message*.

    First, the initial letter of *message* is lowercased. Then, a fixed
    prefix is prepended to *message*.

    The result is then logged using `logger.warning()`.
    """
    logger.warning('%s', Messages.WARNING_PREFIX + message[0].lower() + message[1:])


def loggerize(function: Callable[..., ExitCodes]) -> Callable[..., ExitCodes]:
    """Decorate *function* so it runs with logging enabled."""
    @wraps(function)
    def loggerize_wrapper(*args: str) -> ExitCodes:
        logger.config(main_log_output=Paths.MAIN_LOG, full_log_output=Paths.FULL_LOG)

        logger.debug(Debug.DEBUGGING_INIT)
        logger.info(Messages.PROGRAM_BANNER)
        for required_package in DEPENDENCIES:
            logger.debug(Debug.DEPENDENCY_BANNER.format(required_package.replace('==', ' v')))
        logger.debug(USER_AGENT)

        status = function(*args)

        logger.info('')
        logger.info(Messages.PROCESS_DONE)
        logger.debug(Debug.DEBUGGING_DONE)
        logging.shutdown()
        return status
    return loggerize_wrapper


def keyboard_interrupt_handler(function: Callable[..., ExitCodes]) -> Callable[..., ExitCodes]:
    """Decorate *function* so it handles `KeyboardInterrupt`."""
    @wraps(function)
    def handle_keyboard_interrupt_wrapper(*args: str) -> ExitCodes:
        try:
            return function(*args)
        except KeyboardInterrupt:
            logger.set_indent(0)
            logger.warning('')
            warning(Messages.WARNING_KEYBOARD_INTERRUPT)
            return ExitCodes.KEYBOARD_INTERRUPT
    return handle_keyboard_interrupt_wrapper


def build_parser_config(config: configparser.ConfigParser, section: str) -> ParserConfig:
    """Build parser config from *section* within *config*.

    Empty values are silently skipped.
    Regular expressions are compiled.

    Raise `ProfilesError` if any value fails to compile as a regex.
    """
    parser_config: ParserConfig = {}
    for key, value in config[section].items():
        if not value:
            continue
        try:
            parser_config[key] = re.compile(value, re.IGNORECASE)
        except re.PatternError as exc:
            message = Messages.PROFILES_ERROR_WRONG_REGEX.format(
                section, key,
                exc.pattern,
                '', exc.pos or 0,  # The empty string is needed as a placeholder!
                type(exc).__name__, str(exc))
            raise ProfilesError(message) from exc
    return parser_config


def load_profiles(profiles_path: Path) -> dict[str, Profile]:
    """Load the profiles from *profiles_path*.

    Read *profiles_path*, which contains profile definitions, and return
    a processed list of the obtained profiles as a dictionary.

    Dictionary keys are the obtained profile names, while the values are
    the corresponding profile definitions as `Profile` named tuples.

    Raise `MissingProfilesError` if *profiles_path* cannot be opened or
    read.

    Raise `ProfilesSyntaxError` if there are any syntax errors in the
    contents of *profiles_path*.

    The returned dictionary will be empty if no profiles or only empty
    profiles are present in *profiles_path*.
    """
    url_pattern_key = 'url'

    config = configparser.ConfigParser()
    logger.debug(Debug.LOADING_PROFILES.format(profiles_path))
    try:
        with profiles_path.open(encoding='utf-8-sig') as inifile:
            config.read_file(inifile)
    except (FileNotFoundError, PermissionError) as exc:
        raise ProfilesError(Messages.PROFILES_ERROR_MISSING_PROFILES.format(exc.filename)) from exc
    except configparser.Error as exc:
        errorname = type(exc).__name__.removesuffix(configparser.Error.__name__)
        raise ProfilesError(Messages.PROFILES_ERROR_PROFILES_WRONG_SYNTAX.format(errorname)) from exc

    profiles: dict[str, Profile] = {}
    parsers = [parser() for parser in BaseParser.__subclasses__()]
    for section in config.sections():
        if not config[section]:
            continue
        parser_config = build_parser_config(config, section)
        url_pattern = parser_config.pop(url_pattern_key, None)
        if url_pattern is None:
            raise ProfilesError(Messages.PROFILES_ERROR_PROFILE_WITHOUT_URL.format(section))
        for parser in parsers:
            if parser_config.keys() == parser.PARAMETERS:
                break
        else:
            raise ProfilesError(Messages.PROFILES_ERROR_PROFILE_WRONG_PARAMETERS.format(section))
        profiles[section] = Profile(url_pattern, parser, parser_config)
    if not profiles:
        raise ProfilesError(Messages.PROFILES_ERROR_EMPTY_PROFILES.format(profiles_path))
    return profiles


def is_url(value: str) -> bool:
    """Check whether *value* is a URL, for this program's needs.

    A URL is a string starting with a scheme of at least two characters
    followed by `://`. The two-character minimum keeps a Windows drive
    letter from being taken for a scheme.

    Only the shape is checked, not the actual validity.
    """
    return URL_PATTERN.match(value) is not None


def parse_arguments(*args: str) -> Generator[Gateway]:
    """Parse **args*.

    Parse each argument in **args*, identify its type and check if it is
    supported. If so, build the corresponding `Gateway` and yield it.
    """
    for arg in args:
        clean_arg = arg.strip()
        lowercase_arg = clean_arg.lower()

        logger.debug(Debug.PROCESSING_ARG.format(clean_arg))
        gateway: Gateway
        if not clean_arg:
            continue
        if is_url(clean_arg):
            logger.debug(Debug.ARG_IS_SINGLE_URL)
            gateway = SingleUrlGateway(clean_arg)
        elif lowercase_arg.endswith(TEXTFILE_SUFFIX):
            logger.debug(Debug.ARG_IS_TEXTFILE)
            gateway = TextFileGateway(clean_arg)
        elif lowercase_arg.endswith(SPREADSHEET_SUFFIX):
            logger.debug(Debug.ARG_IS_SPREADSHEET)
            gateway = SpreadSheetGateway(clean_arg)
        else:
            logger.debug(Debug.ARG_IS_UNSUPPORTED)
            gateway = UnsupportedGateway(clean_arg)
        yield gateway


class Gateway(ABC):
    """Base class for gateways.

    A `Gateway` supplies unique URLs from its source in first appearance
    order, and stores their metadata into its sink.
    """

    SINK_STEM = '_out'

    def __init__(self, source: str, *args: object, **kwargs: object) -> None:
        """."""
        super().__init__(*args, **kwargs)
        self.source_path = Path(source)
        self.sink_path = self.generate_sink_path()
        self.urls: list[Url]= []
        self._label = source.strip()

    @property
    def label(self) -> str:
        """."""
        return self._label

    def generate_sink_path(self) -> Path:
        """Generate the sink file path from `self.source`."""
        return self.source_path.with_stem(self.source_path.stem + self.SINK_STEM)

    @final
    def get_urls(self) -> list[Url]:
        """Return the URLs found in this gateway's source.

        This returns *unique* URLs, in order of first appearance.

        Handles some `OSError` exceptions translating them to the more
        precise corresponding `GatewayError'.
        """
        try:
            unique_urls = list(dict.fromkeys(self._get_urls()))
        except FileNotFoundError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND) from exc
        except PermissionError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_NO_PERMISSION) from exc
        self.urls = unique_urls
        return self.urls

    @final
    def save_metadata(self, results: SkimResults) -> None:
        """Save *results* metadata to this gateway's sink.

        Raise `GatewayError` if *results* contains no metadata at all.
        This is checked first, so no I/O is involved in that case.

        Otherwise, the URLs are retrieved again from the source, using
        `get_urls()`, before saving anything. That way the sink reflects
        the source as it is at saving time, not as it was when the URLs
        were first read. As a consequence, any `GatewayError` that the
        `get_urls()` call can raise will be raised here too.

        Handles some `OSError` exceptions translating them to the more
        precise corresponding `GatewayError`.
        """
        if not any(results.values()):
            raise GatewayError(Messages.GATEWAY_ERROR_NO_RESULTS_TO_SAVE)
        self.get_urls()
        try:
            return self._save_metadata(results)
        except PermissionError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_OUTPUT_FILE_NO_PERMISSION) from exc
        except FileNotFoundError as exc:
            if exc.filename is not None and Path(exc.filename) == self.source_path:
                raise GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND) from exc
            raise GatewayError(Messages.GATEWAY_ERROR_OUTPUT_FILE_NOT_FOUND) from exc

    @abstractmethod
    def _get_urls(self) -> list[Url]:
        """Actual implementation of `get_urls()`."""

    @abstractmethod
    def _save_metadata(self, results: SkimResults) -> None:
        """Actual implementation of `save_metadata()`."""


class UnsupportedGateway(Gateway):
    """Represents an unsupported gateway."""

    def _get_urls(self) -> list[Url]:
        """Raise, since this gateway type is not supported."""
        raise GatewayError(Messages.GATEWAY_ERROR_UNSUPPORTED_GATEWAY)

    def _save_metadata(self, results: SkimResults) -> None:
        """Not reachable.

        `save_metadata()` retrieves the URLs with `get_urls()` before
        calling this method, and for this gateway type it always raises.
        """
        raise NotImplementedError


class SingleUrlGateway(Gateway):
    """Represents a gateway providing a single URL.

    The metadata for the URL is logged with `logging.INFO` level, so it
    will be printed on `sys.stdout` in addition to the corresponding log
    file, and will be also written as key-value pairs into a text sink
    file whose name is based on a properly sanitized version of the URL.

    The text sink file has UTF-8 encoding.
    """

    HEADER = '{}\n\n'
    METADATA_PAIR = '[{:{width}}] {}\n'

    def __init__(self, source: str, *args: object, **kwargs: object) -> None:
        """."""
        super().__init__(source, *args, **kwargs)
        self.urls = self._get_urls()
        self.source_path = self.__url_to_path()
        self.sink_path = self.generate_sink_path()

    def _get_urls(self) -> list[Url]:
        """Return this gateway's single URL."""
        return [self.label]

    def _save_metadata(self, results: SkimResults) -> None:
        """Save *results* metadata to a text file sink."""
        metadata = results.get(self.urls[0])
        if not metadata:
            return

        with self.sink_path.open('w', encoding='utf-8') as sink:
            logger.debug(Debug.DUMPING_METADATA_TO_SINK.format(self.sink_path))
            sink.write(self.HEADER.format(self.urls[0]))
            width = max(map(len, metadata))
            for key, value in metadata.items():
                logger.debug(Debug.DUMPING_METADATA_K_V.format(key, value))
                message = self.METADATA_PAIR.format(key, value, width=width)

                # Console output allowed here because it is part of the
                # gateway documented and expected behavior.
                logger.indent()
                logger.info(message.rstrip())
                logger.dedent()
                sink.write(message)

    def __url_to_path(self) -> Path:
        """Convert the *url* to a valid path with the correct suffix.

        The method is quite crude but it works: replace every ASCII non
        word characters (potentially unsafe when they are present in a
        path) by a visually unobtrusive character which is safe to use
        while keeping the path readable.
        """
        return Path(re.sub(r'\W', '_', self.urls[0], flags=re.ASCII).rstrip('. ')).with_suffix(TEXTFILE_SUFFIX)


class TextFileGateway(Gateway):
    """Represents a gateway to a text file containing URLs.

    There must be a single URL per file line. URLs can be repeated and
    there can be interspersed empty lines. Encoding must be `UTF-8`.

    Metadata is written to a text file with `UTF-8` encoding, containing
    one record per distinct URL found in the input in order of its first
    appearance. Repeated URLs do not produce repeated records.

    Each record has a first unindented line with the URL, and then all
    the metadata pairs on separate indented lines. Records are separated
    by an empty line. URLs for which no metadata was obtained do not get
    a record.
    """

    METADATA_HEADER = '{}\n'
    METADATA_PAIR = '  {}: {}\n'
    METADATA_FOOTER = '\n'

    def _get_urls(self) -> list[Url]:
        """Return all urls in the input file, stripped."""
        try:
            with self.source_path.open(encoding='utf-8-sig') as source_file:
                lines = source_file.read().splitlines()
        except UnicodeDecodeError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_INPUT_TEXT_FILE_NOT_UTF_8) from exc
        return [line.strip() for line in lines if line.strip()]

    def _save_metadata(self, results: SkimResults) -> None:
        """Save *results* metadata to a text file sink."""
        with self.sink_path.open('w', encoding='utf-8') as sink:
            logger.debug(Debug.DUMPING_METADATA_TO_SINK.format(self.sink_path))
            for url in self.urls:
                if url not in results:
                    continue
                if not (metadata := results[url]):
                    continue
                sink.write(self.METADATA_HEADER.format(url))
                for key, value in metadata.items():
                    logger.debug(Debug.DUMPING_METADATA_K_V.format(key, value))
                    sink.write(self.METADATA_PAIR.format(key, value))
                sink.write(self.METADATA_FOOTER)


class SpreadSheetGateway(Gateway):
    """Represents a gateway to an Excel-like spreadsheet file.

    Only one sheet (the first one) is supported, and only the first URL
    in a row is used. URLs can be repeated and there can be interspersed
    empty rows.

    Metadata is written to a copy of the original spreadsheet file, with
    a name based upon the original, on new columns.

    A heading row is inserted at the top of the sheet to hold the column
    headers, so the original rows are shifted down by one in the copy.

    A repeated URL is processed only once, but its metadata is written
    on every row where the URL appears. Rows whose URL got no metadata
    are left untouched.
    """

    ADDED_METADATA_COLUMN_HEADER = '[sm] {}'
    ADDED_CELLS_FONT = 'Calibri'
    ADDED_CELLS_COLOR = 'baddad'
    ADDED_CELLS_FILL = 'solid'

    def __init__(self, source: str, *args: object, **kwargs: object) -> None:
        """."""
        super().__init__(source, *args, **kwargs)
        self.sink_sheet: Worksheet | None = None
        self.url_rows: dict[Url, list[int]] = {}
        self.known_metadata: dict[MetadataKey, int] = {}

    def _get_urls(self) -> list[Url]:
        """Return all URLs in the input file, stripped.

        NOTE: only the first sheet is processed, because (allegedly…) it
        is the one where the URLs are.
        """
        try:
            source_workbook = load_workbook(self.source_path)
        except (KeyError, BadZipFile) as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_SOURCE_SHEET_IS_INVALID) from exc
        source_sheet = source_workbook.worksheets[0]
        logger.debug(Debug.WORKING_SHEET.format(source_sheet.title))
        self.url_rows = {}
        all_urls: list[Url] = []
        for row in source_sheet.rows:
            row_number = row[0].row
            if not row_number:
                continue
            logger.debug(Debug.PROCESSING_ROW.format(row_number))
            if (url := self.__get_url_from_row(row)) is None:
                continue
            url = url.strip()
            all_urls.append(url)
            self.url_rows.setdefault(url, []).append(row_number)
        source_workbook.close()
        return all_urls

    def _save_metadata(self, results: SkimResults) -> None:
        """Save *results* metadata to a spreadsheet file sink."""
        logger.debug(Debug.COPYING_WORKBOOK.format(self.sink_path))
        copy2(self.source_path, self.sink_path)

        sink_workbook = load_workbook(self.sink_path)
        self.sink_sheet = sink_workbook.worksheets[0]

        logger.debug(Debug.INSERTING_HEADING_ROW)
        self.sink_sheet.insert_rows(1, 1)

        self.known_metadata = {}
        for url, rows in self.url_rows.items():
            if url in results:
                for row in rows:
                    self.__store_metadata(row, results[url])
        sink_workbook.save(self.sink_path)
        sink_workbook.close()

    @staticmethod
    def __get_url_from_row(row: tuple[Cell | MergedCell, ...]) -> Url | None:
        """Find first URL in row."""
        url = None
        for cell in row:
            if cell.data_type != CELLTYPE_STRING:
                logger.debug(Debug.NONSTRING_CELL.format(cell.coordinate))
                continue
            value = str(cell.value).strip()
            if is_url(value):
                url = value
                logger.debug(Debug.URL_FOUND_IN_CELL.format(cell.coordinate, url))
                break  # Only the FIRST URL found is considered.
        return url

    def __store_metadata(self, row: int, metadata: Metadata) -> None:
        """Store *metadata* in *self.sink_sheet* at given *row*.

        For new metadata keys a new column is added to *self.sink_sheet*
        and the value is added there. For already existing metadata keys
        the value is added to the corresponding existing column.

        The new columns are marked with a prefix so they are easier to
        recognize, filter and process later.
        """
        cell_font = self.ADDED_CELLS_FONT
        cell_color = self.ADDED_CELLS_COLOR
        cell_fill = self.ADDED_CELLS_FILL

        sheet = self.sink_sheet
        if sheet is None:
            return
        for key, value in metadata.items():
            if key not in self.known_metadata:
                column_header = self.ADDED_METADATA_COLUMN_HEADER.format(key)
                logger.debug(Debug.NEW_METADATA_FOUND.format(key))
                column = sheet.max_column + 1
                self.known_metadata[key] = column
                logger.debug(Debug.METADATA_STORED_IN_COLUMN.format(key, get_column_letter(column)))
                cell = sheet.cell(row=1, column=column, value=column_header)
                cell.font = Font(name=cell_font)
                cell.fill = PatternFill(fgColor=cell_color, fill_type=cell_fill)
                # Set column width.
                #
                # As per Excel specification, the width of the zero char
                # in the font used by the `Normal` style in a workbook
                # is the unit for all the widths. So a column of width
                # 42 would fit 42 zero characters in the font specified
                # by the 'Normal' style.
                #
                # No, no kidding.
                #
                # Since this width units are, IMNSHO, totally arbitrary,
                # let's choose an arbitrary column width, so 42.
                #
                # To wit, the Answer to the Ultimate Question of Life,
                # the Universe, and Everything.
                sheet.column_dimensions[get_column_letter(column)].width = 42
                # This is needed because in some occasions Excel files
                # are not properly generated and the last column has a
                # *max* field too large, and that implies an unintended
                # consequence: **ANY** change to the settings of that
                # column affects ALL the following ones whose index is
                # less than *max*… So, it's better to fix that field.
                sheet.column_dimensions[get_column_letter(column)].max = column
            logger.debug(Debug.DUMPING_METADATA_K_V.format(key, value))
            # There is a one row offset because of the added headers.
            sheet.cell(row + 1, self.known_metadata[key], value=value)


def get_parser(url: Url, profiles: dict[str, Profile]) -> BaseParser:
    """Return the appropriate parser for the *url*.

    The appropriate parser is retrieved by finding the needed profile
    within *profiles* whose 'url_pattern' matches the given *url*. Then,
    the parser is returned after being properly configured to handle the
    *url* contents.
    """
    for profile_name, profile in profiles.items():
        if profile.url_pattern.search(url):
            logger.debug(Debug.PROFILE_ID.format(profile_name, type(profile.parser).__name__))
            profile.parser.configure(profile.parser_config)
            return profile.parser
    raise SkimmingError(Messages.SKIMMING_ERROR_NO_MATCHING_PROFILE)


def saca_las_mantecas(url: Url, parser: BaseParser) -> Metadata:
    """Saca las mantecas.

    Saca las mantecas from the given *url*, that is, retrieve contents,
    parse them using *parser*, and obtain library catalogue metadata, if
    any.

    Return obtained metadata as a dictionary.
    """
    try:
        contents, encoding = retrieve_url(url)
    except URLError as exc:
        # Depending on the particular error which happened, the reason
        # attribute of the 'URLError' exception can be a simple error
        # message, an instance of some 'OSError' derived Exception, etc.
        # So, in order to have useful messages, some discrimination has
        # to be done here.
        if isinstance(exc.reason, OSError):
            reason = Messages.URL_ACCESS_REASON_OSLIKE_ERROR.format(type(exc.reason).__name__)
        elif isinstance(exc, HTTPError):
            reason = Messages.URL_ACCESS_REASON_HTTP_ERROR.format(exc.code)
        else:
            reason = Messages.URL_ACCESS_REASON_UNEXPECTED_ERROR
        raise SkimmingError(Messages.SKIMMING_ERROR_URL_ACCESS.format(reason)) from exc
    # Apparently, 'HTTPException', 'ConnectionError' and the subclasses
    # are masked or wrapped by 'urllib', and documentation is not very
    # informative. So, just in case something weird happen, it is better
    # to handle these exception types here as well.
    except HTTPException as exc:
        raise SkimmingError(Messages.SKIMMING_ERROR_ERROR_HTTP_RETRIEVAL.format(type(exc).__name__)) from exc
    except ConnectionError as exc:
        error_code = errno.errorcode.get(exc.errno) if exc.errno else None
        if error_code is None:
            raise SkimmingError(Messages.SKIMMING_ERROR_CONNECTION_FAILED_UNKNOWN_REASON) from exc
        raise SkimmingError(Messages.SKIMMING_ERROR_CONNECTION_FAILED.format(error_code)) from exc

    if not contents:
        raise SkimmingError(Messages.SKIMMING_ERROR_NO_CONTENTS)

    parser.feed(contents.decode(encoding))
    parser.close()
    if retrieved_metadata := parser.get_metadata():
        return retrieved_metadata
    raise SkimmingError(Messages.SKIMMING_ERROR_NO_METADATA_FOUND)


def retrieve_url(url: Url) -> tuple[bytes, str]:
    """Retrieve contents from *url*.

    First resolve any `meta http-equiv="Refresh"` redirection for *url*
    and then get the contents as a byte string.

    Then, detect the contents encoding (in HTML jargon, the charset).

    Return a (contents, charset) tuple.
    """
    current_url: Url | None = url

    if url.startswith('file://'):
        current_url = resolve_file_url(url)

    contents = b''
    charset = ''
    headers = {'User-Agent': USER_AGENT}
    while current_url:
        logger.debug(Debug.PROCESSING_URL.format(current_url))
        with urlopen(Request(current_url, headers=headers)) as response:  # noqa: S310
            # First, check if any redirection is needed and try to get
            # the charset the easy way.
            contents = response.read()
            charset = response.headers.get_content_charset()
        current_url = get_redirected_url(contents, current_url)

    # In this point, we have the contents as a byte string.
    # If the charset is 'None', it has to be determined the hard way.
    if not charset:
        logger.debug(Debug.CHARSET_NOT_IN_HEADERS)
        charset = detect_html_charset(contents)
    else:
        logger.debug(Debug.CHARSET_IN_HEADERS)
    logger.debug(Debug.CONTENTS_ENCODING.format(charset))

    return contents, charset


def resolve_file_url(url: Url) -> Url:
    """Resolve relative paths in `file:` *url*."""
    parsed_url = urlparse(url)
    resolved_path = unquote(parsed_url.path[1:])
    resolved_path = Path(resolved_path).resolve().as_posix()
    resolved_path = quote(resolved_path, safe=':/')
    return parsed_url._replace(path='/' + resolved_path).geturl()


def get_redirected_url(contents: bytes, base_url: Url) -> Url | None:
    """Get redirected URL, if any, from *contents*.

    Get redirected URL from a `meta http-equiv="refresh"` pragma in the
    contents. Use *base_url* as base URL for redirection, if some parts
    are missing in the URL specified by the pragma.

    Return redirected URL, or `None` if there is no redirection pragma.
    """
    meta_refresh_re = rb'<meta http-equiv="refresh" content="(?:[^;]+;\s+)?URL=([^"]+)"'
    url_fields_to_reuse = ('scheme', 'netloc')

    if match := re.search(meta_refresh_re, contents, re.IGNORECASE):
        parsed_url = urlparse(base_url)
        redirected_url = urlparse(match.group(1).decode('ascii'))
        for field in parsed_url._fields:
            value = getattr(parsed_url, field)
            # If not specified in the obtained redirected URL, both the
            # scheme and netloc will be reused from the base URL. Any
            # other field will be obtained from the redirected URL and
            # used, no matter if it is empty.
            if field in url_fields_to_reuse and not getattr(redirected_url, field):
                redirected_url = redirected_url._replace(**{field: value})
        redirected_url = urlunparse(redirected_url)
        logger.debug(Debug.REDIRECTED_URL.format(redirected_url))
        return redirected_url
    return None


def detect_html_charset(contents: bytes) -> str:
    """Obtain charset for *content* from HTML tags, if any.

    If the charset can not be determined a sane fallback (ISO-8859-1) is
    used. It may look like UTF-8 would be such a sane fallback, because
    some webpages may NOT specify any encoding if they are using UTF-8
    and it is identical to ASCII for 7-bit codepoints, but the problem
    is that UTF-8 will fail for webpages whose encoding is any ISO/IEC
    8859 variant.

    So, the default is based on the encoding most frequently used by the
    webpages this program will generally process.
    """
    fallback_charset = 'ISO-8859-1'
    meta_http_equiv_charset_re = rb'<meta http-equiv="content-type".*charset="([^"]+)"'
    meta_charset_re = rb'<meta charset="([^"]+)"'

    charset = fallback_charset
    if match := re.search(meta_http_equiv_charset_re, contents, re.IGNORECASE):
        # Next best thing, from the meta http-equiv="content-type".
        logger.debug(Debug.CHARSET_FROM_HTTP_EQUIV)
        charset = match.group(1).decode('ascii')
    elif match := re.search(meta_charset_re, contents, re.IGNORECASE):
        # Last resort, from some meta charset, if any…
        logger.debug(Debug.CHARSET_FROM_META_CHARSET)
        charset = match.group(1).decode('ascii')
    else:
        logger.debug(Debug.CHARSET_FROM_DEFAULT)
    return charset


def collect_urls(gateway: Gateway) -> list[Url]:
    """Collect URLs from a gateway, handling errors.

    Retrieve the URLs from *gateway* using its `get_urls()` method. If
    that raises a `GatewayError`, log the exception, emit a warning and
    treat the result as empty.

    If *gateway* provides no URLs, a warning is emitted, too.

    Return the list of collected URLs, which is empty if the *gateway*
    could not be read or its source contains no URLs.
    """
    urls: list[Url] = []
    logger.indent()
    try:
        urls = gateway.get_urls()
    except GatewayError as exc:
        log_exception(exc)
        warning(str(exc))
    else:
        if not urls:
            warning(Messages.WARNING_GATEWAY_EMPTY)
    logger.dedent()
    return urls


def process_urls(urls: list[Url], profiles: dict[str, Profile]) -> SkimResults:
    """Process *urls*, obtaining the metadata for each one.

    For every URL in *urls*, find the adequate parser using *profiles*,
    retrieve its contents and extract the metadata. Progress is logged
    as each URL gets processed.

    A URL for which no metadata can be obtained is logged as a warning
    and left out of the results while processing continues.

    A summary is logged after processing is done.

    Return a dictionary mapping each successfully processed URL to its
    metadata, in the same order as *urls*. The dictionary is empty if
    no URL could be processed.
    """
    results: SkimResults = {}
    logger.indent()
    for url in urls:
        logger.info(url)
        try:
            results[url] = saca_las_mantecas(url, get_parser(url, profiles))
        except SkimmingError as exc:
            log_exception(exc)
            logger.indent()
            warning(str(exc))
            logger.dedent()
    summary_template = (
        Messages.URLS_RESULT_NONE if not results
        else Messages.URLS_RESULT_ONE if len(results) == 1
        else Messages.URLS_RESULT_MANY
    )
    summary = summary_template.format(len(results), len(urls))
    logger.info(Messages.URLS_RESULT.format(summary))
    logger.dedent()
    return results


def save_results(gateway: Gateway, results: SkimResults) -> bool:
    """Send *results* to *gateway*.

    Any `GatewayError` raised while saving is logged as a warning.

    Return `True` if the metadata was saved, `False` otherwise.
    """
    try:
        gateway.save_metadata(results)
    except GatewayError as exc:
        log_exception(exc)
        warning(str(exc))
        return False
    return True


@loggerize
@keyboard_interrupt_handler
@ensure_utf8_output
def main(*args: str) -> ExitCodes:  # pylint: disable=unused-variable
    """."""
    exitcode = ExitCodes.SUCCESS

    if not args:
        # Input arguments should be provided automatically when program
        # is used as a drag'n'drop target which is actually the intended
        # way of operation, generally speaking.
        #
        # But the program can be also run by hand from a command prompt,
        # so it is better to signal the end user with an error and give
        # an explanation if no input arguments are provided, as soon as
        # possible.
        error(Messages.ERROR_NO_ARGUMENTS)
        return ExitCodes.NO_ARGUMENTS

    try:
        profiles = load_profiles(Paths.INIFILE)
        logger.debug(Debug.FOUND_PROFILES.format(', '.join(profiles.keys())))
    except ProfilesError as exc:
        log_exception(exc)
        error(str(exc))
        return ExitCodes.ERROR

    for gateway in parse_arguments(*args):
        logger.info('')
        logger.info(Messages.GATEWAY_LABEL.format(gateway.label))
        logger.indent()

        logger.info(Messages.STEP_LOADING_URLS)
        urls = collect_urls(gateway)
        if urls:
            logger.info(Messages.STEP_PROCESSING_URLS)
            results = process_urls(urls, profiles)
            if len(results) != len(urls):
                exitcode = ExitCodes.WARNING
            if results:
                logger.info(Messages.STEP_SAVING_RESULTS)
                success = save_results(gateway, results)
                if not success:
                    exitcode = ExitCodes.WARNING
        else:
            exitcode = ExitCodes.WARNING
        logger.dedent()
    return exitcode
