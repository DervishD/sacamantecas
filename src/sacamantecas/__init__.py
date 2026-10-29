"""See 'README.md' for details."""
import sys

if sys.platform != 'win32':
    sys.exit('\nThis program is compatible only with the Win32 platform.')

# pylint: disable=wrong-import-position
from abc import ABC, abstractmethod
from configparser import ConfigParser, Error as ConfigParserError, UNNAMED_SECTION
from dataclasses import asdict, dataclass, fields
from enum import IntEnum, StrEnum
import errno
from functools import wraps
from html.parser import HTMLParser
from http.client import HTTPException
import logging
from pathlib import Path
import re
from shutil import copy2
import signal
import time
from typing import ClassVar, Final, final, NamedTuple, TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen
import warnings

from legion import ensure_utf8_output, format_message, get_logger
from openpyxl import load_workbook
from openpyxl.cell.cell import Cell, MergedCell, TYPE_STRING as CELLTYPE_STRING
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.cell import get_column_letter

from .about import BUILD, DEPENDENCIES, DEVELOPMENT_MODE, PROGRAM_NAME, REPOSITORY, USER_AGENT, VERSION

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from openpyxl.workbook.workbook import Workbook
    from openpyxl.worksheet.worksheet import Worksheet


@dataclass
class Settings:
    """Store program settings."""   # ruff: ignore[D204]
    DEFAULT_URL_RETRIEVAL_TIMEOUT_SECONDS: ClassVar[int] = 30
    DEFAULT_MAX_URL_REDIRECTIONS: ClassVar[int] = 5
    url_retrieval_timeout_seconds: int = DEFAULT_URL_RETRIEVAL_TIMEOUT_SECONDS
    max_url_redirections: int = DEFAULT_MAX_URL_REDIRECTIONS


class Profile(NamedTuple):
    """Abstraction for profiles."""  # ruff: ignore[D204]
    name: str
    url_pattern: re.Pattern[str]
    parser: BaseParser
    parser_config: ParserConfig

    def debug_log(self) -> None:
        """Log debug information to default logger."""
        logger.debug(Debug.PROFILE_NAME.format(self.name), stacklevel=2)
        logger.debug(Debug.PROFILE_URL_PATTERN.format(self.url_pattern.pattern), stacklevel=2)
        logger.debug(Debug.PROFILE_PARSER_TYPE.format(self.parser), stacklevel=2)
        logger.debug(Debug.PROFILE_PARSER_PARAMETERS, stacklevel=2)
        logger.indent()
        for key, value in self.parser_config.items():
            logger.debug(Debug.PROFILE_PARSER_PARAM.format(key, value.pattern), stacklevel=2)
        logger.dedent()


type MetadataKey = str
type MetadataValue = str
type Metadata = dict[MetadataKey, MetadataValue]
type RawMetadata = dict[MetadataKey, list[MetadataValue]]
type Url = str
type SkimResults = dict[Url, Metadata]
type ParserConfig = dict[str, re.Pattern[str]]


class Paths:  # pylint: disable=too-few-public-methods
    """Program paths."""

    _PROGRAM_ROOT: Final[Path] = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
    _LOGFILE_STEM: Final[str] = '' if DEVELOPMENT_MODE else time.strftime('_%Y%m%d_%H%M%S')
    _LOGFILE_SUFFIX: Final[str] = '.txt'

    MAIN_LOG: Final[Path] = _PROGRAM_ROOT / f'{PROGRAM_NAME}_log{_LOGFILE_STEM}{_LOGFILE_SUFFIX}'
    FULL_LOG: Final[Path] = _PROGRAM_ROOT / f'{PROGRAM_NAME}_trace{_LOGFILE_STEM}{_LOGFILE_SUFFIX}'
    INIFILE: Final[Path] = _PROGRAM_ROOT / f'{PROGRAM_NAME}.ini'


