"""Test suite for metadata parsers."""
import logging
from re import compile as re_compile

import pytest

from sacamantecas import BaratzParser, BaseParser, Debug, logger, OldRegimeParser

BASE_STR = 'ÑábCE XÜç42'
SAMPLE_K = f'{BASE_STR}_k'
SAMPLE_V = f'{BASE_STR}_v'
ACCENTED_TEXT = f'{BASE_STR}{''.join(reversed(BASE_STR))}'


def feed_key(parser: BaseParser, *chunks: str) -> None:
    """Deliver *chunks* to *parser* as if they were a metadata key."""
    parser.within_k = True
    for chunk in chunks:
        parser.handle_data(chunk)
    parser.within_k = False


def feed_value(parser: BaseParser, *chunks: str) -> None:
    """Deliver *chunks* to *parser* as if they were a metadata value."""
    parser.within_v = True
    for chunk in chunks:
        parser.handle_data(chunk)
    parser.within_v = False


@pytest.mark.parametrize(('data', 'expected'), [
    pytest.param(
        SAMPLE_K,
        SAMPLE_K,
        id='plain',
    ),
    pytest.param(
        f'  {SAMPLE_K}  ',
        SAMPLE_K,
        id='padded',
    ),
    pytest.param(
        f'\n\t{SAMPLE_K}\n  x{SAMPLE_K}\t\n',
        f'{SAMPLE_K} x{SAMPLE_K}',
        id='newlines_and_tabs',
    ),
    pytest.param(
        f'{SAMPLE_K}\xa0o{SAMPLE_K}',
        f'{SAMPLE_K} o{SAMPLE_K}',
        id='nbsp',
    ),
    pytest.param(
        f'{SAMPLE_K}\r\n n{SAMPLE_K}',
        f'{SAMPLE_K} n{SAMPLE_K}',
        id='cr',
    ),
    pytest.param(
        ACCENTED_TEXT,
        ACCENTED_TEXT,
        id='accents',
    ),
    pytest.param(
        ' \n\t ',
        '',
        id='whitespace',
    ),
    pytest.param(
        f'{SAMPLE_K}:',
        SAMPLE_K,
        id='colon',
    ),
    pytest.param(
        f'{SAMPLE_K}::',
        SAMPLE_K,
        id='colons',
    ),
    pytest.param(
        f'{SAMPLE_K}: ',
        SAMPLE_K,
        id='colon_trailing_space',
    ),
    pytest.param(
        f'{SAMPLE_K}:{SAMPLE_K}o',
        f'{SAMPLE_K}:{SAMPLE_K}o',
        id='inner_colon',
    ),
    pytest.param(
        ':',
        '',
        id='only_colon',
    ),

    # Current behavior: this may change if boundary whitespace tracking
    # is added in the future.
    pytest.param(
        f'{SAMPLE_K} :',
        f'{SAMPLE_K} ',
        id='space_before_colon',
    ),
])
# pylint: disable-next=unused-variable
def test_key_data(data: str, expected: str) -> None:
    """Test the handling of data found inside a metadata key."""
    parser = BaseParser()

    feed_key(parser, data)

    assert parser.current_k == expected
    assert parser.last_k == expected


# pylint: disable-next=unused-variable
def test_key_split_across_tags() -> None:
    """Test a key whose data arrives in several chunks."""
    # Current behavior: this may change if boundary whitespace tracking
    # is added in the future.
    parser = BaseParser()

    feed_key(parser, f'{SAMPLE_K} ', SAMPLE_K, ':')

    assert parser.current_k == f'{SAMPLE_K}{SAMPLE_K}'


@pytest.mark.parametrize(('data', 'expected_value'), [
    pytest.param(
        SAMPLE_V,
        SAMPLE_V,
        id='plain',
    ),
    pytest.param(
        f'  {SAMPLE_V}  ',
        SAMPLE_V,
        id='padded',
    ),
    pytest.param(
        f'\n\t{SAMPLE_V}\n  x{SAMPLE_V}\t\n',
        f'{SAMPLE_V} x{SAMPLE_V}',
        id='newlines_and_tabs',
    ),
    pytest.param(
        f'{SAMPLE_V}\xa0o{SAMPLE_V}',
        f'{SAMPLE_V} o{SAMPLE_V}',
        id='nbsp',
    ),
    pytest.param(
        f'{SAMPLE_V}\r\nn{SAMPLE_V}',
        f'{SAMPLE_V} n{SAMPLE_V}',
        id='cr',
    ),
    pytest.param(
        ACCENTED_TEXT,
        ACCENTED_TEXT,
        id='accents',
    ),
    pytest.param(
        ' \n\t ',
        '',
        id='whitespace',
    ),
    pytest.param(
        f'{SAMPLE_V}:{SAMPLE_V}o',
        f'{SAMPLE_V}:{SAMPLE_V}o',
        id='inner_colon',
    ),
    pytest.param(
        f'{SAMPLE_V}:',
        f'{SAMPLE_V}:',
        id='trailing_colon',
    ),
])
# pylint: disable-next=unused-variable
def test_value_data(data: str, expected_value: str) -> None:
    """Test the handling of data found inside a metadata value."""
    parser = BaseParser()

    feed_value(parser, data)

    assert parser.current_v == expected_value


