#! /usr/bin/env python3
"""Test suite for metadata parsers."""

from html import escape
from random import choice as randchoice, choices as randchoices, randint
from unicodedata import category

import pytest

from sacamantecas import BaseParser


SPACE = 0x20
LF = 0x0A
CR = 0x0D
NBSP = 0xA0
ALLOWED_CONTROLS = [chr(cp) for cp in (SPACE, LF, CR, NBSP)]

START_CP = 0x0000
END_CP = 0x024F
LETTERS = 'L'
NUMBERS = 'N'
PUNCTUATIONS = 'P'
SYMBOLS = 'S'
ALLOWED_CATEGORIES = (LETTERS, NUMBERS, PUNCTUATIONS, SYMBOLS)
ALLOWED_CHARS = [chr(cp) for cp in range(START_CP, END_CP+1) if category(chr(cp)).startswith(ALLOWED_CATEGORIES)]

MIN_LENGTH = 1
MAX_LENGTH = 42
def generate_random_string():
    """
    Generate a random string with MIN_LENGTH <= length <= MAX_LENGTH.
    Only characters from the ALLOWED_* sets are used.
    """
    return escape(''.join(randchoices(ALLOWED_CONTROLS + ALLOWED_CHARS, k=randint(MIN_LENGTH, MAX_LENGTH))))


MEBI = 1024 * 1024
def test_random_feed():  # pylint: disable=unused-variable
    """Test parser behavior against random data."""
    parser = BaseParser()

    total_characters = 0
    while total_characters < 1 * MEBI:
        random_string = generate_random_string()
        total_characters += len(random_string)
        for _ in range(2):
            parser.within_k = randchoice([True, False])
            parser.within_v = randchoice([True, False])
            parser.feed(random_string)
            parser.within_k = False
            parser.within_v = False
        parser.store_metadata()

    parser.close()


def test_parser_reset():  # pylint: disable=unused-variable
    """Test parser state after a reset."""
    parser = BaseParser()

    k, v = 'key', 'value'

    parser.within_k = True
    parser.feed(k)
    parser.within_k = False
    parser.within_v = True
    parser.feed(v)
    parser.within_v = False
    parser.store_metadata()

    result = parser.get_metadata()
    assert result == {k: v}

    parser.reset()
    result = parser.get_metadata()
    assert not result

    parser.close()


WHITESPACED_AND_NEWLINED = '  {}\n   whitespaced     \n       and\t\n    newlined   '
@pytest.mark.parametrize('metadata', [
    ('key', 'value'),
    ('key', ' '),
    ('key', ''),
    ('key', None),

    (' ', 'value'),
    (' ', ''),
    (' ', ' '),
    (' ', None),

    ('', 'value'),
    ('', ' '),
    ('', ''),
    ('', None),

    (None, 'value'),
    (None, ' '),
    (None, ''),
    (None, None),

    ('key:', 'value'),

    (WHITESPACED_AND_NEWLINED.format('key'), 'value'),
    ('key', WHITESPACED_AND_NEWLINED.format('value')),
    (WHITESPACED_AND_NEWLINED.format('key'), WHITESPACED_AND_NEWLINED.format('value')),
])
def test_parser_baseline(metadata):  # pylint: disable=unused-variable
    """Test the basic functionality of parsers."""
    parser = BaseParser()

    metadata_k, metadata_v = metadata
    expected_k, expected_v = metadata

    if metadata_k:
        parser.within_k = True
        parser.feed(metadata_k)
        parser.within_k = False
        expected_k = ' '.join(expected_k.split()).rstrip(':')
    expected_k = expected_k if expected_k else BaseParser.EMPTY_KEY_PLACEHOLDER

    if metadata_v is not None:
        parser.within_v = True
        parser.feed(metadata_v)
        parser.within_v = False
        expected_v = ' '.join(expected_v.split())

    parser.store_metadata()
    parser.close()
    result = parser.get_metadata()

    if not expected_v:
        expected = {}
    else:
        expected = {expected_k: expected_v}
    assert result == expected


MULTIVALUES = [f'value_{n}' for n in range(9)]
@pytest.mark.parametrize('multikeys, separator', [
    (True, BaseParser.MULTIVALUE_SEPARATOR),
    (False, BaseParser.MULTIDATA_SEPARATOR),
])
def test_parser_multivalues(multikeys, separator):  # pylint: disable=unused-variable
    """Test parsing of multiple values per key."""
    key = 'key'

    parser = BaseParser()

    parser.within_k = True
    parser.feed(key)
    parser.within_k = False
    for value in MULTIVALUES:
        parser.within_v = True
        parser.feed(value)
        parser.within_v = False
        if multikeys:
            parser.store_metadata()
    if not multikeys:
        parser.store_metadata()
    parser.close()
    result = parser.get_metadata()
    expected = {key: separator.join(MULTIVALUES)}
    assert result == expected


    parser.close()
    expected = {key: separator.join(MULTIVALUES)}
    assert result == expected