class Messages(StrEnum):
    """End-user messages."""

    # Helpers.
    ERROR_PREFIX = '\n*** Error: '
    WARNING_PREFIX = '* Aviso: '
    MARKER = '·'
    QUOTED = '«{}»'
    LIST_SEPARATOR = ', '

    # General messages.
    PRESS_ANY_KEY = '\nPulse cualquier tecla para continuar...'
    PROGRAM_BANNER = f'{PROGRAM_NAME} versión {BUILD if DEVELOPMENT_MODE else VERSION} ({REPOSITORY})'
    PROCESS_DONE = 'Proceso finalizado'
    DEFAULT_ERROR_MESSAGE = 'No hay más información sobre el error'
    DEFAULT_WARNING_MESSAGE = 'No hay más información sobre el aviso'

    # Main loop messages.
    LOADING_INIFILE = f'Leyendo fichero de configuración {QUOTED}'
    SETTING_LABEL = 'Ajuste: {} = {}'
    PROFILE_LABEL = f'Perfil: {QUOTED.format('{0}')} ({{1.__class__.__name__}})'
    PROCESSING_GATEWAY = 'Procesando fuente: {}'
    STEP_LOADING_URLS = f'{MARKER}Obteniendo URLs'
    STEP_PROCESSING_URLS = f'{MARKER}Sacando las mantecas'
    URLS_RESULT = '=> {}'
    URLS_RESULT_NONE = 'Ninguna URL procesada de un total de {1}'
    URLS_RESULT_ONE = '1 URL procesada de un total de {1}'
    URLS_RESULT_MANY = '{0} URLs procesadas de un total de {1}'
    STEP_SAVING_RESULTS = f'{MARKER}Guardando metadatos'

    # Warning messages.
    WARNING_KEYBOARD_INTERRUPT = 'El usuario interrumpió la operación de la aplicación.'
    WARNING_GATEWAY_EMPTY = 'La fuente no contiene ningún URL'

    # Generic error messages.
    ERROR_UNHANDLED_EXCEPTION = 'Excepción sin gestionar'
    ERROR_NO_ARGUMENTS = (
        'No se han especificado fuentes de entrada para ser procesadas.\n'
        '\n'
        'Arrastre y suelte un fichero de entrada sobre el icono de la aplicación,\n'
        'o bien proporcione los nombres de las fuentes de entrada como argumentos.'
    )

    # INI file handling errors.
    INIFILE_ERROR_FILE_NOT_FOUND = f'No se encontró el fichero de configuración {QUOTED}'
    INIFILE_ERROR_FILE_NO_PERMISSION = f'No hay permisos suficientes para leer el fichero de configuración {QUOTED}'
    INIFILE_ERROR_FILE_READ_FAILED = f'No se pudo leer el fichero de configuración {QUOTED}'
    INIFILE_ERROR_FILE_NOT_UTF_8 = f'El fichero de configuración {QUOTED} no está codificado en UTF-8'
    INIFILE_ERROR_NO_VALID_PROFILES = f'No se encontraron perfiles válidos en el fichero de configuración {QUOTED}'
    INIFILE_ERROR_WRONG_SYNTAX = f'Sintaxis incorrecta {{}} en el fichero de configuración {QUOTED}'

    # Settings handling errors.
    SETTINGS_ERROR_UNKNOWN_KEYS = 'Se encontraron ajustes desconocido: {}'
    SETTINGS_ERROR_INVALID_VALUE = f'El ajuste {QUOTED} tiene un valor con formato incorrecto ({QUOTED})'

    # Profile handling errors.
    PROFILE_ERROR_EMPTY_PROFILE = f'El perfil {QUOTED} está vacío'
    PROFILE_ERROR_PROFILE_WITHOUT_URL = f'El perfil {QUOTED} no incluye un patrón de URL'
    PROFILE_ERROR_PROFILE_WRONG_PARAMETERS = f'El perfil {QUOTED} no contiene parámetros correctos'
    PROFILE_ERROR_NO_MATCHING_PROFILE = 'No se encontró un perfil para procesar el URL'
    PROFILE_ERROR_INVALID_REGEX = (
        f'Expresión regular incorrecta en el perfil {QUOTED.format('{0}')}, parámetro {QUOTED.format('{1}')}:\n'
        '  {2}\n'
        '  {2:_<{3}.0}^\n'
        '  [{4}: {5}]'
    )

    # Gateway errors.
    GATEWAY_ERROR_UNSUPPORTED_GATEWAY = 'La fuente no es de un tipo admitido'
    GATEWAY_ERROR_INPUT_FILE_NOT_FOUND = 'No se encontró el fichero de entrada'
    GATEWAY_ERROR_OUTPUT_FILE_NOT_FOUND = 'No se encontró el fichero de salida'
    GATEWAY_ERROR_INPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para leer el fichero de entrada'
    GATEWAY_ERROR_OUTPUT_FILE_NO_PERMISSION = 'No hay permisos suficientes para crear el fichero de salida'
    GATEWAY_ERROR_INPUT_FILE_READ_FAILED = 'No se pudo leer el fichero de entrada'
    GATEWAY_ERROR_OUTPUT_FILE_WRITE_FAILED = 'No se pudo escribir el fichero de salida'
    GATEWAY_ERROR_NO_RESULTS_TO_SAVE = 'No hay metadatos para esta fuente'
    GATEWAY_ERROR_INPUT_TEXT_FILE_NOT_UTF_8 = 'El fichero de entrada no está codificado en UTF-8'
    GATEWAY_ERROR_SOURCE_SHEET_IS_INVALID = 'La hoja de entrada es inválida'

    # Skimming errors.
    SKIMMING_ERROR_URL_ACCESS = 'No resultó posible acceder a la dirección especificada ({})'
    URL_ACCESS_REASON_OSLIKE_ERROR = '{}'
    URL_ACCESS_REASON_HTTP_ERROR = 'respuesta HTTP {}'
    URL_ACCESS_REASON_UNEXPECTED_ERROR = 'error inesperado'
    SKIMMING_ERROR_TOO_MANY_REDIRECTIONS = 'Demasiadas redirecciones accediendo al URL (máximo: {})'
    SKIMMING_ERROR_ERROR_HTTP_RETRIEVAL = 'No se obtuvieron contenidos, error de protocolo HTTP {}'
    SKIMMING_ERROR_CONNECTION_FAILED = 'Se produjo un error de conexión {} accediendo al URL'
    SKIMMING_ERROR_CONNECTION_FAILED_UNKNOWN_REASON = 'Se produjo un error de conexión desconocido accediendo al URL'
    SKIMMING_ERROR_TIMEOUT = 'Se agotó el tiempo de espera accediendo al URL'
    SKIMMING_ERROR_UNKNOWN_CHARSET = f'El charset {QUOTED} es desconocido, es imposible decodificar los contenidos'
    SKIMMING_ERROR_EMPTY_CHARSET = 'El charset está vacío, es imposible decodificar los contenidos'
    SKIMMING_ERROR_INVALID_URL = 'El URL no tiene un formato válido'
    SKIMMING_ERROR_NO_CONTENTS = 'No se recibieron contenidos del URL'
    SKIMMING_ERROR_UNDECODABLE_CONTENTS = f'No se pudieron decodificar los contenidos con el charset {QUOTED}'
    SKIMMING_ERROR_NO_METADATA_FOUND = 'No se obtuvieron metadatos'