@pytest.mark.parametrize('chunks', [
    pytest.param(
        (SAMPLE_V, SAMPLE_V),
        id='two_chunks',
    ),
    pytest.param(
        (SAMPLE_V, ' ', SAMPLE_V),
        id='blank_chunk_skipped',
    ),
])
# pylint: disable-next=unused-variable
def test_value_chunks(chunks: tuple[str, ...]) -> None:
    """Test a value whose data arrives in several chunks."""
    parser = BaseParser()

    feed_value(parser, *chunks)

    assert parser.current_v == BaseParser.MULTIDATA_SEPARATOR.join((SAMPLE_V, SAMPLE_V))


# pylint: disable-next=unused-variable
def test_data_outside_key_and_value() -> None:
    """Test that data found outside keys and values is ignored."""
    parser = BaseParser()

    parser.handle_data(SAMPLE_V)
    parser.commit_metadata()

    assert parser.current_k == BaseParser.DEFAULT_K
    assert parser.current_v == BaseParser.DEFAULT_V
    assert parser.last_k == BaseParser.DEFAULT_K
    assert not parser.get_metadata()


@pytest.mark.parametrize(('markup', 'expected'), [
    pytest.param(
        f'{SAMPLE_V} &amp; a{SAMPLE_V}',
        f'{SAMPLE_V} & a{SAMPLE_V}',
        id='amp',
    ),
    pytest.param(
        f'&lt;{SAMPLE_V}&gt;',
        f'<{SAMPLE_V}>',
        id='angle_brackets',
    ),
    pytest.param(
        f'{SAMPLE_V}&#233;',
        f'{SAMPLE_V}é',
        id='numeric',
    ),
    pytest.param(
        f'{SAMPLE_V}&eacute;',
        f'{SAMPLE_V}é',
        id='named',
    ),
    pytest.param(
        f'{SAMPLE_V}&nbsp;n{SAMPLE_V}',
        f'{SAMPLE_V} n{SAMPLE_V}',
        id='nbsp',
    ),
    pytest.param(
        f'{SAMPLE_V}&nbsp;&nbsp;nn{SAMPLE_V}',
        f'{SAMPLE_V} nn{SAMPLE_V}',
        id='nbsp_run',
    ),
])
# pylint: disable-next=unused-variable
def test_character_references(markup: str, expected: str) -> None:
    """Test that charrefs are converted before handling data."""
    parser = BaseParser()

    parser.within_v = True
    parser.feed(markup)
    parser.close()
    parser.within_v = False

    assert parser.current_v == expected


@pytest.mark.parametrize(('key', 'value', 'expected'), [
    pytest.param(
        '',
        '',
        [Debug.METADATA_IS_EMPTY],
        id='empty',
    ),
    pytest.param(
        SAMPLE_K,
        '',
        [Debug.METADATA_MISSING_VALUE.format(SAMPLE_K)],
        id='no_value',
    ),
    pytest.param(
        '',
        SAMPLE_V,
        [
            Debug.METADATA_MISSING_KEY.format(BaseParser.EMPTY_KEY_PLACEHOLDER),
            Debug.METADATA_OK.format(BaseParser.EMPTY_KEY_PLACEHOLDER, SAMPLE_V),
        ],
        id='no_key',
    ),
    pytest.param(
        SAMPLE_K,
        SAMPLE_V,
        [Debug.METADATA_OK.format(SAMPLE_K, SAMPLE_V)],
        id='full',
    ),
])
# pylint: disable-next=unused-variable
def test_commit_branches(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: str,
    expected: list[str],
) -> None:
    """Test all `commit_metadata()` branches."""
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)
    parser = BaseParser()

    parser.current_k = key
    parser.current_v = value
    parser.commit_metadata()

    assert caplog.messages == expected
    assert parser.current_k == BaseParser.DEFAULT_K
    assert parser.current_v == BaseParser.DEFAULT_V


