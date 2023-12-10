#! /usr/bin/env python3
"""Test suite for metadata parsers."""

from html import escape
from random import choice as randchoice, choices as randchoices, randint
from re import compile as re_compile
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


K = 'key'
V = 'value'
EMPTY = ' '
WS_NL = '  {}\n   whitespaced     \n       and\t\n    newlined   '
# In the baseline test below, EMPTY means that parser.feed() gets empty data,
# and None that parser.feed() is not even called for that particular item.
@pytest.mark.parametrize('contents, expected', [
    # Normal metadata.
    ((K, V), {K: V}),
    ((f'{K}:', V), {K: V}),
    ((WS_NL.format(K), WS_NL.format(V)), {' '.join(WS_NL.split()).format(K): ' '.join(WS_NL.split()).format(V)}),

    # Incomplete metadata, missing value.
    ((K, EMPTY), {}),
    ((K, None), {}),

    # Incomplete metadata, missing key.
    ((EMPTY, V), {BaseParser.EMPTY_KEY_PLACEHOLDER: V}),
    ((None, V), {BaseParser.EMPTY_KEY_PLACEHOLDER: V}),

    # Empty metadata.
    ((EMPTY, EMPTY), {})
])
def test_parser_baseline(contents, expected):  # pylint: disable=unused-variable
    """Test the basic functionality of parsers."""
    parser = BaseParser()

    k, v = contents

    if k is not None:
        parser.within_k = True
        parser.feed(k)
        parser.within_k = False

    if v is not None:
        parser.within_v = True
        parser.feed(v)
        parser.within_v = False

    parser.store_metadata()
    parser.close()
    result = parser.get_metadata()

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


ELEMENT_B = '<{TAG} class="{MARKER}_suffix">'
ELEMENT_E = '</{TAG}>'

K_CLASS = 'k_marker'
V_CLASS = 'v_marker'
K_CLASS_RE = re_compile(f'{K_CLASS}.*')
V_CLASS_RE =  re_compile(f'{V_CLASS}.*')
TAG = 'div'
KB = ELEMENT_B.format(TAG=TAG, MARKER=K_CLASS)
VB = ELEMENT_B.format(TAG=TAG, MARKER=V_CLASS)
EE = ELEMENT_E.format(TAG=TAG)
@pytest.mark.parametrize('contents, expected', [
    # Baseline.
    (f'{KB}{{K}}{EE}{VB}{{V}}{EE}', ('{K}', '{V}')),

    # Empty key.
    (f'{KB}{EE}{VB}{{V}}{EE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),
    (f'{VB}{{V}}{EE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),

    # Empty value.
    (f'{KB}{{K}}{EE}{VB}{{V}}', ()),
    (f'{KB}{{K}}{EE}{VB}{EE}', ()),
    (f'{KB}{{K}}{EE}{VB}', ()),
    (f'{KB}{{K}}{EE}', ()),
    (f'{KB}{EE}{VB}{{V}}', ()),
    (f'{KB}{EE}{VB}{EE}', ()),
    (f'{KB}{EE}{VB}', ()),
    (f'{KB}{EE}', ()),
    (f'{VB}{{V}}', ()),
    (f'{VB}{EE}', ()),
    (f'{VB}', ()),

    # Nesting, value inside key.
    (f'{KB}{{K}}{VB}{{V}}{EE}', ('{K}', '{V}')),
    (f'{KB}{{K}}{VB}{{V}}', ()),
    (f'{KB}{{K}}{VB}{EE}', ()),
    (f'{KB}{{K}}{VB}', ()),
    (f'{KB}{VB}{EE}', ()),
    (f'{KB}{VB}', ()),

    # Nesting, key inside value.
    (f'{VB}{{V}}{KB}{{K}}{EE}{VB}{{V}}{EE}', ('{K}', '{V}')),
    (f'{VB}{{V}}{KB}{{K}}{EE}{VB}{{V}}', ()),
    (f'{VB}{{V}}{KB}{{K}}{EE}{VB}{EE}', ()),
    (f'{VB}{{V}}{KB}{{K}}{EE}{VB}', ()),
    (f'{VB}{{V}}{KB}{{K}}{EE}', ()),
    (f'{VB}{{V}}{KB}{{K}}', ()),
    (f'{VB}{{V}}{KB}{EE}', ()),
    (f'{VB}{{V}}{KB}', ()),
    (f'{VB}{KB}{{K}}{EE}{VB}{{V}}{EE}', ('{K}', '{V}')),
    (f'{VB}{KB}{{K}}{EE}{VB}{{V}}', ()),
    (f'{VB}{KB}{{K}}{EE}{VB}{EE}', ()),
    (f'{VB}{KB}{{K}}{EE}{VB}', ()),
    (f'{VB}{KB}{{K}}{EE}', ()),
    (f'{VB}{KB}{{K}}', ()),
    (f'{VB}{KB}{EE}', ()),
    (f'{VB}{KB}', ()),
])
def test_old_regime_parser(contents, expected):  # pylint: disable=unused-variable
    """Test Old Regime parser."""
    k_data = generate_random_string()
    v_data = generate_random_string()

    parser = OldRegimeParser()
    parser.configure({OldRegimeParser.K_CLASS: K_CLASS_RE, OldRegimeParser.V_CLASS: V_CLASS_RE})
    parser.feed(contents.format(K=escape(k_data), V=escape(v_data)))
    parser.close()
    result = parser.get_metadata()

    if not expected:
        expected = {}
    else:
        expected_k, expected_v = expected
        expected_k = expected_k.format(K=' '.join(k_data.split()).rstrip(':'))
        expected_v = expected_v.format(V=' '.join(v_data.split()))
        expected = {expected_k: expected_v}
    assert result == expected


    parser.close()
    expected = {key: separator.join(MULTIVALUES)}
    assert result == expected