class Debug(StrEnum):
    """Trace (debugging) messages."""

    # General messages.
    DEBUGGING_INIT = 'Registro de depuración iniciado'
    DEBUGGING_DONE = 'Registro de depuración finalizado'
    DEPENDENCY_BANNER = 'Usando paquete {}'
    USER_AGENT_LABEL = f'User-Agent: {USER_AGENT}'

    # Exception logging.
    EXCEPTION_LOG = 'Se lanzó una excepción {}'
    EXCEPTION_LOG_NO_CONTEXT = 'La excepción no contiene contexto'
    EXCEPTION_LOG_CONTEXT = (
        '  __context__ -> {}\n'
        '  __repr__    -> {}\n'
        '  __str__     -> {}\n'
    )

    # Argument parsing.
    PROCESSING_ARG = f'Procesando argumento {Messages.QUOTED}'
    ARG_IS_SINGLE_URL = 'El argumento es de tipo single_url'
    ARG_IS_TEXTFILE = 'El argumento es de tipo textfile'
    ARG_IS_SPREADSHEET = 'El argumento es de tipo spreadsheet'
    ARG_IS_UNSUPPORTED = 'El argumento no es de un tipo admitido'

    # Settings handling.
    PARSING_SETTINGS = 'Procesando ajustes'
    MISSING_SETTINGS = f'El fichero {Messages.QUOTED} no contiene ajustes'

    # Profiles handling.
    PARSING_PROFILES = 'Procesando perfiles'
    PROFILE_NAME =        f'Nombre        : {Messages.QUOTED}'
    PROFILE_URL_PATTERN = f'Patrón de URL : {Messages.QUOTED}'
    PROFILE_PARSER_TYPE =  'Tipo de parser: {0.__class__.__name__}'
    PROFILE_PARSER_PARAMETERS = 'Parámetros del parser:'
    PROFILE_PARSER_PARAM = f'{Messages.QUOTED} = {Messages.QUOTED}'
    PROFILE_ID = f'Perfil y tipo de catálogo: {Messages.QUOTED}/{Messages.QUOTED}'

    # URL retrieval.
    PROCESSING_URL = f'Procesando URL {Messages.QUOTED}'
    REDIRECTED_URL = f'URL redirigido a {Messages.QUOTED}'
    CHARSET_NOT_IN_HEADERS = 'Charset no detectado en las cabeceras'
    CHARSET_FROM_HTTP_EQUIV = 'Charset detectado mediante meta http-equiv'
    CHARSET_FROM_META_CHARSET = 'Charset detectado mediante meta charset'
    CHARSET_FROM_DEFAULT = 'Charset no detectado, usando valor por defecto'
    CHARSET_IN_HEADERS = 'Charset detectado en las cabeceras'
    CONTENTS_ENCODING = f'Contenidos codificados con charset {Messages.QUOTED}'

    # Gateways.
    DUMPING_METADATA_TO_SINK = f'Volcando metadatos a {Messages.QUOTED}'
    DUMPING_METADATA_K_V = f'Añadiendo metadato {Messages.QUOTED} con valor {Messages.QUOTED}'
    WORKING_SHEET = f'La hoja con la que se trabajará es {Messages.QUOTED}'
    WORKBOOK_WARNING = 'Advertencia {} al cargar el workbook «{}»: {}'
    PROCESSING_ROW = 'Procesando fila {}'
    COPYING_WORKBOOK = f'Copiando workbook a {Messages.QUOTED}'
    INSERTING_HEADING_ROW = 'Insertando fila de cabeceras'
    NONSTRING_CELL = 'La celda {} no es de tipo cadena, será ignorada'
    URL_FOUND_IN_CELL = f'Se encontró un URL en la celda {{}}: {Messages.QUOTED}'
    NEW_METADATA_FOUND = f'Se encontró un metadato nuevo: {Messages.QUOTED}'
    METADATA_STORED_IN_COLUMN = f'El metadato {Messages.QUOTED} irá en la columna {{}}'

    # Parsers.
    HTML_START_TAG = '➜ HTML <{}{}{}>'
    METADATA_KEY_FOUND = f'Se encontró la clave {Messages.QUOTED}'
    METADATA_VALUE_FOUND = f'Se encontró el valor {Messages.QUOTED}'
    METADATA_IS_EMPTY = 'Metadato vacío'
    METADATA_MISSING_VALUE = f'Metadato {Messages.QUOTED} incompleto, ignorando'
    METADATA_MISSING_KEY = f'No se encontró una clave, usando {Messages.QUOTED}'
    METADATA_OK = f'Metadato correcto {Messages.QUOTED}: {Messages.QUOTED}'
    METADATA_KEY_MARKER_FOUND = f'Se encontró una marca de clave {Messages.QUOTED}'
    METADATA_VALUE_MARKER_FOUND = f'Se encontró una marca de valor {Messages.QUOTED}'
    METADATA_MARKER_FOUND = f'Se encontró una marca de metadato {Messages.QUOTED}'
    PARSER_NESTING_ERROR_K_IN_V = 'Problema de anidación (clave dentro de valor), restableciendo parser'
    PARSER_NESTING_ERROR_V_IN_K = 'Problema de anidación (valor dentro de clave), restableciendo parser'


