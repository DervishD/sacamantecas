#! /usr/bin/env python3
"""Test suite for metadata parsers."""
from html import escape
import logging
from random import choice as randchoice, choices as randchoices, randint
from re import compile as re_compile
from unicodedata import category

import pytest

from sacamantecas import (
    BaratzParser,
    BaseParser,
    logger,
    OldRegimeParser,
)


def generate_random_string() -> str:
    """Generate a random string.

    Generate a random string with random length between certain limits..
    Only characters from the `ALLOWED_*` sets are used.
    """
    space_codepoint = 0x20
    lf_codepoint = 0x0A
    cr_codepoint = 0x0D
    nbsp_codepoint = 0xA0
    letter_category = 'L'
    number_category = 'N'
    puntuations_category = 'P'
    symbols_category = 'S'
    printables_start_codepoint = 0x0000
    printables_end_codepoint = 0x024F
    allowed_control_chars = [chr(cp) for cp in (space_codepoint, lf_codepoint, cr_codepoint, nbsp_codepoint)]
    allowed_printable_chars = [
        chr(cp) for cp in range(printables_start_codepoint, printables_end_codepoint+1)
        if category(chr(cp)).startswith((letter_category, number_category, puntuations_category, symbols_category))
    ]
    allowed_chars = allowed_control_chars + allowed_printable_chars
    min_len = 1
    max_len = 42
    return escape(''.join(randchoices(allowed_chars, k=randint(min_len, max_len))))  # noqa: S311


def test_random_data_parsing() -> None:
    """Test parser behavior against random data."""
    max_random_strings_to_feed = 2 ** 10
    feeds_per_random_string = 10

    parser = BaseParser()

    fed_random_strings = 0
    while fed_random_strings < max_random_strings_to_feed:
        random_string = generate_random_string()

        for _ in range(feeds_per_random_string):
            parser.within_k = randchoice([True, False])  # noqa: S311
            parser.within_v = randchoice([True, False])  # noqa: S311
            parser.feed(random_string)
            parser.within_k = False
            parser.within_v = False

        parser.store_metadata()

        fed_random_strings += 1

    parser.close()


K, V = 'key', 'value'


def test_parser_reset() -> None:
    """Test parser state after a reset."""
    parser = BaseParser()

    k, v = K, V

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


@pytest.mark.parametrize(('k', 'v', 'expected'), [
    pytest.param(
        None,
        None,
        'Metadato vacío.',
        id='test_store_metadata_empty_metadata',
    ),
    pytest.param(
        K,
        None,
        f'Metadato «{K}» incompleto, ignorando.',
        id='test_store_metadata_missing_value',
    ),
    pytest.param(
        None,
        V,
        f'No se encontró una clave, usando «{BaseParser.EMPTY_KEY_PLACEHOLDER}».',
        id='test_store_metadata_missing_key',
    ),
    pytest.param(
        K,
        V,
        f'Metadato correcto «{K}: {V}».',
        id='test_store_metadata_valid_full_metadata',
    ),
])
def test_medatata_storage(caplog: pytest.LogCaptureFixture, k: str, v: str, expected: str) -> None:
    """Test `store_metadata()` branches."""
    logger.propagate = True
    caplog.set_level(logging.DEBUG)

    parser = BaseParser()

    parser.current_k = k
    parser.current_v = v

    parser.store_metadata()

    assert caplog.records[0].message == expected

    if k and v:  # Test that duplicates are not stored.
        parser.current_k = k
        parser.current_v = v
        parser.store_metadata()

    assert parser.current_k == parser.DEFAULT_K
    assert parser.current_v == parser.DEFAULT_V


SINGLE_K, SINGLE_V = 'single_key', ['single_value']
MULTIPLE_K, MULTIPLE_V = 'multiple_key', ['multiple_value1', 'multiple_value2', 'multiple_value3']
@pytest.mark.parametrize(('metadata', 'expected'), [
    pytest.param(
        {SINGLE_K: SINGLE_V},
        {SINGLE_K: SINGLE_V[0]},
        id='test_retrieve_metadata_single_data',
    ),
    pytest.param(
        {MULTIPLE_K: MULTIPLE_V},
        {MULTIPLE_K: BaseParser.MULTIVALUE_SEPARATOR.join(MULTIPLE_V)},
        id='test_retrieve_metadata_multiple_data',
    ),
])
def test_metadata_retrieval(metadata: dict[str, list[str]], expected: dict[str, str]) -> None:
    """Test `get_metadata()`."""
    parser = BaseParser()

    parser.retrieved_metadata = metadata

    assert parser.get_metadata() == expected