# pylint: disable-next=unused-variable
def test_commit_reuses_last_key() -> None:
    """Test that a value without key is stored under the last key found."""
    parser = BaseParser()

    value1, value2 = f'{SAMPLE_V}1', f'{SAMPLE_V}2'
    feed_key(parser, SAMPLE_K)
    feed_value(parser, value1)
    parser.commit_metadata()
    feed_value(parser, value2)
    parser.commit_metadata()

    assert parser.get_metadata() == {SAMPLE_K: BaseParser.MULTIVALUE_SEPARATOR.join((value1, value2))}


# pylint: disable-next=unused-variable
def test_commit_last_key_follows_latest_key() -> None:
    """Test that the key reused for a value without key is the latest one."""
    parser = BaseParser()

    key1, key2 = f'{SAMPLE_K}1', f'{SAMPLE_K}2'
    value1, value2, value3 = f'{SAMPLE_V}1', f'{SAMPLE_V}2', f'{SAMPLE_V}3'

    feed_key(parser, key1)
    feed_value(parser, value1)
    parser.commit_metadata()

    feed_key(parser, key2)
    feed_value(parser, value2)
    parser.commit_metadata()

    feed_value(parser, value3)
    parser.commit_metadata()

    assert list(parser.get_metadata().items()) == [
        (key1, value1),
        (key2, BaseParser.MULTIVALUE_SEPARATOR.join((value2, value3))),
    ]