class ExitCodes(IntEnum):
    """Customized exit codes."""  # ruff: ignore[D204]
    SUCCESS = 0
    # 1 is reserved, used as exitcode by Python unhandled exceptions.
    NO_ARGUMENTS = 2
    WARNING = 3
    ERROR = 4
    KEYBOARD_INTERRUPT = 128 + signal.SIGINT


logger = get_logger(PROGRAM_NAME)
program_settings = Settings()


class CharsetError(LookupError):
    """Raise when the charset for content decoding is invalid."""

    def __init__(self, charset: str) -> None:
        """."""
        super().__init__(charset)
        self.charset = charset

class TooManyRedirectionsError(Exception):
    """Raise when a URL redirects more times than allowed."""

    def __init__(self, limit: int) -> None:
        """."""
        super().__init__(limit)
        self.limit = limit

class IniFileError(Exception):
    """Raise for INI file related errors."""

class SettingsError(Exception):
    """Raise for settings related errors."""

class ProfileError(Exception):
    """Raise for profile related errors."""

class GatewayError(Exception):
    """Raise for gateway related errors."""

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
        for attr_name, attr_value in attrs:
            if attr_value is None:
                continue
            if attr_name == self.CLASS_ATTR and (match := self.config[self.K_CLASS].search(attr_value)):
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
            if attr_name == self.CLASS_ATTR and (match := self.config[self.V_CLASS].search(attr_value)):
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # ruff: ignore[C901]
        """Handle opening tags."""
        super().handle_starttag(tag, attrs)
        if not self.within_meta:
            if not self.config[self.M_TAG].fullmatch(tag):
                return
            for attr_name, attr_value in attrs:
                if attr_value is None:
                    continue
                if self.config[self.M_ATTR].fullmatch(attr_name) and self.config[self.M_VALUE].search(attr_value):
                    logger.debug(Debug.METADATA_MARKER_FOUND.format(attr_value))
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


def error(message: str) -> None:
    """Preprocess and log error *message*.

    First, the initial letter of *message* is lowercased. Then, a fixed
    prefix is prepended. Finally, the resulting string is formatted by
    using `legion.format_message()`, that is, if *message* has multiple
    lines, then the first one is considered a heading, and the remaining
    lines are indented.

    The result is logged using `logger.error()`.
    """
    logger.set_indent(0)
    heading, _, remaining = message.partition('\n')
    if not heading:
        heading = Messages.DEFAULT_ERROR_MESSAGE
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
    processed_message = message or Messages.DEFAULT_WARNING_MESSAGE
    logger.warning('%s', f'{Messages.WARNING_PREFIX}{processed_message[0].lower() + processed_message[1:]}')


def loggerize(function: Callable[..., ExitCodes]) -> Callable[..., ExitCodes]:
    """Decorate *function* so it runs with logging enabled."""
    @wraps(function)
    def loggerize_wrapper(*args: str) -> ExitCodes:
        logger.config(main_log_output=Paths.MAIN_LOG, full_log_output=Paths.FULL_LOG)

        logger.debug(Debug.DEBUGGING_INIT)
        logger.info(Messages.PROGRAM_BANNER)
        for required_package in DEPENDENCIES:
            logger.debug(Debug.DEPENDENCY_BANNER.format(required_package.replace('==', ' v')))
        logger.debug(Debug.USER_AGENT_LABEL)

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


def parse_settings(contents: dict[str, str]) -> Settings:
    """Parse program settings from *contents*.

    The *contents* are parsed using `Settings` as the scheme, performing
    type translation as needed.

    Raise `SettingsError` if a key in *contents* does not correspond to an
    attribute in `Settings`.

    Return a `Settings` instance.
    """
    settings: dict[str, int] = {}
    known_keys = {field.name for field in fields(Settings)}
    logger.debug(Debug.PARSING_SETTINGS)

    if extra_keys := [key for key in contents if key not in known_keys]:
        key_list = Messages.LIST_SEPARATOR.join(Messages.QUOTED.format(key) for key in extra_keys)
        raise SettingsError(Messages.SETTINGS_ERROR_UNKNOWN_KEYS.format(key_list))

    for key, value in contents.items():
        # NOTE: only `int` fields are supported for now, so the code is
        # kept simple and validation is minimal. If in the future more
        # data types are needed for the settings, a more complex way of
        # converting them will be implemented. Right now, it would just
        # be overkill.
        try:
            settings[key] = int(value)
        except ValueError as exc:
            raise SettingsError(Messages.SETTINGS_ERROR_INVALID_VALUE.format(key, value)) from exc

    return Settings(**settings)