EMPTY_DATA = ' '
WS_NL_DATA = '  {}\n   whitespaced     \n       and\t\n    newlined   '
# In the baseline test below, EMPTY means that parser.feed() gets empty
# data, and None that parser.feed() is not even called for that item.
@pytest.mark.parametrize(('contents', 'expected'), [
    # Normal metadata.
    pytest.param(
        (K, V),
        {K: V},
        id='test_parser_baseline_normal_data',
    ),
    pytest.param(
        (f'{K}:', V),
        {K: V},
        id='test_parser_baseline_key_with_separator',
    ),
    pytest.param(
        (WS_NL_DATA.format(K), WS_NL_DATA.format(V)),
        {' '.join(WS_NL_DATA.split()).format(K): ' '.join(WS_NL_DATA.split()).format(V)},
        id='test_parser_baseline_whitespaced_data',
    ),

    # Incomplete metadata, missing value.
    pytest.param((K, EMPTY_DATA), {}, id='test_parser_baseline_empty_value'),
    pytest.param((K, None), {}, id='test_parser_baseline_none_value'),

    # Incomplete metadata, missing key.
    pytest.param((EMPTY_DATA, V), {BaseParser.EMPTY_KEY_PLACEHOLDER: V}, id='test_parser_baseline_empty_key'),
    pytest.param((None, V), {BaseParser.EMPTY_KEY_PLACEHOLDER: V}, id='test_parser_baseline_none_key'),

    # Empty metadata.
    pytest.param((EMPTY_DATA, EMPTY_DATA), {}, id='test_parser_baseline_missing_data'),
])
def test_parser_baseline(contents: tuple[str | None, str | None], expected: dict[str, str]) -> None:
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


@pytest.mark.parametrize(('multikeys', 'separator'), [
    pytest.param(
        False,
        BaseParser.MULTIDATA_SEPARATOR,
        id='test_metadata_multiple_values_single_key',
    ),
    pytest.param(
        True,
        BaseParser.MULTIVALUE_SEPARATOR,
        id='test_metadata_multiple_values_multiple_keys',
    ),
])
def test_parser_multivalues(multikeys: bool, separator: str) -> None: # noqa: FBT001
    """Test parsing of multiple values per key."""
    key = K
    multivalues = [f'value_{n}' for n in range(9)]

    parser = BaseParser()

    parser.within_k = True
    parser.feed(key)
    parser.within_k = False

    for value in multivalues:
        parser.within_v = True
        parser.feed(value)
        parser.within_v = False
        if multikeys:
            parser.store_metadata()

    if not multikeys:
        parser.store_metadata()

    parser.close()

    result = parser.get_metadata()
    expected = {key: separator.join(multivalues)}

    assert result == expected


ELEMENT_B, ELEMENT_E = '<{TAG} class="{MARKER}_suffix">', '</{TAG}>'


