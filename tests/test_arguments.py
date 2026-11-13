"""Test suite for argument handling."""
import logging

import pytest

from sacamantecas import (
    Debug,
    Gateway,
    logger,
    parse_arguments,
    SingleUrlGateway,
    SpreadSheetGateway,
    TextFileGateway,
    UnsupportedGateway,
)

URL = 'https://host.domain.tld/page'
STEM = 'file_stem'


@pytest.mark.parametrize(('argument', 'expected'), [
    pytest.param(
        URL,
        SingleUrlGateway,
        id='url',
    ),
    pytest.param(
        URL.upper(),
        SingleUrlGateway,
        id='url_uppercase',
    ),
    pytest.param(
        f'{URL}.txt',
        SingleUrlGateway,
        id='url_with_file_suffix',
    ),
    pytest.param(
        f'{STEM}.txt',
        TextFileGateway,
        id='text_file',
    ),
    pytest.param(
        f'{STEM}.TXT',
        TextFileGateway,
        id='text_file_uppercase',
    ),
    pytest.param(
        f'{STEM}.xlsx',
        SpreadSheetGateway,
        id='spreadsheet',
    ),
    pytest.param(
        f'{STEM}.XLSX',
        SpreadSheetGateway,
        id='spreadsheet_uppercase',
    ),
    pytest.param(
        f'C:\\dir\\{STEM}.txt',
        TextFileGateway,
        id='drive_path',
    ),
    pytest.param(
        f'  {STEM}.txt  ',
        TextFileGateway,
        id='padded',
    ),
    pytest.param(
        f'{STEM}.qxt',
        UnsupportedGateway,
        id='unsupported_extension',
    ),
    pytest.param(
        STEM,
        UnsupportedGateway,
        id='no_extension',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_arguments_gateway_types(argument: str, expected: type[Gateway]) -> None:
    """Test the gateway type chosen for a single argument."""
    gateways = list(parse_arguments(argument))

    assert [type(gateway) for gateway in gateways] == [expected]


@pytest.mark.parametrize(('arguments', 'expected'), [
    pytest.param(
        (),
        [],
        id='no_arguments',
    ),
    pytest.param(
        ('',),
        [],
        id='empty',
    ),
    pytest.param(
        (' \t\n ',),
        [],
        id='whitespace',
    ),
    pytest.param(
        (f'  {STEM}.txt  ',),
        [f'{STEM}.txt'],
        id='padded',
    ),
    pytest.param(
        (f'{STEM}.txt', URL, f'{STEM}.xlsx', STEM),
        [f'{STEM}.txt', URL, f'{STEM}.xlsx', STEM],
        id='order',
    ),
    pytest.param(
        (f'{STEM}.xlsx', '  ', f'{STEM}.txt'),
        [f'{STEM}.xlsx', f'{STEM}.txt'],
        id='blank_between',
    ),
    pytest.param(
        (f'{STEM}.txt', f'{STEM}.txt'),
        [f'{STEM}.txt', f'{STEM}.txt'],
        id='repeated',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_arguments_labels(arguments: tuple[str, ...], expected: list[str]) -> None:
    """Test the labels of the gateways built for several arguments."""
    gateways = list(parse_arguments(*arguments))

    assert [gateway.label for gateway in gateways] == expected


@pytest.mark.parametrize(('argument', 'expected'), [
    pytest.param(
        URL,
        [Debug.PROCESSING_ARG.format(URL), Debug.ARG_IS_SINGLE_URL],
        id='url',
    ),
    pytest.param(
        f'{STEM}.txt',
        [Debug.PROCESSING_ARG.format(f'{STEM}.txt'), Debug.ARG_IS_TEXTFILE],
        id='text_file',
    ),
    pytest.param(
        f'{STEM}.xlsx',
        [Debug.PROCESSING_ARG.format(f'{STEM}.xlsx'), Debug.ARG_IS_SPREADSHEET],
        id='spreadsheet',
    ),
    pytest.param(
        STEM,
        [Debug.PROCESSING_ARG.format(STEM), Debug.ARG_IS_UNSUPPORTED],
        id='unsupported',
    ),
    pytest.param(
        f'  {STEM}.txt  ',
        [Debug.PROCESSING_ARG.format(f'{STEM}.txt'), Debug.ARG_IS_TEXTFILE],
        id='padded',
    ),
    pytest.param(
        '  ',
        [],
        id='blank',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_arguments_messages(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    argument: str,
    expected: list[str],
) -> None:
    """Test the debug messages logged for an argument."""
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)

    list(parse_arguments(argument))

    assert caplog.messages == expected