def parse_profiles(contents: dict[str, dict[str, str]]) -> tuple[Profile, ...]:
    """Parse profile definitions from *contents* dictionary.

    Each key in *contents* is a profile name and the corresponding value
    is the profile definition. Profile definitions are dictionaries with
    catalogue parser parameters as keys, and regular expression patterns
    as values, where keys without value are silently ignored.

    If the parameters in a profile definition matches those belonging to
    a known catalogue parser, a new `Profile` instance is built from the
    data.

    Raise `ProfileError` if a profile does not contain any parameters, a
    required one is missing, or they contain invalid values.

    Return a tuple of the `Profile` instances built from *contents*.
    """
    url_pattern_key = 'url'
    profiles: list[Profile] = []
    parsers = [parser() for parser in BaseParser.__subclasses__()]
    logger.debug(Debug.PARSING_PROFILES)
    for profile_name, profile_contents in contents.items():
        if not profile_contents:
            raise ProfileError(Messages.PROFILE_ERROR_EMPTY_PROFILE.format(profile_name))
        parser_config: ParserConfig = {}
        for key, pattern in profile_contents.items():
            if not pattern:
                continue
            try:
                parser_config[key] = re.compile(pattern, re.IGNORECASE)
            except re.PatternError as exc:
                message = Messages.PROFILE_ERROR_INVALID_REGEX.format(
                    profile_name, key, pattern, exc.pos or 0, type(exc).__name__, exc.msg,
                )
                raise ProfileError(message) from exc
        if (url_pattern := parser_config.pop(url_pattern_key, None)) is None:
            raise ProfileError(Messages.PROFILE_ERROR_PROFILE_WITHOUT_URL.format(profile_name))
        for parser in parsers:
            if parser_config.keys() == parser.PARAMETERS:
                break
        else:
            raise ProfileError(Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(profile_name))
        profiles.append(Profile(profile_name, url_pattern, parser, parser_config))

    return tuple(profiles)


def load_inifile(inifile_path: Path) -> tuple[Settings, tuple[Profile, ...]]:
    """Load the program INI file from *inifile_path*.

    Read and process the INI file at *inifile_path*, containing program
    settings and profile definitions.

    Raise `IniFileError` if *inifile_path* cannot be found, read, or if
    it has syntax or encoding errors.

    Raise `SettingsError` if program settings cannot be obtained.

    Raise `ProfileError` if profiles cannot be obtained.

    Return a tuple of a `Settings` instance and a tuple of the `Profile`
    instances obtained from the INI file.
    """
    inifile_parser = ConfigParser(interpolation=None, allow_unnamed_section=True)

    try:
        with inifile_path.open(encoding='utf-8-sig') as inifile:
            inifile_parser.read_file(inifile)
    except FileNotFoundError as exc:
        raise IniFileError(Messages.INIFILE_ERROR_FILE_NOT_FOUND.format(inifile_path)) from exc
    except PermissionError as exc:
        raise IniFileError(Messages.INIFILE_ERROR_FILE_NO_PERMISSION.format(inifile_path)) from exc
    except OSError as exc:
        raise IniFileError(Messages.INIFILE_ERROR_FILE_READ_FAILED.format(inifile_path)) from exc
    except UnicodeDecodeError as exc:
        raise IniFileError(Messages.INIFILE_ERROR_FILE_NOT_UTF_8.format(inifile_path)) from exc
    except ConfigParserError as exc:
        errorname = type(exc).__name__.removesuffix(ConfigParserError.__name__)
        raise IniFileError(Messages.INIFILE_ERROR_WRONG_SYNTAX.format(errorname, inifile_path)) from exc

    if inifile_parser.has_section(UNNAMED_SECTION):
        settings = parse_settings(dict(inifile_parser[UNNAMED_SECTION]))
        for key, value in asdict(settings).items():
            logger.info(Messages.SETTING_LABEL.format(key, value))
        inifile_parser.remove_section(UNNAMED_SECTION)
    else:
        # NOTE: this is **NOT** considered an error because for now, all
        # the settings have defaults, so the program will run perfectly
        # even if the entire settings section is missing.
        logger.debug(Debug.MISSING_SETTINGS)
        settings = Settings()
    profiles = parse_profiles({section: dict(inifile_parser[section]) for section in inifile_parser.sections()})
    if not profiles:
        raise ProfileError(Messages.INIFILE_ERROR_NO_VALID_PROFILES.format(inifile_path))

    for profile in profiles:
        logger.info(Messages.PROFILE_LABEL.format(profile.name, profile.parser))
        profile.debug_log()

    return settings, profiles


