#! /usr/bin/env python3
"""Test suite for non-refactored code strings."""
from tokenize import generate_tokens, STRING

from sacamantecas import APP_NAME, ASCII, BaseParser, Config, Debug, EMPTY_STRING, Messages, ROOT_PATH, UTF8


ALLOWED_STRINGS = (
    # Early platform check.
    'win32', '\nThis application is compatible only with the Win32 platform.',
    # Python well-known strings.
    'frozen', '__main__',
    # Application constants.
    EMPTY_STRING, UTF8, ASCII,
    # Punctuation characters.
    '/', ':', '.', '"', ', ',
    # Strings used for logging.dictConfig configuration dictionary.
    'version', 'disable_existing_loggers', 'propagate',
    'indentlevel','+', '-',
    '()', 'style', 'format', 'datefmt',
    'formatters', 'filters', 'handlers', 'loggers',
    'level', 'formatter', 'class', 'filename', 'mode', 'encoding', 'stream',
    'debugfile_formatter', 'logfile_formatter', 'console_formatter',
    'debugfile_filter', 'logfile_filter', 'stdout_filter', 'stderr_filter',
    'debugfile_handler', 'logfile_handler', 'stdout_handler', 'stderr_handler',
    # Miscellaneous strings that should not be refactored.
    'w',
    ' versión ',
    'kernel32',
    'BadRegex',
    'User-Agent',
    'Error',
    'file://',
    'scheme', 'netloc',
)
PARSER_STRINGS = (BaseParser.__dict__,) + tuple(c.__dict__ for c in BaseParser.__subclasses__())
PARSER_STRINGS = (v for d in PARSER_STRINGS for k, v in d.items() if not k.startswith('__') and isinstance(v, str))
CONFIG_STRINGS = {k: v for k,v in Config.__dict__.items() if not k.startswith('__')}
CONFIG_STRINGS = (v.decode(UTF8) if isinstance(v, bytes) else v for v in CONFIG_STRINGS.values())
CONFIG_STRINGS = (str(v) for item in CONFIG_STRINGS for v in (item if isinstance(item, tuple) else (item,)))
MESSAGE_STRINGS = Messages.__members__.values()
DEBUG_STRINGS = Debug.__members__.values()
REFACTORED_STRINGS = (*ALLOWED_STRINGS, *PARSER_STRINGS, *CONFIG_STRINGS, *MESSAGE_STRINGS, *DEBUG_STRINGS)
def test_strings():  # pylint: disable=unused-variable
    """Test for non-refactored strings."""
    unrefactored_strings = []
    with open(ROOT_PATH / f'{APP_NAME}.py', 'rt', encoding=UTF8) as code:
        for tokeninfo in generate_tokens(code.readline):
            if tokeninfo.type != STRING:
                continue
            if tokeninfo.line.strip().startswith('__'):
                continue
            if tokeninfo.string.startswith(('"""', "'''")):
                continue
            string = tokeninfo.string
            if string.startswith('r'):
                string = tokeninfo.string.lstrip('r')
            else:
                string = tokeninfo.string.replace('\\n', '\n')
            string = string.lstrip('b')
            string = string.strip(string[0])
            if string in REFACTORED_STRINGS:
                continue
            unrefactored_strings.append(tokeninfo.string)
    assert not unrefactored_strings
