#! /usr/bin/env python3
"""Test suite for non-refactored code strings."""
from tokenize import generate_tokens, STRING

from sacamantecas import BaseParser, Constants, Debug, Messages


ALLOWED_STRINGS = (
    # Early platform check.
    'win32', '\nThis application is compatible only with the Win32 platform.',
    # Python well-known strings.
    'frozen', '__main__',
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
PARSER_STRINGS = (
    v for d in ((BaseParser.__dict__,) + tuple(c.__dict__ for c in BaseParser.__subclasses__()))
        for k, v in d.items() if not k.startswith('__') and isinstance(v, str)
)
CONSTANT_STRINGS = (
    str(v) for item in ((v.decode(Constants.UTF8) if isinstance(v, bytes) else v)  # type: ignore
        for v in {k: v for k,v in Constants.__dict__.items() if not k.startswith('__')}.values())
            for v in (item if isinstance(item, tuple) else (item,))  # type: ignore
)
MESSAGE_STRINGS = Messages.__members__.values()
DEBUG_STRINGS = Debug.__members__.values()
REFACTORED_STRINGS = (*ALLOWED_STRINGS, *PARSER_STRINGS, *CONSTANT_STRINGS, *MESSAGE_STRINGS, *DEBUG_STRINGS)
def test_strings() -> None:  # pylint: disable=unused-variable
    """Test for non-refactored strings."""
    unrefactored_strings: list[str] = []

    with open(Constants.APP_PATH, 'rt', encoding=Constants.UTF8) as code:
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