def is_url(value: str) -> bool:
    """Check whether *value* is a URL, for this program's needs.

    A URL is a string starting with a scheme of at least two characters
    followed by `://`. The two-character minimum keeps a Windows drive
    letter from being taken for a scheme.

    Only the shape is checked, not the actual validity.
    """
    url_scheme_re = r'[a-z][a-z0-9+.-]+://'
    return re.prefixmatch(url_scheme_re, value, re.IGNORECASE) is not None


def parse_arguments(*args: str) -> Iterator[Gateway]:
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
        elif lowercase_arg.endswith('.txt'):
            logger.debug(Debug.ARG_IS_TEXTFILE)
            gateway = TextFileGateway(clean_arg)
        elif lowercase_arg.endswith('.xlsx'):
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
        self._label = source.strip()
        self.urls: list[Url]= []
        self.source_path = self.generate_source_path()
        self.sink_path = self.generate_sink_path()

    @property
    def label(self) -> str:
        """."""
        return self._label

    def generate_source_path(self) -> Path:
        """Generate the source file path from `self.label`."""
        return Path(self.label)

    def generate_sink_path(self) -> Path:
        """Generate the sink file path from `self.source_path`."""
        return self.source_path.with_stem(self.source_path.stem + self.SINK_STEM)

    @final
    def get_urls(self) -> list[Url]:
        """Obtain the URLs found in this gateway's source.

        Raise `GatewayError` to wrap some `OSError` exceptions to give
        some context and better precision.

        Return *unique* URLs, in order of first appearance.
        """
        try:
            unique_urls = list(dict.fromkeys(self._get_urls()))
        except FileNotFoundError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND) from exc
        except PermissionError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_NO_PERMISSION) from exc
        except OSError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_INPUT_FILE_READ_FAILED) from exc
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
        except OSError as exc:
            raise GatewayError(Messages.GATEWAY_ERROR_OUTPUT_FILE_WRITE_FAILED) from exc

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

    def generate_source_path(self) -> Path:
        """Convert the URL to a valid path with *.txt* suffix.

        The URL is actually stored at `self._label`, as it is the source
        for this gateway.

        The method is quite crude but it works: replace every ASCII non
        word characters (potentially unsafe when they are present in a
        path) by a visually unobtrusive character which is safe to use
        while keeping the path readable.
        """
        return Path(re.sub(r'\W', '_', self.label, flags=re.ASCII)).with_suffix('.txt')

    def _get_urls(self) -> list[Url]:
        """Return this gateway's single URL."""
        return [self.label]

    def _save_metadata(self, results: SkimResults) -> None:
        """Save *results* metadata to a text file sink."""
        metadata = results.get(self.label)
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
        self.url_rows: dict[Url, list[int]] = {}

    def _get_urls(self) -> list[Url]:
        """Return all URLs in the input file, stripped.

        NOTE: only the first sheet is processed, because (allegedly…) it
        is the one where the URLs are.
        """
        try:
            source_workbook = self._load_workbook(self.source_path)
        # NOTE: the `except` blocks below are a hack, true, but they are
        # the lesser evil. Unfortunately, openpyxl documentation is not
        # very thorough regarding the exceptions it raises for invalid
        # files and the documented ones are a mess, from `BadZipFile` to
        # XML parser errors, including standard library ones.
        #
        # The solution below is quite pragmatic: catch all of them, but
        # make sure `OSError` ones are bubbled up to `self.get_urls()`.
        except OSError:
            raise
        except Exception as exc:
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
            if (url := self._get_url_from_row(row)) is None:
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

        sink_workbook = self._load_workbook(self.sink_path)
        sink_sheet = sink_workbook.worksheets[0]

        logger.debug(Debug.INSERTING_HEADING_ROW)
        sink_sheet.insert_rows(1, 1)

        known_metadata: dict[MetadataKey, int] = {}
        for url, rows in self.url_rows.items():
            if url in results:
                for row in rows:
                    self._store_metadata(sink_sheet, row, results[url], known_metadata)
        sink_workbook.save(self.sink_path)
        sink_workbook.close()

    @staticmethod
    def _load_workbook(workbook_path: Path) -> Workbook:
        """Load the workbook at *workbook_path*, logging warnings.

        `openpyxl` reports unsupported features through the `warnings`
        module, which would print to `sys.stderr`, outside the program
        normal log, and only the first time per run.
        """
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter('always')
            try:
                return load_workbook(workbook_path)
            finally:
                for caught_warning in caught_warnings:
                    logger.debug(
                        Debug.WORKBOOK_WARNING.format(
                            caught_warning.category.__name__,
                            workbook_path,
                            caught_warning.message,
                        ), stacklevel=2,
                    )

    @staticmethod
    def _get_url_from_row(row: tuple[Cell | MergedCell, ...]) -> Url | None:
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

    def _store_metadata(self,
        sheet: Worksheet,
        row: int,
        metadata: Metadata,
        known_metadata: dict[MetadataKey, int],
    ) -> None:
        """Store *metadata* in *sheet* at given *row*.

        For new metadata keys a new column is added to *sink_sheet*, and
        the value is added there. For already existing metadata keys the
        value is added to the corresponding existing column.

        The *known_metadata* argument serves to track existing metadata
        keys, to know in which column are they stored.

        The new columns are marked with a prefix so they are easier to
        recognize, filter and process later.
        """
        cell_font = self.ADDED_CELLS_FONT
        cell_color = self.ADDED_CELLS_COLOR
        cell_fill = self.ADDED_CELLS_FILL

        for key, value in metadata.items():
            if key not in known_metadata:
                column_header = self.ADDED_METADATA_COLUMN_HEADER.format(key)
                logger.debug(Debug.NEW_METADATA_FOUND.format(key))
                column = sheet.max_column + 1
                known_metadata[key] = column
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
            sheet.cell(row + 1, known_metadata[key], value=value)


