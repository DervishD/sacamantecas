#! /usr/bin/env python3
"""Test suite for metadata parsers."""
# cSpell:ignore Baratz

import logging
from html import escape
from random import choice as randchoice, choices as randchoices, randint
from re import compile as re_compile
from unicodedata import category

import pytest

from sacamantecas import BaratzParser, BaseParser, Debug, EMPTY_STRING, OldRegimeParser


SPACE = 0x20
LF = 0x0A
CR = 0x0D
NBSP = 0xA0
ALLOWED_CONTROLS = [chr(cp) for cp in (SPACE, LF, CR, NBSP)]

K = 'key'
V = 'value'

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


@pytest.mark.parametrize('k, v, expected', [
    (None, None, Debug.METADATA_IS_EMPTY),
    (K, None, Debug.METADATA_MISSING_VALUE.format(K)),
    (None, V, Debug.METADATA_MISSING_KEY.format(BaseParser.EMPTY_KEY_PLACEHOLDER)),
    (K, V, Debug.METADATA_OK.format(K, V))
])
def test_medatata_storage(caplog, k, v, expected):  # pylint: disable=unused-variable
    """Test store_metadata() branches."""
    caplog.set_level(logging.DEBUG)
    parser = BaseParser()

    parser.current_k = k
    parser.current_v = v

    parser.store_metadata()

    assert caplog.records[0].message == expected
    assert parser.current_k == EMPTY_STRING
    assert parser.current_v == EMPTY_STRING


SINGLE_K = 'single_key'
SINGLE_V = ['single_value']
MULTIPLE_K = 'multiple_key'
MULTIPLE_V = ['multiple_value1', 'multiple_value2', 'multiple_value3']
@pytest.mark.parametrize('metadata, expected', [
    ({SINGLE_K: SINGLE_V}, {SINGLE_K: SINGLE_V[0]}),
    ({MULTIPLE_K: MULTIPLE_V}, {MULTIPLE_K: BaseParser.MULTIVALUE_SEPARATOR.join(MULTIPLE_V)})
])
def test_metadata_retrieval(metadata, expected):   # pylint: disable=unused-variable
    """Test get_metadata()."""
    parser = BaseParser()
    parser.retrieved_metadata = metadata
    assert parser.get_metadata() == expected


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
    # Normal metadata.
    (f'{KB}{{K}}{EE}{VB}{{V}}{EE}', ('{K}', '{V}')),

    # Incomplete metadata, missing value.
    (f'{KB}{{K}}{EE}{VB}{{V}}', ()),
    (f'{KB}{{K}}{EE}{VB}{EE}', ()),
    (f'{VB}{{V}}', ()),
    (f'{VB}{EE}', ()),

    # Incomplete metadata, missing key.
    (f'{KB}{EE}{VB}{{V}}{EE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),
    (f'{VB}{{V}}{EE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),

    # Nesting, value inside key.
    (f'{KB}{{K}}{VB}{{V}}{EE}', ('{K}', '{V}')),
    (f'{KB}{{K}}{VB}{EE}', ()),

    # Nesting, key inside value.
    (f'{VB}_{{V}}_{KB}{{K}}{EE}{VB}{{V}}{EE}', ('{K}', '{V}')),
    (f'{VB}{KB}{{K}}{EE}{VB}{{V}}{EE}', ('{K}', '{V}')),
    (f'{VB}_{{V}}_{KB}{EE}{VB}{{V}}{EE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),
    (f'{VB}{KB}{EE}{VB}{{V}}{EE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),
    (f'{VB}_{{V}}_{KB}{{K}}{EE}{VB}{{V}}', (),),
    (f'{VB}{KB}{{K}}{EE}{VB}{{V}}', (),),

    # Ill-formed, no closing tags.
    (f'{KB}{{K}}{VB}{{V}}', ()),
    (f'{KB}{{K}}{VB}', ()),
    (f'{KB}{VB}{{V}}', ()),
    (f'{KB}{VB}', ()),
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


M_TAG = 'dl'
M_TAG_RE = re_compile(f'{M_TAG}.*')
M_ATTR = 'class'
M_ATTR_RE = re_compile(f'{M_ATTR}.*')
M_VALUE = 'meta_marker'
M_VALUE_RE = re_compile(f'{M_VALUE}.*')
MB = ELEMENT_B.format(TAG=M_TAG, MARKER=M_VALUE)
ME = ELEMENT_E.format(TAG=M_TAG)
KB = ELEMENT_B.format(TAG=BaratzParser.K_TAG, MARKER='')
KE = ELEMENT_E.format(TAG=BaratzParser.K_TAG)
VB = ELEMENT_B.format(TAG=BaratzParser.V_TAG, MARKER='')
VE = ELEMENT_E.format(TAG=BaratzParser.V_TAG)
@pytest.mark.parametrize('contents, expected', [
    # Normal metadata.
    (f'{MB}{KB}{{K}}{KE}{VB}{{V}}{VE}{ME}', ('{K}', '{V}')),
    (f'{MB}{KB}{{K}}{KE}{VB}{{V}}{VE}', ('{K}', '{V}')),

    # No metadata marker.
    (f'{KB}{{K}}{KE}{VB}{{V}}{VE}{ME}', ()),
    (f'{KB}{{K}}{KE}{VB}{{V}}{VE}', ()),

    # Incomplete metadata, missing value.
    (f'{MB}{KB}{{K}}{KE}{VB}{{V}}', ()),
    (f'{MB}{KB}{{K}}{KE}{VB}{VE}', ()),
    (f'{MB}{VB}{{V}}', ()),
    (f'{MB}{VB}{VE}', ()),

    # Incomplete metadata, missing key.
    (f'{MB}{KB}{KE}{VB}{{V}}{VE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),
    (f'{MB}{VB}{{V}}{VE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),

    # Nesting, value inside key.
    (f'{MB}{KB}{{K}}{VB}{{V}}{VE}{KE}', ('{K}', '{V}')),
    (f'{MB}{KB}{{K}}{VB}{VE}{KE}', ()),

    # Nesting, key inside value.
    (f'{MB}{VB}_{{V}}_{KB}{{K}}{KE}{VB}{{V}}{VE}', ('{K}', '{V}')),
    (f'{MB}{VB}{KB}{{K}}{KE}{VB}{{V}}{VE}', ('{K}', '{V}')),
    (f'{MB}{VB}_{{V}}_{KB}{KE}{VB}{{V}}{VE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),
    (f'{MB}{VB}{KB}{KE}{VB}{{V}}{VE}', (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}')),
    (f'{MB}{VB}_{{V}}_{KB}{{K}}{KE}{VB}{{V}}', ()),
    (f'{MB}{VB}{KB}{{K}}{KE}{VB}{{V}}', ()),

    # Ill-formed, no closing tags.
    (f'{MB}{KB}{{K}}{VB}{{V}}', ()),
    (f'{MB}{KB}{{K}}{VB}', ()),
    (f'{MB}{KB}{VB}{{V}}', ()),
    (f'{MB}{KB}{VB}', ()),
])
def test_baratz_parser(contents, expected):  # pylint: disable=unused-variable
    """Test Baratz parser."""
    k_data = generate_random_string()
    v_data = generate_random_string()

    parser = BaratzParser()
    parser.configure({BaratzParser.M_TAG: M_TAG_RE, BaratzParser.M_ATTR: M_ATTR_RE, BaratzParser.M_VALUE: M_VALUE_RE})
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