K_CLASS, V_CLASS = 'k_marker', 'v_marker'
K_CLASS_RE, V_CLASS_RE = re_compile(f'{K_CLASS}.*'), re_compile(f'{V_CLASS}.*')
TAG = 'div'
OP_KB, OP_VB = ELEMENT_B.format(TAG=TAG, MARKER=K_CLASS), ELEMENT_B.format(TAG=TAG, MARKER=V_CLASS)
OP_EE = ELEMENT_E.format(TAG=TAG)
@pytest.mark.parametrize(('contents', 'expected'), [
    # Normal metadata.
    pytest.param(f'{OP_KB}{{K}}{OP_EE}{OP_VB}{{V}}{OP_EE}', ('{K}', '{V}'), id='test_old_regime_parser_ok'),

    # Incomplete metadata, missing value.
    pytest.param(f'{OP_KB}{{K}}{OP_EE}{OP_VB}{{V}}', (), id='test_old_regime_parser_missing_value_1'),
    pytest.param(f'{OP_KB}{{K}}{OP_EE}{OP_VB}{OP_EE}', (), id='test_old_regime_parser_missing_value_2'),
    pytest.param(f'{OP_VB}{{V}}', (), id='test_old_regime_parser_missing_value_3'),
    pytest.param(f'{OP_VB}{OP_EE}', (), id='test_old_regime_parser_missing_value_4'),

    # Incomplete metadata, missing key.
    pytest.param(
        f'{OP_KB}{OP_EE}{OP_VB}{{V}}{OP_EE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_old_regime_parser_missing_key_1',
    ),
    pytest.param(
        f'{OP_VB}{{V}}{OP_EE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_old_regime_parser_missing_key_2',
    ),

    # Nesting, value inside key.
    pytest.param(f'{OP_KB}{{K}}{OP_VB}{{V}}{OP_EE}', ('{K}', '{V}'), id='test_old_regime_parser_nesting_v_in_k_1'),
    pytest.param(f'{OP_KB}{{K}}{OP_VB}{OP_EE}', (), id='test_old_regime_parser_nesting_v_in_k_2'),

    # Nesting, key inside value.
    pytest.param(
        f'{OP_VB}_{{V}}_{OP_KB}{{K}}{OP_EE}{OP_VB}{{V}}{OP_EE}',
        ('{K}', '{V}'),
        id='test_old_regime_parser_nesting_k_in_v_1',
    ),
    pytest.param(
        f'{OP_VB}{OP_KB}{{K}}{OP_EE}{OP_VB}{{V}}{OP_EE}',
        ('{K}', '{V}'),
        id='test_old_regime_parser_nesting_k_in_v_2',
    ),
    pytest.param(
        f'{OP_VB}_{{V}}_{OP_KB}{OP_EE}{OP_VB}{{V}}{OP_EE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_old_regime_parser_nesting_k_in_v_3',
    ),
    pytest.param(
        f'{OP_VB}{OP_KB}{OP_EE}{OP_VB}{{V}}{OP_EE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_old_regime_parser_nesting_k_in_v_4',
    ),
    pytest.param(
        f'{OP_VB}_{{V}}_{OP_KB}{{K}}{OP_EE}{OP_VB}{{V}}',
        (),
        id='test_old_regime_parser_nesting_k_in_v_5',
    ),
    pytest.param(
        f'{OP_VB}{OP_KB}{{K}}{OP_EE}{OP_VB}{{V}}',
        (),
        id='test_old_regime_parser_nesting_k_in_v_6',
    ),

    # Ill-formed, no closing tags.
    pytest.param(f'{OP_KB}{{K}}{OP_VB}{{V}}', (), id='test_old_regime_parser_no_closing_tags_1'),
    pytest.param(f'{OP_KB}{{K}}{OP_VB}', (), id='test_old_regime_parser_no_closing_tags_2'),
    pytest.param(f'{OP_KB}{OP_VB}{{V}}', (), id='test_old_regime_parser_no_closing_tags_3'),
    pytest.param(f'{OP_KB}{OP_VB}', (), id='test_old_regime_parser_no_closing_tags_4'),

    # Ill-formed, no class attribute in marker tag.
    pytest.param(f'<{TAG}></{TAG}>', (), id='test_old_regime_parser_no_class_in_marker_tag'),

    # Ill-formed, empty class attribute in marker tag.
    pytest.param(f'<{TAG} class></{TAG}>', (), id='test_old_regime_parser_empty_class_in_marker_tag'),

    # Ill-formed, wrong attribute in marker tag.
    pytest.param(f'<{TAG} wrong="wrong"></{TAG}>', (), id='test_old_regime_parser_wrong_attribute_in_marker_tag'),
])
def test_old_regime_parser(contents: str, expected: tuple[str, str]) -> None:
    """Test *Old Regime* parser."""
    k_data = generate_random_string()
    v_data = generate_random_string()

    parser = OldRegimeParser()

    parser.configure({OldRegimeParser.K_CLASS: K_CLASS_RE, OldRegimeParser.V_CLASS: V_CLASS_RE})
    parser.feed(contents.format(K=escape(k_data), V=escape(v_data)))

    parser.close()

    result = parser.get_metadata()

    if not expected:
        expected_dict = {}
    else:
        expected_k, expected_v = expected
        expected_k = expected_k.format(K=' '.join(k_data.split()).rstrip(':'))
        expected_v = expected_v.format(V=' '.join(v_data.split()))
        expected_dict = {expected_k: expected_v}

    assert result == expected_dict