def get_parser(url: Url, profiles: tuple[Profile, ...]) -> BaseParser:
    """Obtain the appropriate parser for the *url*.

    The appropriate parser is retrieved by finding the needed profile
    within *profiles* whose 'url_pattern' matches the given *url*. Then,
    the parser is returned after being properly configured to handle the
    *url* contents.

    Raise `ProfileError` if no matching profile is found for *url*.

    Return the appropriate parser instance.
    """
    for profile in profiles:
        if profile.url_pattern.search(url):
            logger.debug(Debug.PROFILE_ID.format(profile.name, type(profile.parser).__name__))
            profile.parser.configure(profile.parser_config)
            return profile.parser
    raise ProfileError(Messages.PROFILE_ERROR_NO_MATCHING_PROFILE)


# pylint: disable-next=too-many-branches
def retrieval_error_message(exc: Exception) -> str | None:  # ruff: ignore[C901,PLR0912]
    """Retrieve the end user message for *exc*.

    *exc* is one of the many possible exceptions that can be raised when
    retrieving a URL. In order to give the end user a set of meaningful
    and coherent messages, instead of using the predefined message for
    the exception, the corresponding `Messages.SKIMMING_ERROR_` message
    is returned.

    Return the appropriate message for *exc* or `None` if one does not
    exist for *exc*, so the caller can let it propagate unchanged.
    """
    match exc:
        # Depending on the particular error which happened, the reason
        # attribute of the 'URLError' exception can be a simple error
        # message, an instance of some 'OSError' derived Exception, etc.
        # So, in order to have useful messages, some discrimination has
        # to be done here.
        case HTTPError():
            reason = Messages.URL_ACCESS_REASON_HTTP_ERROR.format(exc.code)
            message = Messages.SKIMMING_ERROR_URL_ACCESS.format(reason)
        case URLError(reason=OSError() as os_error):
            reason = Messages.URL_ACCESS_REASON_OSLIKE_ERROR.format(type(os_error).__name__)
            message = Messages.SKIMMING_ERROR_URL_ACCESS.format(reason)
        case URLError():
            reason = Messages.URL_ACCESS_REASON_UNEXPECTED_ERROR
            message = Messages.SKIMMING_ERROR_URL_ACCESS.format(reason)
        # Apparently, 'HTTPException', 'ConnectionError' and the subclasses
        # are masked or wrapped by 'urllib', and documentation is not very
        # informative. So, just in case something weird happen, it is better
        # to handle these exception types here as well.
        case ConnectionError(errno=errno_value) if isinstance(errno_value, int) and errno_value in errno.errorcode:
            message = Messages.SKIMMING_ERROR_CONNECTION_FAILED.format(errno.errorcode[errno_value])
        case ConnectionError():
            message = Messages.SKIMMING_ERROR_CONNECTION_FAILED_UNKNOWN_REASON
        case HTTPException():
            message = Messages.SKIMMING_ERROR_ERROR_HTTP_RETRIEVAL.format(type(exc).__name__)
        case TimeoutError():
            message = Messages.SKIMMING_ERROR_TIMEOUT
        case OSError():  # Must go after all its subclasses above.
            message = Messages.SKIMMING_ERROR_CONNECTION_FAILED.format(type(exc).__name__)
        case TooManyRedirectionsError(limit=limit):
            message = Messages.SKIMMING_ERROR_TOO_MANY_REDIRECTIONS.format(limit)
        case CharsetError(charset=charset) if not charset:
            message = Messages.SKIMMING_ERROR_EMPTY_CHARSET
        case CharsetError(charset=charset):
            message = Messages.SKIMMING_ERROR_UNKNOWN_CHARSET.format(charset)
        case UnicodeDecodeError(encoding=charset):
            message = Messages.SKIMMING_ERROR_UNDECODABLE_CONTENTS.format(charset)
        case ValueError():  # For instance from 'Request' with a URL without scheme.
            message = Messages.SKIMMING_ERROR_INVALID_URL
        case _:
            message = None
    return message


def saca_las_mantecas(url: Url, parser: BaseParser) -> Metadata:
    """Saca las mantecas.

    Saca las mantecas from the given *url*, that is, retrieve contents,
    parse them using *parser*, and obtain library catalogue metadata, if
    any.

    Raise `SkimmingError` for any problem it finds.

    Return obtained metadata as a dictionary.
    """
    try:
        contents = retrieve_url(url)
    except Exception as exc:
        if (message := retrieval_error_message(exc)):
            raise SkimmingError(message) from exc
        raise

    if not contents:
        raise SkimmingError(Messages.SKIMMING_ERROR_NO_CONTENTS)

    parser.feed(contents)
    parser.close()
    if retrieved_metadata := parser.get_metadata():
        return retrieved_metadata
    raise SkimmingError(Messages.SKIMMING_ERROR_NO_METADATA_FOUND)