# pylint: disable-next=unused-variable
def test_commit_duplicate_value(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a duplicate value is ignored and logged."""
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)
    parser = BaseParser()

    for _ in range(2):
        parser.current_k = SAMPLE_K
        parser.current_v = SAMPLE_V
        parser.commit_metadata()

    assert caplog.messages == [
        Debug.METADATA_OK.format(SAMPLE_K, SAMPLE_V),
        Debug.METADATA_DUPLICATE.format(SAMPLE_K, SAMPLE_V),
    ]


@pytest.mark.parametrize(('pairs', 'expected'), [
    pytest.param(
        [(SAMPLE_K, SAMPLE_V)],
        [(SAMPLE_K, SAMPLE_V)],
        id='single',
    ),
    pytest.param(
        [(SAMPLE_K, SAMPLE_V), (SAMPLE_K, SAMPLE_V)],
        [(SAMPLE_K, SAMPLE_V)],
        id='duplicate_value',
    ),
    pytest.param(
        [(SAMPLE_K, SAMPLE_V), (SAMPLE_K, f'o{SAMPLE_V}'), (SAMPLE_K, SAMPLE_V)],
        [(SAMPLE_K, BaseParser.MULTIVALUE_SEPARATOR.join((SAMPLE_V, f'o{SAMPLE_V}')))],
        id='duplicate_not_adjacent',
    ),
    pytest.param(
        [(SAMPLE_K, SAMPLE_V), (SAMPLE_K, f'o{SAMPLE_V}')],
        [(SAMPLE_K, BaseParser.MULTIVALUE_SEPARATOR.join((SAMPLE_V, f'o{SAMPLE_V}')))],
        id='same_key',
    ),
    pytest.param(
        [(SAMPLE_K, f'o{SAMPLE_V}'), (SAMPLE_K, SAMPLE_V)],
        [(SAMPLE_K, BaseParser.MULTIVALUE_SEPARATOR.join((f'o{SAMPLE_V}', SAMPLE_V)))],
        id='values_order',
    ),
    pytest.param(
        [(SAMPLE_K, SAMPLE_V), (f'o{SAMPLE_K}', f'o{SAMPLE_V}')],
        [(SAMPLE_K, SAMPLE_V), (f'o{SAMPLE_K}', f'o{SAMPLE_V}')],
        id='two_keys',
    ),
    pytest.param(
        [(f'o{SAMPLE_K}', f'o{SAMPLE_V}'), (SAMPLE_K, SAMPLE_V)],
        [(f'o{SAMPLE_K}', f'o{SAMPLE_V}'), (SAMPLE_K, SAMPLE_V)],
        id='keys_order',
    ),
])
# pylint: disable-next=unused-variable
def test_commit_storage(pairs: list[tuple[str, str]], expected: list[tuple[str, str]]) -> None:
    """Test duplicate handling and ordering of committed metadata."""
    parser = BaseParser()

    for key, value in pairs:
        parser.current_k = key
        parser.current_v = value
        parser.commit_metadata()

    assert list(parser.get_metadata().items()) == expected


@pytest.mark.parametrize(('raw_metadata', 'expected'), [
    pytest.param(
        {},
        {},
        id='empty',
    ),
    pytest.param(
        {SAMPLE_K: [SAMPLE_V]},
        {SAMPLE_K: SAMPLE_V},
        id='single',
    ),
    pytest.param(
        {SAMPLE_K: [SAMPLE_V, f'o{SAMPLE_V}', f'x{SAMPLE_V}']},
        {SAMPLE_K: BaseParser.MULTIVALUE_SEPARATOR.join((SAMPLE_V, f'o{SAMPLE_V}', f'x{SAMPLE_V}'))},
        id='multivalue',
    ),
    pytest.param(
        {SAMPLE_K: [SAMPLE_V], f'o{SAMPLE_K}': [f'o{SAMPLE_V}', f'x{SAMPLE_V}']},
        {SAMPLE_K: SAMPLE_V, f'o{SAMPLE_K}': BaseParser.MULTIVALUE_SEPARATOR.join((f'o{SAMPLE_V}', f'x{SAMPLE_V}'))},
        id='several_keys',
    ),
])
# pylint: disable-next=unused-variable
def test_get_metadata_joins(raw_metadata: dict[str, list[str]], expected: dict[str, str]) -> None:
    """Test that `get_metadata()` joins the values of each key."""
    parser = BaseParser()

    parser.retrieved_metadata = raw_metadata

    assert parser.get_metadata() == expected


# pylint: disable-next=unused-variable
def test_get_metadata_keeps_raw_metadata() -> None:
    """Test that `get_metadata()` does not alter the metadata."""
    parser = BaseParser()

    other_value = f'o{SAMPLE_V}'
    parser.retrieved_metadata = {SAMPLE_K: [SAMPLE_V, other_value]}

    assert parser.get_metadata() == {SAMPLE_K: BaseParser.MULTIVALUE_SEPARATOR.join((SAMPLE_V, other_value))}
    assert parser.get_metadata() == {SAMPLE_K: BaseParser.MULTIVALUE_SEPARATOR.join((SAMPLE_V, other_value))}
    assert parser.retrieved_metadata == {SAMPLE_K: [SAMPLE_V, other_value]}


# pylint: disable-next=unused-variable
def test_reset_clears_state() -> None:
    """Test that `reset()` leaves the parser in its initial state."""
    parser = BaseParser()

    parser.within_k = True
    parser.within_v = True
    parser.current_k = SAMPLE_K
    parser.current_v = SAMPLE_V
    parser.last_k = SAMPLE_K
    parser.retrieved_metadata = {SAMPLE_K: [SAMPLE_V]}
    parser.reset()

    assert parser.within_k is False
    assert parser.within_v is False
    assert parser.current_k == BaseParser.DEFAULT_K
    assert parser.current_v == BaseParser.DEFAULT_V
    assert parser.last_k == BaseParser.DEFAULT_K
    assert not parser.retrieved_metadata
    assert not parser.get_metadata()


# pylint: disable-next=unused-variable
def test_configure_keeps_supported_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `configure()` silently drops unsupported parameters."""
    supported_parameter = f'{BASE_STR}_s'
    supported_pattern = re_compile(supported_parameter)
    unsupported_parameter = f'{BASE_STR}_u'
    monkeypatch.setattr(BaseParser, 'PARAMETERS', {supported_parameter})
    parser = BaseParser()

    parser.configure({supported_parameter: supported_pattern, unsupported_parameter: re_compile(unsupported_parameter)})

    assert parser.config == {supported_parameter: supported_pattern}


# pylint: disable-next=unused-variable
def test_configure_replaces_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `configure()` does not keep old parameters."""
    monkeypatch.setattr(BaseParser, 'PARAMETERS', {BASE_STR})
    parser = BaseParser()

    parser.configure({BASE_STR: re_compile(BASE_STR)})
    parser.configure({})

    assert not parser.config


# pylint: disable-next=unused-variable
def test_configure_resets_state() -> None:
    """Test that `configure()` also resets the parser state."""
    parser = BaseParser()

    feed_key(parser, SAMPLE_K)
    feed_value(parser, SAMPLE_V)
    parser.commit_metadata()

    parser.current_k = f'{SAMPLE_K}o'
    parser.current_v = f'{SAMPLE_V}o'
    parser.configure({})

    assert parser.current_k == BaseParser.DEFAULT_K
    assert parser.current_v == BaseParser.DEFAULT_V
    assert parser.last_k == BaseParser.DEFAULT_K
    assert not parser.get_metadata()


# pylint: disable-next=unused-variable
def test_reuse_forgets_last_key() -> None:
    """Test that a reused parser does not inherit the last key."""
    parser = BaseParser()

    feed_key(parser, SAMPLE_K)
    feed_value(parser, SAMPLE_V)
    parser.commit_metadata()
    parser.configure({})
    other_value = f'o{SAMPLE_V}o'
    feed_value(parser, other_value)
    parser.commit_metadata()

    assert parser.get_metadata() == {BaseParser.EMPTY_KEY_PLACEHOLDER: other_value}


# pylint: disable-next=unused-variable
def test_reuse_forgets_unfinished_values() -> None:
    """Test that a reused parser does not inherit unfinished values."""
    parser = BaseParser()

    parser.within_v = True
    parser.handle_data(SAMPLE_V)
    parser.configure({})
    parser.handle_data(f'o{SAMPLE_V}o')
    parser.commit_metadata()

    assert parser.current_v == BaseParser.DEFAULT_V
    assert not parser.get_metadata()


# pylint: disable-next=unused-variable
def test_colon_only_key_wipes_last_key() -> None:
    """Test the last key after a key which contains only the colon."""
    # Current behavior: a key made only of the terminator wipes the last
    # key, so the next value without key gets the placeholder.
    parser = BaseParser()

    feed_key(parser, f'{SAMPLE_K}:')
    feed_value(parser, SAMPLE_V)
    parser.commit_metadata()
    other_value = f'o{SAMPLE_V}o'
    feed_key(parser, ':')
    feed_value(parser, other_value)
    parser.commit_metadata()

    assert list(parser.get_metadata().items()) == [
        (SAMPLE_K, SAMPLE_V),
        (BaseParser.EMPTY_KEY_PLACEHOLDER, other_value),
    ]


SAMPLE_TAG = BASE_STR.replace(' ', '_')

@pytest.mark.parametrize(('attrs', 'expected'), [
    pytest.param(
        [],
        Debug.HTML_START_TAG.format(SAMPLE_TAG, '', ''),
        id='no_attrs',
    ),
    pytest.param(
        [(SAMPLE_K, SAMPLE_V)],
        Debug.HTML_START_TAG.format(SAMPLE_TAG, ' ', f'{SAMPLE_K}="{SAMPLE_V}"'),
        id='one_attr',
    ),
    pytest.param(
        [(SAMPLE_K, SAMPLE_V), (f'o{SAMPLE_K}', f'o{SAMPLE_V}')],
        Debug.HTML_START_TAG.format(SAMPLE_TAG, ' ', f'{SAMPLE_K}="{SAMPLE_V}" o{SAMPLE_K}="o{SAMPLE_V}"'),
        id='two_attrs',
    ),

    # Current behavior: an attribute without value is logged as "None".
    pytest.param(
        [(SAMPLE_K, None)],
        Debug.HTML_START_TAG.format(SAMPLE_TAG, ' ', f'{SAMPLE_K}="None"'),
        id='valueless_attr',
    ),
])
# pylint: disable-next=unused-variable
def test_start_tag_logging(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    attrs: list[tuple[str, str | None]],
    expected: str,
) -> None:
    """Test the message logged for each start tag."""
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)
    parser = BaseParser()

    parser.handle_starttag(SAMPLE_TAG, attrs)

    assert caplog.messages == [expected]


TAG = 'div'
ELEMENT_B, ELEMENT_E = '<{TAG} class="{MARKER}_suffix">', '</{TAG}>'
SAMPLE_MARKER = BASE_STR.replace(' ', '_')


K_CLASS, V_CLASS = f'{SAMPLE_MARKER}_k', f'{SAMPLE_MARKER}_v'
K_CLASS_RE, V_CLASS_RE = re_compile(f'{K_CLASS}.*'), re_compile(f'{V_CLASS}.*')
OP_KB, OP_VB = ELEMENT_B.format(TAG=TAG, MARKER=K_CLASS), ELEMENT_B.format(TAG=TAG, MARKER=V_CLASS)
OP_EE = ELEMENT_E.format(TAG=TAG)


@pytest.mark.parametrize(('markup', 'expected'), [
    # Normal metadata.
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='baseline',
    ),

    # Incomplete metadata, missing value.
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}',
        {},
        id='no_value_1',
    ),
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{OP_EE}',
        {},
        id='no_value_2',
    ),
    pytest.param(
        f'{OP_VB}{SAMPLE_V}',
        {},
        id='no_value_3',
    ),
    pytest.param(
        f'{OP_VB}{OP_EE}',
        {},
        id='no_value_4',
    ),

    # Incomplete metadata, missing key.
    pytest.param(
        f'{OP_KB}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='no_key_1',
    ),
    pytest.param(
        f'{OP_VB}{SAMPLE_V}{OP_EE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='no_key_2',
    ),

    # Nesting, value inside key.
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='v_in_k_1',
    ),
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_VB}{OP_EE}',
        {},
        id='v_in_k_2',
    ),

    # Nesting, key inside value.
    pytest.param(
        f'{OP_VB}_{SAMPLE_V}_{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='k_in_v_1',
    ),
    pytest.param(
        f'{OP_VB}{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='k_in_v_2',
    ),
    pytest.param(
        f'{OP_VB}_{SAMPLE_V}_{OP_KB}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='k_in_v_3',
    ),
    pytest.param(
        f'{OP_VB}{OP_KB}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='k_in_v_4',
    ),
    pytest.param(
        f'{OP_VB}_{SAMPLE_V}_{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}',
        {},
        id='k_in_v_5',
    ),
    pytest.param(
        f'{OP_VB}{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}',
        {},
        id='k_in_v_6',
    ),

    # Nesting, key inside key and value inside value.
    pytest.param(
        f'{OP_KB}_{SAMPLE_K}_{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='k_in_k',
    ),
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}_{SAMPLE_V}_{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='v_in_v',
    ),

    # Ill-formed, no closing tags.
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_VB}{SAMPLE_V}',
        {},
        id='unclosed_1',
    ),
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_VB}',
        {},
        id='unclosed_2',
    ),
    pytest.param(
        f'{OP_KB}{OP_VB}{SAMPLE_V}',
        {},
        id='unclosed_3',
    ),
    pytest.param(
        f'{OP_KB}{OP_VB}',
        {},
        id='unclosed_4',
    ),

    # Ill-formed, marker tag without a usable class attribute.
    pytest.param(
        f'<{TAG}></{TAG}>',
        {},
        id='no_class',
    ),
    pytest.param(
        f'<{TAG} class></{TAG}>',
        {},
        id='empty_class',
    ),
    pytest.param(
        f'<{TAG} wrong="wrong"></{TAG}>',
        {},
        id='wrong_attr',
    ),

    # Marker tag matching both patterns, taken as a key.
    pytest.param(
        f'<{TAG} class="{K_CLASS} {V_CLASS}">{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='both_markers',
    ),
])
# pylint: disable-next=unused-variable
def test_old_regime_parser(markup: str, expected: dict[str, str]) -> None:
    """Test *Old Regime* parser."""
    parser = OldRegimeParser()

    parser.configure({OldRegimeParser.K_CLASS: K_CLASS_RE, OldRegimeParser.V_CLASS: V_CLASS_RE})
    parser.feed(markup)
    parser.close()

    assert parser.get_metadata() == expected


M_TAG, M_ATTR, M_VALUE = 'dl', 'class', f'{SAMPLE_MARKER}_m'
M_TAG_RE, M_ATTR_RE, M_VALUE_RE = re_compile(f'{M_TAG}.*'), re_compile(f'{M_ATTR}.*'), re_compile(f'{M_VALUE}.*')
BP_MB, BP_ME = ELEMENT_B.format(TAG=M_TAG, MARKER=M_VALUE), ELEMENT_E.format(TAG=M_TAG)
BP_KB, BP_KE = f'<{BaratzParser.K_TAG}>', f'</{BaratzParser.K_TAG}>'
BP_VB, BP_VE = f'<{BaratzParser.V_TAG}>', f'</{BaratzParser.V_TAG}>'


@pytest.mark.parametrize(('markup', 'expected'), [
    # Normal metadata.
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}{BP_ME}',
        {SAMPLE_K: SAMPLE_V},
        id='pair_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {SAMPLE_K: SAMPLE_V},
        id='pair_2',
    ),

    # No metadata marker.
    pytest.param(
        f'{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}{BP_ME}',
        {},
        id='no_marker_1',
    ),
    pytest.param(
        f'{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {},
        id='no_marker_2',
    ),

    # Missing metadata.
    pytest.param(
        f'{BP_MB}<wrong></wrong>{BP_ME}',
        {},
        id='no_metadata',
    ),

    # Incomplete metadata, missing value.
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}',
        {},
        id='no_value_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{BP_VE}',
        {},
        id='no_value_2',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{SAMPLE_V}',
        {},
        id='no_value_3',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{BP_VE}',
        {},
        id='no_value_4',
    ),

    # Incomplete metadata, missing key.
    pytest.param(
        f'{BP_MB}{BP_KB}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='no_key_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{SAMPLE_V}{BP_VE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='no_key_2',
    ),

    # Nesting, value inside key.
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_VB}{SAMPLE_V}{BP_VE}{BP_KE}',
        {SAMPLE_K: SAMPLE_V},
        id='v_in_k_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_VB}{BP_VE}{BP_KE}',
        {},
        id='v_in_k_2',
    ),

    # Nesting, key inside value.
    pytest.param(
        f'{BP_MB}{BP_VB}_{SAMPLE_V}_{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {SAMPLE_K: SAMPLE_V},
        id='k_in_v_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {SAMPLE_K: SAMPLE_V},
        id='k_in_v_2',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}_{SAMPLE_V}_{BP_KB}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='k_in_v_3',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{BP_KB}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='k_in_v_4',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}_{SAMPLE_V}_{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}',
        {},
        id='k_in_v_5',
    ),
    pytest.param(
        f'{BP_MB}{BP_VB}{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}',
        {},
        id='k_in_v_6',
    ),

    # Ill-formed, no closing tags.
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_VB}{SAMPLE_V}',
        {},
        id='unclosed_1',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_VB}',
        {},
        id='unclosed_2',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{BP_VB}{SAMPLE_V}',
        {},
        id='unclosed_3',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{BP_VB}',
        {},
        id='unclosed_4',
    ),

    # Ill-formed, metadata marker tag without a usable class attribute.
    pytest.param(
        f'<{M_TAG}></{M_TAG}>',
        {},
        id='no_class',
    ),
    pytest.param(
        f'<{M_TAG} class></{M_TAG}>',
        {},
        id='empty_class',
    ),
    pytest.param(
        f'<{M_TAG} wrong="wrong"></{M_TAG}>',
        {},
        id='wrong_attr',
    ),

    # Invalid catalogue structure.
    pytest.param(
        f'{BP_MB}{BP_KB}_{SAMPLE_K}_{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}',
        {SAMPLE_K: SAMPLE_V},
        id='k_in_k',
    ),
    pytest.param(
        f'{BP_MB}{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}_{SAMPLE_V}_{BP_VB}{SAMPLE_V}{BP_VE}',
        {SAMPLE_K: SAMPLE_V},
        id='v_in_v',
    ),
])
# pylint: disable-next=unused-variable
def test_baratz_parser(markup: str, expected: dict[str, str]) -> None:
    """Test *Baratz* parser."""
    parser = BaratzParser()

    parser.configure({BaratzParser.M_TAG: M_TAG_RE, BaratzParser.M_ATTR: M_ATTR_RE, BaratzParser.M_VALUE: M_VALUE_RE})
    parser.feed(markup)
    parser.close()

    assert parser.get_metadata() == expected


@pytest.mark.parametrize(('markup', 'expected'), [
    # Marker in the class attribute.
    pytest.param(
        f'<{TAG} class="{SAMPLE_MARKER} {K_CLASS} {SAMPLE_MARKER}">{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='multi_class',
    ),
    pytest.param(
        f'<{TAG} id="{SAMPLE_MARKER}" class="{K_CLASS}">{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='class_not_first',
    ),
    pytest.param(
        f'<{TAG} id="{K_CLASS}">{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {BaseParser.EMPTY_KEY_PLACEHOLDER: SAMPLE_V},
        id='other_attr',
    ),

    # Key and value in different tags, other tags inside them.
    pytest.param(
        f'<td class="{K_CLASS}">{SAMPLE_K}</td><span class="{V_CLASS}">{SAMPLE_V}</span>',
        {SAMPLE_K: SAMPLE_V},
        id='different_tags',
    ),
    pytest.param(
        f'{OP_KB}{SAMPLE_K}<b></b>o{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {f'{SAMPLE_K}o{SAMPLE_K}': SAMPLE_V},
        id='inner_tag_key',
    ),
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}<b></b>o{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: BaseParser.MULTIDATA_SEPARATOR.join((SAMPLE_V, f'o{SAMPLE_V}'))},
        id='inner_tag_value',
    ),

    # Current behavior: a nested tag with the same name as the marker
    # tag ends the key or the value, and the text after it is lost.
    pytest.param(
        f'{OP_KB}{SAMPLE_K}<{TAG}></{TAG}>_{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='same_tag_key',
    ),
    pytest.param(
        f'{OP_KB}{SAMPLE_K}{OP_EE}{OP_VB}{SAMPLE_V}<{TAG}></{TAG}>_{SAMPLE_V}{OP_EE}',
        {SAMPLE_K: SAMPLE_V},
        id='same_tag_value',
    ),
])
# pylint: disable-next=unused-variable
def test_old_regime_markers(markup: str, expected: dict[str, str]) -> None:
    """Test the marker matching of *Old Regime* parser."""
    parser = OldRegimeParser()

    parser.configure({OldRegimeParser.K_CLASS: K_CLASS_RE, OldRegimeParser.V_CLASS: V_CLASS_RE})
    parser.feed(markup)
    parser.close()

    assert parser.get_metadata() == expected


BP_PAIR = f'{BP_KB}{SAMPLE_K}{BP_KE}{BP_VB}{SAMPLE_V}{BP_VE}'
BP_OTHER_PAIR = f'{BP_KB}o{SAMPLE_K}{BP_KE}{BP_VB}o{SAMPLE_V}{BP_VE}'


@pytest.mark.parametrize(('markup', 'expected'), [
    # Marker tag, attribute name and value matching.
    pytest.param(
        f'<{M_TAG} class="{SAMPLE_MARKER} {M_VALUE} {SAMPLE_MARKER}">{BP_PAIR}{BP_ME}',
        {SAMPLE_K: SAMPLE_V},
        id='value_in_list',
    ),
    pytest.param(
        f'<{M_TAG} id="{SAMPLE_MARKER}" class="{M_VALUE}">{BP_PAIR}{BP_ME}',
        {SAMPLE_K: SAMPLE_V},
        id='attr_not_first',
    ),
    pytest.param(
        f'<{M_TAG}x class="{M_VALUE}">{BP_PAIR}</{M_TAG}x>',
        {},
        id='tag_longer',
    ),
    pytest.param(
        f'<{M_TAG} {M_ATTR}x="{M_VALUE}">{BP_PAIR}{BP_ME}',
        {},
        id='attr_longer',
    ),
    pytest.param(
        f'<{M_TAG} id="{M_VALUE}">{BP_PAIR}{BP_ME}',
        {},
        id='attr_other',
    ),
    pytest.param(
        f'<{M_TAG} class="{SAMPLE_MARKER}">{BP_PAIR}{BP_ME}',
        {},
        id='value_other',
    ),

    # Metadata blocks.
    pytest.param(
        f'{BP_MB}{BP_PAIR}{BP_ME}{BP_MB}{BP_OTHER_PAIR}{BP_ME}',
        {SAMPLE_K: SAMPLE_V, f'o{SAMPLE_K}': f'o{SAMPLE_V}'},
        id='two_blocks',
    ),
    pytest.param(
        f'{BP_OTHER_PAIR}{BP_MB}{BP_PAIR}{BP_ME}',
        {SAMPLE_K: SAMPLE_V},
        id='pair_before_block',
    ),
    pytest.param(
        f'{BP_MB}{BP_PAIR}{BP_ME}{BP_OTHER_PAIR}',
        {SAMPLE_K: SAMPLE_V},
        id='pair_after_block',
    ),

    pytest.param(
        f'{BP_MB}{BP_PAIR}<{M_TAG}x></{M_TAG}x>{BP_OTHER_PAIR}{BP_ME}',
        {SAMPLE_K: SAMPLE_V, f'o{SAMPLE_K}': f'o{SAMPLE_V}'},
        id='inner_longer_tag',
    ),

    # Current behavior: a nested tag with the same name as the marker
    # tag ends the metadata block, and what follows is lost.
    pytest.param(
        f'{BP_MB}{BP_PAIR}<{M_TAG}></{M_TAG}>{BP_OTHER_PAIR}{BP_ME}',
        {SAMPLE_K: SAMPLE_V},
        id='same_tag_block',
    ),
])
# pylint: disable-next=unused-variable
def test_baratz_markers(markup: str, expected: dict[str, str]) -> None:
    """Test the marker matching of *Baratz* parser."""
    parser = BaratzParser()

    parser.configure({
        BaratzParser.M_TAG: re_compile(M_TAG),
        BaratzParser.M_ATTR: re_compile(M_ATTR),
        BaratzParser.M_VALUE: re_compile(M_VALUE),
    })
    parser.feed(markup)
    parser.close()

    assert parser.get_metadata() == expected


# pylint: disable-next=unused-variable
def test_parsers_parameters_are_distinct() -> None:
    """Test that no two parsers share the same set of parameters."""
    parameter_sets = [frozenset(parser_class.PARAMETERS) for parser_class in BaseParser.__subclasses__()]

    duplicates = [parameters for parameters in parameter_sets if parameter_sets.count(parameters) > 1]

    assert not duplicates