M_TAG, M_ATTR, M_VALUE = 'dl', 'class', 'meta_marker'
M_TAG_RE, M_ATTR_RE, M_VALUE_RE = re_compile(f'{M_TAG}.*'), re_compile(f'{M_ATTR}.*'), re_compile(f'{M_VALUE}.*')
BP_MB, BP_ME = ELEMENT_B.format(TAG=M_TAG, MARKER=M_VALUE), ELEMENT_E.format(TAG=M_TAG)
BP_KB, BP_KE = ELEMENT_B.format(TAG=BaratzParser.K_TAG, MARKER=''), ELEMENT_E.format(TAG=BaratzParser.K_TAG)
BP_VB, BP_VE = ELEMENT_B.format(TAG=BaratzParser.V_TAG, MARKER=''), ELEMENT_E.format(TAG=BaratzParser.V_TAG)
@pytest.mark.parametrize(('contents', 'expected'), [
    # Normal metadata.
    pytest.param(f'{BP_MB}{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}{BP_VE}{BP_ME}', ('{K}', '{V}'), id='test_baratz_parser_ok_1'),
    pytest.param(f'{BP_MB}{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}{BP_VE}', ('{K}', '{V}'), id='test_baratz_parser_ok_2'),

    # No metadata marker.
    pytest.param(f'{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}{BP_VE}{BP_ME}', (), id='test_baratz_parser_no_marker_1'),
    pytest.param(f'{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}{BP_VE}', (), id='test_baratz_parser_no_marker_2'),

    # Missing metadata.
    pytest.param(f'{BP_MB}<wrong></wrong>{BP_ME}', (), id='test_baratz_parser_missing_metadata'),

    # Incomplete metadata, missing value.
    pytest.param(f'{BP_MB}{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}', (), id='test_baratz_parser_missing_value_1'),
    pytest.param(f'{BP_MB}{BP_KB}{{K}}{BP_KE}{BP_VB}{BP_VE}', (), id='test_baratz_parser_missing_value_2'),
    pytest.param(f'{BP_MB}{BP_VB}{{V}}', (), id='test_baratz_parser_missing_value_3'),
    pytest.param(f'{BP_MB}{BP_VB}{BP_VE}', (), id='test_baratz_parser_missing_value_4'),

    # Incomplete metadata, missing key.
    pytest.param(
        f'{BP_MB}{BP_KB}{BP_KE}{BP_VB}{{V}}{BP_VE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_baratz_parser_missing_key_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{{V}}{BP_VE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_baratz_parser_missing_key_2',
    ),

    # Nesting, value inside key.
    pytest.param(
        f'{BP_MB}{BP_KB}{{K}}{BP_VB}{{V}}{BP_VE}{BP_KE}',
        ('{K}', '{V}'),
        id='test_baratz_parser_nesting_v_in_k_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{{K}}{BP_VB}{BP_VE}{BP_KE}',
        (),
        id='test_baratz_parser_nesting_v_in_k_2',
    ),

    # Nesting, key inside value.
    pytest.param(
        f'{BP_MB}{BP_VB}_{{V}}_{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}{BP_VE}',
        ('{K}', '{V}'),
        id='test_baratz_parser_nesting_k_in_v_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}{BP_VE}',
        ('{K}', '{V}'),
        id='test_baratz_parser_nesting_k_in_v_2',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}_{{V}}_{BP_KB}{BP_KE}{BP_VB}{{V}}{BP_VE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_baratz_parser_nesting_k_in_v_3',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{BP_KB}{BP_KE}{BP_VB}{{V}}{BP_VE}',
        (BaseParser.EMPTY_KEY_PLACEHOLDER, '{V}'),
        id='test_baratz_parser_nesting_k_in_v_4',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}_{{V}}_{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}',
        (),
        id='test_baratz_parser_nesting_k_in_v_5',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{BP_KB}{{K}}{BP_KE}{BP_VB}{{V}}',
        (),
        id='test_baratz_parser_nesting_k_in_v_6',
    ),

    # Ill-formed, no closing tags.
    pytest.param(f'{BP_MB}{BP_KB}{{K}}{BP_VB}{{V}}', (), id='test_baratz_parser_no_closing_tags_1'),
    pytest.param(f'{BP_MB}{BP_KB}{{K}}{BP_VB}', (), id='test_baratz_parser_no_closing_tags_2'),
    pytest.param(f'{BP_MB}{BP_KB}{BP_VB}{{V}}', (), id='test_baratz_parser_no_closing_tags_3'),
    pytest.param(f'{BP_MB}{BP_KB}{BP_VB}', (), id='test_baratz_parser_no_closing_tags_4'),

    # Ill-formed, no class attribute in marker tag.
    pytest.param(f'<{M_TAG}></{M_TAG}>', (), id='test_baratz_parser_no_class_in_marker_tag'),

    # Ill-formed, empty class attribute in marker tag.
    pytest.param(f'<{M_TAG} class></{M_TAG}>', (), id='test_baratz_parser_empty_class_in_marker_tag'),

    # Ill-formed, wrong attribute in marker tag.
    pytest.param(f'<{M_TAG} wrong="wrong"></{M_TAG}>', (), id='test_baratz_parser_wrong_attribute_in_marker_tag'),
])
def test_baratz_parser(contents: str, expected: tuple[str, str]) -> None:
    """Test *Baratz* parser."""
    k_data = generate_random_string()
    v_data = generate_random_string()

    parser = BaratzParser()

    parser.configure({BaratzParser.M_TAG: M_TAG_RE, BaratzParser.M_ATTR: M_ATTR_RE, BaratzParser.M_VALUE: M_VALUE_RE})
    parser.feed(contents.format(K=escape(k_data), V=escape(v_data)))

    parser.close()

    result = parser.get_metadata()

    if not expected:
        expected_dict = {}
    else:
        expected_k, expected_v = expected
        expected_k = expected_k.format(K=' '.join(k_data.split()).rstrip(':'))
        expected_v = expected_v.format(V=' '.join(v_data.split()))
        expected_dict = {expected_k: expected_v}

    assert result == expected_dict