def retrieve_url(url: Url) -> str:
    """Retrieve contents from *url*.

    Any URL access is aborted after the number of seconds specified in
    `program_settings.url_retrieval_timeout_seconds`.

    First resolve any `meta http-equiv="Refresh"` redirection for *url*.
    up to a maximum of `program_settings.max_redirections` hops.

    Second, get the *url* contents as a byte string.

    Third, detect the contents encoding (in HTML jargon, the charset).

    Return the decoded contents as a string.
    """
    current_url: Url | None = url
    timeout = program_settings.url_retrieval_timeout_seconds
    max_redirections = program_settings.max_url_redirections

    if url.startswith('file://'):
        current_url = resolve_file_url(url)

    contents = b''
    charset = ''
    headers = {'User-Agent': USER_AGENT}
    redirections = 0
    while current_url:
        logger.debug(Debug.PROCESSING_URL.format(current_url))
        with urlopen(Request(current_url, headers=headers), timeout=timeout) as response:  # ruff: ignore[S310]
            # First, check if any redirection is needed and try to get
            # the charset the easy way.
            contents = response.read()
            charset = response.headers.get_content_charset()
        current_url = get_redirected_url(contents, current_url)
        if current_url:
            redirections += 1
            if redirections > max_redirections:
                raise TooManyRedirectionsError(max_redirections)

    # In this point, we have the contents as a byte string.
    # If the charset is 'None', it has to be determined the hard way.
    if not charset:
        logger.debug(Debug.CHARSET_NOT_IN_HEADERS)
        charset = detect_html_charset(contents)
    else:
        logger.debug(Debug.CHARSET_IN_HEADERS)

    charset = charset.strip()
    logger.debug(Debug.CONTENTS_ENCODING.format(charset))

    try:
        return contents.decode(charset)
    except LookupError as exc:
        raise CharsetError(charset) from exc


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

    if match := re.search(meta_refresh_re, contents, re.IGNORECASE):
        target_url = match.group(1).decode('ascii', errors='replace')
        # If not specified in the obtained redirected URL, both the
        # scheme and netloc will be reused from the base URL. Any
        # other field will be obtained from the redirected URL and
        # used, no matter if it is empty.
        redirected_url = urljoin(base_url, target_url)
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
    meta_http_equiv_charset_re = rb'<meta http-equiv=(["\'])content-type\1.*?charset=(["\'])([^"\']+)\2'
    meta_charset_re = rb'<meta charset=(["\'])([^"\']+)\1'

    charset = fallback_charset
    if match := re.search(meta_http_equiv_charset_re, contents, re.IGNORECASE):
        # Next best thing, from the meta http-equiv="content-type".
        logger.debug(Debug.CHARSET_FROM_HTTP_EQUIV)
        charset = match.group(3).decode('ascii')
    elif match := re.search(meta_charset_re, contents, re.IGNORECASE):
        # Last resort, from some meta charset, if any…
        logger.debug(Debug.CHARSET_FROM_META_CHARSET)
        charset = match.group(2).decode('ascii')
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
    try:
        urls = gateway.get_urls()
    except GatewayError as exc:
        log_exception(exc)
        warning(str(exc))
    else:
        if not urls:
            warning(Messages.WARNING_GATEWAY_EMPTY)
    return urls


def process_urls(urls: list[Url], profiles: tuple[Profile, ...]) -> SkimResults:
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
    for url in urls:
        logger.info(url)
        try:
            results[url] = saca_las_mantecas(url, get_parser(url, profiles))
        except (ProfileError, SkimmingError) as exc:
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
    global program_settings  # pylint: disable=global-statement
    exitcode = ExitCodes.SUCCESS

    if not any(argument.strip() for argument in args):
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

    logger.info('')
    logger.info(Messages.LOADING_INIFILE.format(Paths.INIFILE))
    try:
        logger.indent()
        program_settings, profiles = load_inifile(Paths.INIFILE)
        logger.dedent()
    except (IniFileError, SettingsError, ProfileError) as exc:
        log_exception(exc)
        error(str(exc))
        return ExitCodes.ERROR

    for gateway in parse_arguments(*args):
        logger.info('')
        logger.info(Messages.PROCESSING_GATEWAY.format(gateway.label))

        logger.indent()
        logger.info(Messages.STEP_LOADING_URLS)

        logger.indent()
        urls = collect_urls(gateway)
        logger.dedent()

        if urls:
            logger.info(Messages.STEP_PROCESSING_URLS)
            logger.indent()
            results = process_urls(urls, profiles)
            logger.dedent()
            if len(results) != len(urls):
                exitcode = ExitCodes.WARNING
            if results:
                logger.info(Messages.STEP_SAVING_RESULTS)
                logger.indent()
                if not save_results(gateway, results):
                    exitcode = ExitCodes.WARNING
                logger.dedent()
        else:
            exitcode = ExitCodes.WARNING
        logger.dedent()
    return exitcode
