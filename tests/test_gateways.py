"""Test suite for the different gateway types."""

import errno
import logging
from pathlib import Path
from typing import NoReturn
import warnings

from openpyxl import load_workbook
from openpyxl.cell.cell import TYPE_STRING as CELLTYPE_STRING
from openpyxl.styles import Font, PatternFill
from openpyxl.workbook.workbook import Workbook
import pytest

from sacamantecas import (
    Debug,
    Gateway,
    GatewayError,
    logger,
    Messages,
    Metadata,
    SingleUrlGateway,
    SkimResults,
    SpreadSheetGateway,
    TextFileGateway,
    UnsupportedGateway,
    Url,
)

SOURCE_LABEL = 'a_source_label'
SOURCE_STEM = 'a_stem'
SOURCE_SUFFIX = '.a_suffix'

URL_A = 'xx://host.domain_a.tld'
URL_B = 'xx://host.domain_b.tld'
URL_C = 'xx://host.domain_c.tld'

SAMPLE_MESSAGE = 'some message'
SAMPLE_KEY = 'A key'
SAMPLE_VALUE = 'A value'


class StubGateway(Gateway):
    """Minimal  gateway whose source yields a preset list of URLs.

    If an exception is given, reading the source raises it instead.

    It also tracks the calls to `_get_urls()` and `_save_metadata()`.
    """

    def __init__(self,
        source: str,
        urls: list[Url],
        read_exception: Exception | None = None,
        save_exception: Exception | None = None,
    ) -> None:
        """Initialize the gateway.

        It receives the *source* label, the *urls* its source will yield
        and two optional exceptions, which if provided will be raised at
        read time (`_get_urls()`) or save time (`_save_metadata()`).
        """
        super().__init__(source)
        self.preset_urls = urls
        self.read_exception = read_exception
        self.save_exception = save_exception
        self.get_urls_calls = 0
        self.save_metadata_calls = 0
        self.received_results: SkimResults = {}
        self.urls_at_save_time: list[Url] = []

    def _get_urls(self) -> list[Url]:
        """Return the stored URLs.

        It also track the number of calls and, if provided, raises the
        preset exception.
        """
        self.get_urls_calls += 1
        if self.read_exception is not None:
            raise self.read_exception
        return self.preset_urls

    def _save_metadata(self, results: SkimResults) -> None:
        """Save metadata from *results*.

        It also tracks the number of calls and, if provided, raises the
        preset exception.

        In addition to all that, it keeps a copy of the URLs as they are
        at the moment this function is called, not at the moment those
        URLs were first obtained. This is useful to check the source is
        seen as it is at save time and not as it was when the URLs were
        returned by `_get_urls()`.

        It also keeps a copy of the received results.
        """
        self.save_metadata_calls += 1
        self.received_results = results
        self.urls_at_save_time = list(self.urls)
        if self.save_exception is not None:
            raise self.save_exception


@pytest.mark.parametrize(('source', 'expected'), [
    pytest.param(
        f'  {SOURCE_LABEL}  ',
        SOURCE_LABEL,
        id='outer_whitespace_stripped',
    ),
    pytest.param(
        f'{SOURCE_LABEL}  {SOURCE_LABEL}',
        f'{SOURCE_LABEL}  {SOURCE_LABEL}',
        id='inner_whitespace_kept',
    ),
    pytest.param(
        f'{SOURCE_LABEL}AbC',
        f'{SOURCE_LABEL}AbC',
        id='case_kept',
    ),
])
# pylint: disable-next=unused-variable
def test_label_strips_surrounding_whitespace(source: str, expected: str) -> None:
    """Test that a gateway strips whitespace from the source name."""
    gateway = StubGateway(source, [])

    assert gateway.label == expected


@pytest.mark.parametrize(('source', 'expected_source_path', 'expected_sink_path'), [
    pytest.param(
        SOURCE_STEM,
        Path(SOURCE_STEM),
        Path(f'{SOURCE_STEM}{Gateway.SINK_STEM}'),
        id='no_suffix',
    ),
    pytest.param(
        f'{SOURCE_STEM}{SOURCE_SUFFIX}',
        Path(f'{SOURCE_STEM}{SOURCE_SUFFIX}'),
        Path(f'{SOURCE_STEM}{Gateway.SINK_STEM}{SOURCE_SUFFIX}'),
        id='suffix',
    ),
    pytest.param(
        f'{SOURCE_STEM}{SOURCE_SUFFIX}{SOURCE_SUFFIX}',
        Path(f'{SOURCE_STEM}{SOURCE_SUFFIX}{SOURCE_SUFFIX}'),
        Path(f'{SOURCE_STEM}{SOURCE_SUFFIX}{Gateway.SINK_STEM}{SOURCE_SUFFIX}'),
        id='two_suffixes',
    ),
    pytest.param(
        f'dir/{SOURCE_STEM}{SOURCE_SUFFIX}',
        Path('dir') / f'{SOURCE_STEM}{SOURCE_SUFFIX}',
        Path('dir') / f'{SOURCE_STEM}{Gateway.SINK_STEM}{SOURCE_SUFFIX}',
        id='directory',
    ),
    pytest.param(
        SOURCE_SUFFIX,
        Path(SOURCE_SUFFIX),
        Path(f'{SOURCE_SUFFIX}{Gateway.SINK_STEM}'),
        id='name_starting_with_dot',
    ),
    pytest.param(
        '..',
        Path('..'),
        Path(f'..{Gateway.SINK_STEM}'),
        id='parent_directory',
    ),
    pytest.param(
        f'  {SOURCE_STEM}{SOURCE_SUFFIX}  ',
        Path(f'{SOURCE_STEM}{SOURCE_SUFFIX}'),
        Path(f'{SOURCE_STEM}{Gateway.SINK_STEM}{SOURCE_SUFFIX}'),
        id='padded_source',
    ),
    pytest.param(
        f'C:\\dir\\{SOURCE_STEM}{SOURCE_SUFFIX}',
        Path(f'C:\\dir\\{SOURCE_STEM}{SOURCE_SUFFIX}'),
        Path('C:\\dir') / f'{SOURCE_STEM}{Gateway.SINK_STEM}{SOURCE_SUFFIX}',
        id='drive_letter',
    ),
    pytest.param(
        f'\\\\host\\share\\dir\\{SOURCE_STEM}{SOURCE_SUFFIX}',
        Path(f'\\\\host\\share\\dir\\{SOURCE_STEM}{SOURCE_SUFFIX}'),
        Path('\\\\host\\share\\dir') / f'{SOURCE_STEM}{Gateway.SINK_STEM}{SOURCE_SUFFIX}',
        id='unc_path',
    ),
])
# pylint: disable-next=unused-variable
def test_paths_from_source(source: str, expected_source_path: Path, expected_sink_path: Path) -> None:
    """Test that a gateway builds paths correctly.

    Its source path should be built from its label string and its sink
    path should be built from the source path.
    """
    gateway = StubGateway(source, [])

    assert (gateway.source_path, gateway.sink_path) == (expected_source_path, expected_sink_path)


@pytest.mark.parametrize('source', [
    pytest.param(
        '',
        id='empty',
    ),
    pytest.param(
        '  \t\n  ',
        id='whitespace',
    ),
    pytest.param(
        '\u00a0\u3000',
        id='unicode_whitespace',
    ),
    pytest.param(
        '.',
        id='dot',
    ),
    pytest.param(
        '  .  ',
        id='padded_dot',
    ),
    pytest.param(
        './',
        id='dot_and_slash',
    ),
    pytest.param(
        'C:\\',
        id='drive_root',
    ),
    pytest.param(
        'C:',
        id='drive_without_directory',
    ),
    pytest.param(
        '\\\\host\\share\\',
        id='unc_share_root',
    ),
])
# pylint: disable-next=unused-variable
def test_source_without_file_name_is_rejected(source: str) -> None:
    """Test that a gateway cannot be created without a file name."""
    with pytest.raises(ValueError, match='has an empty name'):
        StubGateway(source, [])


@pytest.mark.parametrize(('urls', 'expected'), [
    pytest.param(
        [],
        [],
        id='empty',
    ),
    pytest.param(
        [URL_A],
        [URL_A],
        id='single',
    ),
    pytest.param(
        [URL_C, URL_A, URL_B],
        [URL_C, URL_A, URL_B],
        id='distinct-keep-source-order',
    ),
    pytest.param(
        [URL_A, URL_A, URL_B],
        [URL_A, URL_B],
        id='adjacent-duplicates',
    ),
    pytest.param(
        [URL_C, URL_B, URL_C, URL_A, URL_B],
        [URL_C, URL_B, URL_A],
        id='several-duplicates-keeps-first-position',
    ),
    pytest.param(
        [URL_A, URL_A.upper()],
        [URL_A, URL_A.upper()],
        id='letter-case-matters',
    ),
])
# pylint: disable-next=unused-variable
def test_get_urls_unique_in_first_appearance_order(urls: list[Url], expected: list[Url]) -> None:
    """Test that `get_urls()` returns each URL once.

    The order is first appearance.
    """
    gateway = StubGateway(SOURCE_LABEL, urls)

    assert gateway.get_urls() == expected


@pytest.mark.parametrize(('urls', 'expected'), [
    pytest.param(
        [[URL_A, URL_B, URL_A]],
        [URL_A, URL_B],
        id='one_call',
    ),
    pytest.param(
        [[URL_A, URL_B], [URL_B, URL_C]],
        [URL_B, URL_C],
        id='second_call_replaces',
    ),
    pytest.param(
        [[URL_A, URL_B], []],
        [],
        id='second_call_empty_clears',
    ),
])
# pylint: disable-next=unused-variable
def test_get_urls_stores_latest_urls(urls: list[list[Url]], expected: list[Url]) -> None:
    """Test that `get_urls()` stores URLs in `self.urls` as side effect.

    Each successive call replaces previous ones.
    """
    gateway = StubGateway(SOURCE_LABEL, [])

    for source_urls in urls:
        gateway.preset_urls = source_urls
        gateway.get_urls()

    assert gateway.urls == expected


@pytest.mark.parametrize(('raised_exception', 'expected_exception', 'expected_message'), [
    pytest.param(
        FileNotFoundError(),
        GatewayError,
        Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND,
        id='file_not_found',
    ),
    pytest.param(
        PermissionError(),
        GatewayError,
        Messages.GATEWAY_ERROR_INPUT_FILE_NO_PERMISSION,
        id='no_permission',
    ),
    pytest.param(
        OSError(),
        GatewayError,
        Messages.GATEWAY_ERROR_INPUT_FILE_READ_FAILED,
        id='plain_oserror',
    ),
    pytest.param(
        IsADirectoryError(),
        GatewayError,
        Messages.GATEWAY_ERROR_INPUT_FILE_READ_FAILED,
        id='other_oserror_subclass',
    ),
    pytest.param(
        GatewayError(SAMPLE_MESSAGE),
        GatewayError,
        SAMPLE_MESSAGE,
        id='gateway_error_passes_through',
    ),
    pytest.param(
        ValueError(SAMPLE_MESSAGE),
        ValueError,
        SAMPLE_MESSAGE,
        id='value_error_passes_through',
    ),
])
# pylint: disable-next=unused-variable
def test_get_urls_error_mapping(
    raised_exception: Exception,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    """Test that `get_urls()` handles exceptions as it should.

    It maps `OSError` exceptions to `GatewayError` and lets any other
    exception through.
    """
    gateway = StubGateway(SOURCE_LABEL, [], raised_exception)

    with pytest.raises(expected_exception) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == expected_message


# pylint: disable-next=unused-variable
def test_get_urls_failure_keeps_previous_urls() -> None:
    """Test that a failed `get_urls()` keeps `self.urls`."""
    urls = [URL_A, URL_B, URL_C]
    gateway = StubGateway(SOURCE_LABEL, urls)
    gateway.get_urls()
    gateway.read_exception = Exception(SAMPLE_MESSAGE)

    with pytest.raises(Exception, match=SAMPLE_MESSAGE):
        gateway.get_urls()

    assert gateway.urls == urls


# pylint: disable-next=unused-variable
def test_get_urls_rejects_urls_with_nul() -> None:
    """Test that `get_urls()` raises if any URL has a NUL character."""
    gateway = StubGateway(SOURCE_LABEL, [URL_A, f'{URL_B}\x00', URL_C])

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert (str(excinfo.value), gateway.urls) == (Messages.GATEWAY_ERROR_NUL_IN_URLS, [])


# pylint: disable-next=unused-variable
def test_get_urls_nul_failure_keeps_previous_urls() -> None:
    """Test that a NUL validation failure does not replace last URLs."""
    gateway = StubGateway(SOURCE_LABEL, [URL_A])
    gateway.get_urls()
    gateway.preset_urls = [URL_B, f'{URL_C}\x00']

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_NUL_IN_URLS
    assert gateway.urls == [URL_A]


@pytest.mark.parametrize('results', [
    pytest.param(
        {},
        id='no_urls',
    ),
    pytest.param(
        {URL_A: {}, URL_B: {}},
        id='urls_without_metadata',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_rejects_empty_results(results: SkimResults) -> None:
    """Test that `save_metadata()` raises when there is no metadata."""
    gateway = StubGateway(SOURCE_LABEL, [URL_A, URL_B])

    with pytest.raises(GatewayError) as excinfo:
        gateway.save_metadata(results)

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_NO_RESULTS_TO_SAVE
    assert (gateway.get_urls_calls, gateway.save_metadata_calls) == (0, 0)


@pytest.mark.parametrize(('urls', 'results'), [
    pytest.param(
        [URL_A],
        {URL_B: {SAMPLE_KEY: SAMPLE_VALUE}, URL_C: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='only_other_urls',
    ),
    pytest.param(
        [URL_A, URL_B],
        {URL_A: {}, URL_B: {}, URL_C: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='source_urls_without_metadata',
    ),
    pytest.param(
        [URL_A],
        {URL_A.swapcase(): {SAMPLE_KEY: SAMPLE_VALUE}},
        id='url_in_other_case',
    ),
    pytest.param(
        [URL_A],
        {f'  {URL_A}  ': {SAMPLE_KEY: SAMPLE_VALUE}},
        id='url_with_padding',
    ),
    pytest.param(
        [],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='empty_source',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_rejects_results_without_source_urls(urls: list[Url], results: SkimResults) -> None:
    """Test that `save_metadata()` just raises if no URLs have metadata.

    It should raise, saving nothing, if none of the *source_urls* have
    metadata in the *results*.
    """
    gateway = StubGateway(SOURCE_LABEL, urls)

    with pytest.raises(GatewayError) as excinfo:
        gateway.save_metadata(results)

    assert (str(excinfo.value), gateway.save_metadata_calls) == (Messages.GATEWAY_ERROR_NO_RESULTS_TO_SAVE, 0)


@pytest.mark.parametrize('results', [
    pytest.param(
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}, URL_B: {}},
        id='first_url_with_metadata',
    ),
    pytest.param(
        {URL_A: {}, URL_B: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='last_url_with_metadata',
    ),
    pytest.param(
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}, URL_C: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='url_not_in_source_among_others',
    ),
    pytest.param(
        {URL_A: {'': ''}},
        id='empty_strings_as_metadata',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_accepts_results_with_metadata(results: SkimResults) -> None:
    """Test that `save_metadata()` saves the results once."""
    gateway = StubGateway(SOURCE_LABEL, [URL_A, URL_B])

    gateway.save_metadata(results)

    assert gateway.save_metadata_calls == 1


@pytest.mark.parametrize(('read_time_urls', 'save_time_urls', 'expected_urls'), [
    pytest.param(
        [URL_A, URL_B],
        [URL_A, URL_B],
        [URL_A, URL_B],
        id='source_unchanged',
    ),
    pytest.param(
        [URL_A, URL_B],
        [URL_C],
        [URL_C],
        id='source_replaced',
    ),
    pytest.param(
        [URL_A],
        [URL_A, URL_B],
        [URL_A, URL_B],
        id='urls_added',
    ),
    pytest.param(
        [URL_A],
        [URL_B, URL_A, URL_B],
        [URL_B, URL_A],
        id='urls_made_unique',
    ),
    pytest.param(
        [],
        [URL_A, URL_B],
        [URL_A, URL_B],
        id='source_filled',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_reads_urls_again(
    read_time_urls: list[Url],
    save_time_urls: list[Url],
    expected_urls: list[Url],
) -> None:
    """Test that `save_metadata()` saves with up-to-date URLs.

    It checks the results are saved with the URLs the source has at the
    moment the function is called and not the ones from the first read.
    """
    gateway = StubGateway(SOURCE_LABEL, read_time_urls)
    gateway.get_urls()
    gateway.preset_urls = save_time_urls

    gateway.save_metadata({url: {SAMPLE_KEY: SAMPLE_VALUE} for url in (URL_A, URL_B, URL_C)})

    assert gateway.urls_at_save_time == expected_urls


@pytest.mark.parametrize('results', [
    pytest.param(
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='one_url',
    ),
    pytest.param(
        {URL_B: {SAMPLE_KEY: SAMPLE_VALUE}, URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='urls_not_in_source_order',
    ),
    pytest.param(
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE, SAMPLE_KEY[:-1]: SAMPLE_VALUE}},
        id='keys_not_sorted',
    ),
    pytest.param(
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}, URL_B: {}},
        id='url_without_metadata',
    ),
    pytest.param(
        {URL_C: {SAMPLE_KEY: SAMPLE_VALUE}, URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        id='url_not_in_source',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_passes_results_unchanged(results: SkimResults) -> None:
    """Test that `save_metadata()` does not process results.

    It should hand the results to the sink with no filtering, reordering
    or any other modification.
    """
    gateway = StubGateway(SOURCE_LABEL, [URL_A, URL_B])

    gateway.save_metadata(results)

    received = [(url, list(metadata.items())) for url, metadata in gateway.received_results.items()]
    expected = [(url, list(metadata.items())) for url, metadata in results.items()]
    assert received == expected


# pylint: disable-next=unused-variable
def test_save_metadata_unreadable_source_aborts() -> None:
    """Test that `save_metadata()` raises for unreadable sources.

    It should raise when reading the source raises, and in that case, it
    should not save anything.
    """
    gateway = StubGateway(SOURCE_LABEL, [URL_A], Exception(SAMPLE_MESSAGE))

    with pytest.raises(Exception, match=SAMPLE_MESSAGE) as excinfo:
        gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert (str(excinfo.value), gateway.save_metadata_calls) == (SAMPLE_MESSAGE, 0)


@pytest.mark.parametrize(('filename', 'expected'), [
    pytest.param(
        SOURCE_LABEL,
        Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND,
        id='source_file',
    ),
    pytest.param(
        Path(SOURCE_LABEL),
        Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND,
        id='source_file_as_path',
    ),
    pytest.param(
        f'{SOURCE_LABEL}_other',
        Messages.GATEWAY_ERROR_OUTPUT_FILE_NOT_FOUND,
        id='other_file',
    ),
    pytest.param(
        None,
        Messages.GATEWAY_ERROR_OUTPUT_FILE_NOT_FOUND,
        id='no_filename',
    ),
    pytest.param(
        str(Path(SOURCE_LABEL).absolute()),
        Messages.GATEWAY_ERROR_OUTPUT_FILE_NOT_FOUND,
        id='absolute_form_of_source_file',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_missing_file_source_or_sink(filename: str | Path | None, expected: str) -> None:
    """Test that `save_metadata()` treats missing files as it should.

    It should distinguish a missing source file from a missing sink file
    by the file name.
    """
    gateway = StubGateway(SOURCE_LABEL, [URL_A], save_exception=FileNotFoundError(errno.ENOENT, '', filename))

    with pytest.raises(GatewayError) as excinfo:
        gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert str(excinfo.value) == expected


@pytest.mark.parametrize(('label', 'filename'), [
    pytest.param(
        'abc',
        'ABC',
        id='other_case',
    ),
    pytest.param(
        'dir\\abc',
        'dir/abc',
        id='forward_slashes',
    ),
    pytest.param(
        'dir/abc',
        'dir\\abc',
        id='backward_slashes',
    ),
    pytest.param(
        'dir\\abc',
        'dir\\\\abc',
        id='repeated_separators',
    ),
    pytest.param(
        'dir\\abc',
        '.\\dir\\abc',
        id='leading_dot_segment',
    ),
    pytest.param(
        'C:\\dir\\abc',
        'c:\\DIR\\abc',
        id='drive_letter_and_directory_case',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_missing_source_file_windows_spellings(label: str, filename: str) -> None:
    """Test that `save_metadata()` behaves under Windows.

    It should recognize the source file under the equivalent spellings
    of its path on Windows.
    """
    gateway = StubGateway(label, [URL_A], save_exception=FileNotFoundError(errno.ENOENT, '', filename))

    with pytest.raises(GatewayError) as excinfo:
        gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND


@pytest.mark.parametrize(('save_exception', 'expected_exception', 'expected_message'), [
    pytest.param(
        PermissionError(),
        GatewayError,
        Messages.GATEWAY_ERROR_OUTPUT_FILE_NO_PERMISSION,
        id='no_permission',
    ),
    pytest.param(
        OSError(),
        GatewayError,
        Messages.GATEWAY_ERROR_OUTPUT_FILE_WRITE_FAILED,
        id='plain_oserror',
    ),
    pytest.param(
        IsADirectoryError(),
        GatewayError,
        Messages.GATEWAY_ERROR_OUTPUT_FILE_WRITE_FAILED,
        id='other_oserror_subclass',
    ),
    pytest.param(
        GatewayError(SAMPLE_MESSAGE),
        GatewayError,
        SAMPLE_MESSAGE,
        id='gateway_error_passes_through',
    ),
    pytest.param(
        ValueError(SAMPLE_MESSAGE),
        ValueError,
        SAMPLE_MESSAGE,
        id='value_error_passes_through',
    ),
])
# pylint: disable-next=unused-variable
def test_save_metadata_save_error_mapping(
    save_exception: Exception,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    """Test that `save_metadata()` handles exceptions as it should.

    It should map the `OSError` exceptions raised while saving, and let
    any other exception through.
    """
    gateway = StubGateway(SOURCE_LABEL, [URL_A], save_exception=save_exception)

    with pytest.raises(expected_exception) as excinfo:
        gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert str(excinfo.value) == expected_message


# pylint: disable-next=unused-variable
def test_unsupported_gateway_get_urls_raises() -> None:
    """Test that an unsupported gateway raises when asked for its URLs.

    This must not depend on what its source looks like, so an arbitrary
    value is used as the source for the gateway.
    """
    gateway = UnsupportedGateway(SOURCE_STEM)

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_UNSUPPORTED_GATEWAY


# pylint: disable-next=unused-variable
def test_unsupported_gateway_save_metadata_raises() -> None:
    """Test that an unsupported gateway raises on save metadata."""
    gateway = UnsupportedGateway(SOURCE_STEM)

    with pytest.raises(GatewayError) as excinfo:
        gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_UNSUPPORTED_GATEWAY


# pylint: disable-next=unused-variable
def test_unsupported_gateway_private_save_metadata_is_not_implemented() -> None:
    """Test that the unsupported gateway's private save method is a guard."""
    gateway = UnsupportedGateway(SOURCE_STEM)

    with pytest.raises(NotImplementedError):
        # pylint: disable-next=protected-access
        gateway._save_metadata({})  # pyright: ignore[reportPrivateUsage]  # ruff: ignore[SLF001]


@pytest.mark.parametrize(('url', 'expected'), [
    pytest.param(
        'xx://a',
        'xx___a',
        id='scheme_and_host',
    ),
    pytest.param(
        'xx://a.b/c.d',
        'xx___a_b_c_d',
        id='dots_and_slashes',
    ),
    pytest.param(
        'xx://a/b?c=d&e=f#g',
        'xx___a_b_c_d_e_f_g',
        id='query_and_fragment',
    ),
    pytest.param(
        'xx://a:8080/b%20c',
        'xx___a_8080_b_20c',
        id='port_and_percent_encoding',
    ),
    pytest.param(
        'xx://a/',
        'xx___a_',
        id='trailing_slash',
    ),
    pytest.param(
        'xx://A_1/B2',
        'xx___A_1_B2',
        id='word_characters_kept',
    ),
    pytest.param(
        'xx://\u00e1',
        'xx____',
        id='non_ascii_letter',
    ),
    pytest.param(
        'xx://\u0663',
        'xx____',
        id='non_ascii_digit',
    ),
    pytest.param(
        '  xx://a  ',
        'xx___a',
        id='padded_url',
    ),
])
# pylint: disable-next=unused-variable
def test_single_url_gateway_paths(url: str, expected: str) -> None:
    """Test that a single URL gateway uses the URL to build paths.

    It should convert the URL into a safe `.txt` source path, and build
    its sink path from it.
    """
    gateway = SingleUrlGateway(url)

    assert (gateway.source_path, gateway.sink_path) == (
        Path(f'{expected}.txt'),
        Path(f'{expected}{Gateway.SINK_STEM}.txt'),
    )


@pytest.mark.parametrize(('url', 'expected'), [
    pytest.param(
        URL_A,
        URL_A,
        id='plain',
    ),
    pytest.param(
        f'  {URL_A}  ',
        URL_A,
        id='whitespace_padded',
    ),
])
# pylint: disable-next=unused-variable
def test_single_url_gateway_get_urls(url: str, expected: str) -> None:
    """Test that a single URL gateway provides its URL.

    It should remove the whitespace around it.
    """
    gateway = SingleUrlGateway(url)

    assert gateway.get_urls() == [expected]


@pytest.mark.parametrize(('source', 'results', 'expected'), [
    pytest.param(
        URL_A,
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        f'{URL_A}\n\n[{SAMPLE_KEY}] {SAMPLE_VALUE}\n',
        id='one_pair',
    ),
    pytest.param(
        URL_A,
        {URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1', f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'}},
        f'{URL_A}\n\n[{SAMPLE_KEY}1] {SAMPLE_VALUE}1\n[{SAMPLE_KEY}2] {SAMPLE_VALUE}2\n',
        id='pairs_in_given_order',
    ),
    pytest.param(
        URL_A,
        {URL_A: {'kkk': f'{SAMPLE_VALUE}1', 'k': f'{SAMPLE_VALUE}2', 'kk': f'{SAMPLE_VALUE}3'}},
        f'{URL_A}\n\n[kkk] {SAMPLE_VALUE}1\n[k  ] {SAMPLE_VALUE}2\n[kk ] {SAMPLE_VALUE}3\n',
        id='keys_padded_to_the_longest',
    ),
    pytest.param(
        URL_A,
        {URL_A: {SAMPLE_KEY: ''}},
        f'{URL_A}\n\n[{SAMPLE_KEY}] \n',
        id='empty_value',
    ),
    pytest.param(
        URL_A,
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1  {SAMPLE_VALUE}2 / {SAMPLE_VALUE}3'}},
        f'{URL_A}\n\n[{SAMPLE_KEY}] {SAMPLE_VALUE}1  {SAMPLE_VALUE}2 / {SAMPLE_VALUE}3\n',
        id='value_kept_verbatim',
    ),
    pytest.param(
        f'  {URL_A}  ',
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        f'{URL_A}\n\n[{SAMPLE_KEY}] {SAMPLE_VALUE}\n',
        id='padded_source',
    ),
])
# pylint: disable-next=unused-variable
def test_single_url_gateway_sink_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: str,
    results: SkimResults,
    expected: str,
) -> None:
    """Test that a single URL gateway writes results as it should.

    It should write the URL, and then each metadata pair with the keys
    padded to the longest one, keeping order.
    """
    monkeypatch.chdir(tmp_path)
    gateway = SingleUrlGateway(source)

    gateway.save_metadata(results)

    assert gateway.sink_path.read_text(encoding='utf-8') == expected


# pylint: disable-next=unused-variable
def test_single_url_gateway_sink_encoding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that a single URL gateway writes its sink as UTF-8.

    It is written without BOM, whatever the characters in the URL, the
    key or the value are latin-1, outside latin-1 or outside the BMP.
    """
    monkeypatch.chdir(tmp_path)
    url = f'{URL_A}\u00e1'
    key = f'{SAMPLE_KEY}\u0398'
    value = f'{SAMPLE_VALUE}\U0001f600'

    gateway = SingleUrlGateway(url)
    gateway.save_metadata({url: {key: value}})

    assert gateway.sink_path.read_bytes().replace(b'\r\n', b'\n') == f'{url}\n\n[{key}] {value}\n'.encode()


# pylint: disable-next=unused-variable
def test_single_url_gateway_sink_ignores_results_for_other_urls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test that a single URL gateway only writes metadata for its URL.

    Metadata in the results for any other URL must be ignored.
    """
    monkeypatch.chdir(tmp_path)
    gateway = SingleUrlGateway(URL_A)

    gateway.save_metadata({
        URL_A: {SAMPLE_KEY: SAMPLE_VALUE},
        URL_C: {f'{SAMPLE_KEY}x': f'{SAMPLE_VALUE}x'},
    })

    assert gateway.sink_path.read_text(encoding='utf-8') == f'{URL_A}\n\n[{SAMPLE_KEY}] {SAMPLE_VALUE}\n'


# pylint: disable-next=unused-variable
def test_single_url_gateway_replaces_existing_sink(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that a single URL gateway replaces the sink file contents.

    No matter what the sink file contained, it should be replaced.
    """
    monkeypatch.chdir(tmp_path)
    gateway = SingleUrlGateway(URL_A)

    metadata = {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}}
    expected = f'{URL_A}\r\n\r\n[{SAMPLE_KEY}] {SAMPLE_VALUE}\r\n'

    gateway.sink_path.write_bytes(b'x' * len(expected.encode() * 2))

    gateway.save_metadata(metadata)

    assert gateway.sink_path.read_bytes() == expected.encode()


@pytest.mark.parametrize(('results', 'expected'), [
    pytest.param(
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        [f'[{SAMPLE_KEY}] {SAMPLE_VALUE}'],
        id='one_pair',
    ),
    pytest.param(
        {URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1', f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'}},
        [f'[{SAMPLE_KEY}1] {SAMPLE_VALUE}1', f'[{SAMPLE_KEY}2] {SAMPLE_VALUE}2'],
        id='pairs_in_given_order',
    ),
    pytest.param(
        {URL_A: {'k': f'{SAMPLE_VALUE}1', 'kkk': f'{SAMPLE_VALUE}2'}},
        [f'[k  ] {SAMPLE_VALUE}1', f'[kkk] {SAMPLE_VALUE}2'],
        id='keys_padded_to_the_longest',
    ),
    pytest.param(
        {URL_A: {SAMPLE_KEY: ''}},
        [f'[{SAMPLE_KEY}]'],
        id='empty_value',
    ),
    pytest.param(
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE} \t'}},
        [f'[{SAMPLE_KEY}] {SAMPLE_VALUE}'],
        id='trailing_whitespace_of_value_removed',
    ),
])
# pylint: disable-next=unused-variable
def test_single_url_gateway_console_output(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    results: SkimResults,
    expected: list[str],
) -> None:
    """Test that a single URL gateway logs properly.

    It should log each metadata pair with `logging.INFO` level, without
    trailing whitespace.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr(logger, 'indent', lambda: None)
    monkeypatch.setattr(logger, 'dedent', lambda: None)
    caplog.set_level(logging.INFO)
    gateway = SingleUrlGateway(URL_A)

    gateway.save_metadata(results)

    assert caplog.record_tuples == [(logger.name, logging.INFO, message) for message in expected]


@pytest.mark.parametrize(('results', 'expected'), [
    pytest.param(
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        ['indent', f'[{SAMPLE_KEY}] {SAMPLE_VALUE}', 'dedent'],
        id='one_pair',
    ),
    pytest.param(
        {URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1', f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'}},
        [
            'indent', f'[{SAMPLE_KEY}1] {SAMPLE_VALUE}1', 'dedent',
            'indent', f'[{SAMPLE_KEY}2] {SAMPLE_VALUE}2', 'dedent',
        ],
        id='several_pairs',
    ),
])
# pylint: disable-next=unused-variable
def test_single_url_gateway_console_indentation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    results: SkimResults,
    expected: list[str],
) -> None:
    """Test that a single URL gateway indents properly.

    It should indent each console line, while restoring the indentation
    afterwards.
    """
    events: list[str] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logger, 'indent', lambda: events.append('indent'))
    monkeypatch.setattr(logger, 'dedent', lambda: events.append('dedent'))
    monkeypatch.setattr(logger, 'info', events.append)
    gateway = SingleUrlGateway(URL_A)

    gateway.save_metadata(results)

    assert events == expected


@pytest.mark.parametrize('metadata', [
    pytest.param(
        {SAMPLE_KEY: SAMPLE_VALUE},
        id='one_pair',
    ),
    pytest.param(
        {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1', f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'},
        id='pairs_in_given_order',
    ),
    pytest.param(
        {SAMPLE_KEY: ''},
        id='empty_value',
    ),
    pytest.param(
        {SAMPLE_KEY: f' {SAMPLE_VALUE}1  {SAMPLE_VALUE}2 \t'},
        id='value_kept_verbatim',
    ),
])
# pylint: disable-next=unused-variable
def test_single_url_gateway_debug_messages(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    metadata: Metadata,
) -> None:
    """Test that a single URL gateway logs debug messages properly.

    It should trace the sink it dumps to, then each metadata pair, with
    `logging.DEBUG` level.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logger, 'propagate', True)
    monkeypatch.setattr(logger, 'indent', lambda: None)
    monkeypatch.setattr(logger, 'dedent', lambda: None)
    caplog.set_level(logging.DEBUG)
    gateway = SingleUrlGateway(URL_A)
    expected_messages = [
        Debug.DUMPING_METADATA_TO_SINK.format(gateway.sink_path),
        *(Debug.DUMPING_METADATA_K_V.format(key, value) for key, value in metadata.items()),
    ]

    gateway.save_metadata({URL_A: metadata})

    debug_records = [record for record in caplog.record_tuples if record[1] != logging.INFO]
    expected_records = [(logger.name, logging.DEBUG, message) for message in expected_messages]
    assert debug_records == expected_records


@pytest.mark.parametrize(('content', 'expected'), [
    pytest.param(
        f'{URL_A}'.encode(),
        [URL_A],
        id='one_url_without_final_newline',
    ),
    pytest.param(
        f'{URL_A}\n'.encode(),
        [URL_A],
        id='final_newline',
    ),
    pytest.param(
        f'{URL_C}\n{URL_A}\n{URL_B}\n'.encode(),
        [URL_C, URL_A, URL_B],
        id='urls_in_file_order',
    ),
    pytest.param(
        f'{URL_A}\r\n{URL_B}\r\n'.encode(),
        [URL_A, URL_B],
        id='crlf_line_endings',
    ),
    pytest.param(
        f'{URL_A}\r{URL_B}\r'.encode(),
        [URL_A, URL_B],
        id='cr_line_endings',
    ),
    pytest.param(
        f'{URL_A}\r\n{URL_B}\r{URL_C}\n'.encode(),
        [URL_A, URL_B, URL_C],
        id='mixed_line_endings',
    ),
    pytest.param(
        f'\n{URL_A}\n\n\n{URL_B}\n\n'.encode(),
        [URL_A, URL_B],
        id='blank_lines',
    ),
    pytest.param(
        f'{URL_A}\n \t \n{URL_B}\n'.encode(),
        [URL_A, URL_B],
        id='whitespace_only_lines',
    ),
    pytest.param(
        f'  {URL_A}\n'.encode(),
        [URL_A],
        id='leading_whitespace',
    ),
    pytest.param(
        f'{URL_A}  \t\n'.encode(),
        [URL_A],
        id='trailing_whitespace',
    ),
    pytest.param(
        f'{URL_A} {URL_B}\n'.encode(),
        [f'{URL_A} {URL_B}'],
        id='inner_whitespace_kept',
    ),
    pytest.param(
        b'\xef\xbb\xbf' + f'{URL_A}\n'.encode(),
        [URL_A],
        id='bom_removed',
    ),
    pytest.param(
        'xx://\u00e1\n'.encode(),
        ['xx://\u00e1'],
        id='non_ascii_kept',
    ),
    pytest.param(
        b'XX://A/b\n',
        ['XX://A/b'],
        id='case_kept',
    ),
    pytest.param(
        b'',
        [],
        id='empty_file',
    ),
    pytest.param(
        b'\n \n\t\n',
        [],
        id='only_blank_lines',
    ),
    # Current behavior, known limitation: Unicode line boundaries other
    # than the usual line endings also split lines.
    pytest.param(
        f'{URL_A}\u2028{URL_B}\n'.encode(),
        [URL_A, URL_B],
        id='unicode_line_separator',
    ),
])
# pylint: disable-next=unused-variable
def test_text_file_gateway_get_urls(tmp_path: Path, content: bytes, expected: list[Url]) -> None:
    """Test that a text file gateway reads URLs correctly.

    It should get one URL per non-blank line, in file order, stripped.
    """
    source_path = tmp_path / f'{SOURCE_STEM}.txt'
    source_path.write_bytes(content)
    gateway = TextFileGateway(str(source_path))

    assert gateway.get_urls() == expected


@pytest.mark.parametrize('content', [
    pytest.param(
        b'xx://\xe1\n',
        id='latin_1_character',
    ),
    pytest.param(
        b'xx://a\xc3',
        id='truncated_sequence',
    ),
])
# pylint: disable-next=unused-variable
def test_text_file_gateway_get_urls_not_utf_8(tmp_path: Path, content: bytes) -> None:
    """Test that a text file gateway raises for invalid UTF-8.

    It should raise a `GatewayError` for a file whose contents are not
    valid UTF-8.
    """
    source_path = tmp_path / f'{SOURCE_STEM}.txt'
    source_path.write_bytes(content)
    gateway = TextFileGateway(str(source_path))

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_INPUT_TEXT_FILE_NOT_UTF_8


@pytest.mark.parametrize('source_path', [
    pytest.param(
        f'{SOURCE_STEM}.txt',
        id='missing_file',
    ),
    pytest.param(
        f'dir/{SOURCE_STEM}.txt',
        id='missing_directory',
    ),
])
# pylint: disable-next=unused-variable
def test_text_file_gateway_get_urls_missing_file(tmp_path: Path, source_path: str) -> None:
    """Test that a text file gateway raises for missing source files.

    It should raise a `GatewayError` if its source file does not exist.
    """
    gateway = TextFileGateway(str(tmp_path / source_path))

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND


@pytest.mark.parametrize(('urls', 'results', 'expected'), [
    pytest.param(
        [URL_A],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}\n\n',
        id='one_pair',
    ),
    pytest.param(
        [URL_A],
        {URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1', f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'}},
        f'{URL_A}\n  {SAMPLE_KEY}1: {SAMPLE_VALUE}1\n  {SAMPLE_KEY}2: {SAMPLE_VALUE}2\n\n',
        id='pairs_in_given_order',
    ),
    pytest.param(
        [URL_A],
        {URL_A: {'k': f'{SAMPLE_VALUE}1', 'kkk': f'{SAMPLE_VALUE}2'}},
        f'{URL_A}\n  k: {SAMPLE_VALUE}1\n  kkk: {SAMPLE_VALUE}2\n\n',
        id='keys_not_padded',
    ),
    pytest.param(
        [URL_A],
        {URL_A: {SAMPLE_KEY: ''}},
        f'{URL_A}\n  {SAMPLE_KEY}: \n\n',
        id='empty_value',
    ),
    pytest.param(
        [URL_A],
        {URL_A: {'': SAMPLE_VALUE}},
        f'{URL_A}\n  : {SAMPLE_VALUE}\n\n',
        id='empty_key',
    ),
    pytest.param(
        [URL_A],
        {URL_A: {SAMPLE_KEY: f' {SAMPLE_VALUE}1  {SAMPLE_VALUE}2 / {SAMPLE_VALUE}3 \t'}},
        f'{URL_A}\n  {SAMPLE_KEY}:  {SAMPLE_VALUE}1  {SAMPLE_VALUE}2 / {SAMPLE_VALUE}3 \t\n\n',
        id='value_kept_verbatim',
    ),
    pytest.param(
        [URL_A, URL_B],
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'}, URL_B: {SAMPLE_KEY: f'{SAMPLE_VALUE}2'}},
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}1\n\n{URL_B}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}2\n\n',
        id='records_separated_by_an_empty_line',
    ),
])
# pylint: disable-next=unused-variable
def test_text_file_gateway_sink_text(tmp_path: Path, urls: list[Url], results: SkimResults, expected: str) -> None:
    """Test that a text file gateway writes output properly.

    It should print each record as its URL, its indented `key: value`
    lines and an empty line.
    """
    source_path = tmp_path / f'{SOURCE_STEM}.txt'
    source_path.write_bytes('\n'.join(urls).encode())
    gateway = TextFileGateway(str(source_path))

    gateway.save_metadata(results)

    assert gateway.sink_path.read_text(encoding='utf-8') == expected


@pytest.mark.parametrize(('source', 'results', 'expected'), [
    pytest.param(
        f'{URL_C}\n{URL_A}\n{URL_B}\n',
        {
            URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'},
            URL_B: {SAMPLE_KEY: f'{SAMPLE_VALUE}2'},
            URL_C: {SAMPLE_KEY: f'{SAMPLE_VALUE}3'},
        },
        f'{URL_C}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}3\n\n'
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}1\n\n'
        f'{URL_B}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}2\n\n',
        id='source_order_not_results_order',
    ),
    pytest.param(
        f'{URL_A}\n{URL_B}\n{URL_A}\n',
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'}, URL_B: {SAMPLE_KEY: f'{SAMPLE_VALUE}2'}},
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}1\n\n{URL_B}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}2\n\n',
        id='repeated_url_one_record',
    ),
    pytest.param(
        f'{URL_A}\n{URL_B}\n{URL_C}\n',
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'}, URL_B: {}, URL_C: {SAMPLE_KEY: f'{SAMPLE_VALUE}3'}},
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}1\n\n{URL_C}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}3\n\n',
        id='url_without_metadata_skipped',
    ),
    pytest.param(
        f'{URL_A}\n{URL_B}\n{URL_C}\n',
        {URL_B: {SAMPLE_KEY: f'{SAMPLE_VALUE}2'}},
        f'{URL_B}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}2\n\n',
        id='url_missing_from_results_skipped',
    ),
    pytest.param(
        f'{URL_A}\n',
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'}, URL_C: {SAMPLE_KEY: f'{SAMPLE_VALUE}3'}},
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}1\n\n',
        id='results_for_unknown_url_ignored',
    ),
    pytest.param(
        f'{URL_A}\n',
        {URL_A.swapcase(): {SAMPLE_KEY: f'{SAMPLE_VALUE}2'}, URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'}},
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}1\n\n',
        id='url_in_other_case',
    ),
    pytest.param(
        f'\n  {URL_A} \n\n{URL_B}\n',
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'}, URL_B: {SAMPLE_KEY: f'{SAMPLE_VALUE}2'}},
        f'{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}1\n\n{URL_B}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}2\n\n',
        id='urls_stripped_and_blank_lines_ignored',
    ),
])
# pylint: disable-next=unused-variable
def test_text_file_gateway_sink_records(tmp_path: Path, source: str, results: SkimResults, expected: str) -> None:
    """Test that a text file gateway writes one record per source URL.

    Records contain the obtained metadata, in order of first appearance.
    """
    source_path = tmp_path / f'{SOURCE_STEM}.txt'
    source_path.write_bytes(source.encode())
    gateway = TextFileGateway(str(source_path))

    gateway.save_metadata(results)

    assert gateway.sink_path.read_text(encoding='utf-8') == expected


@pytest.mark.parametrize(('url', 'results', 'expected'), [
    pytest.param(
        URL_A,
        {URL_A: {f'{SAMPLE_KEY}\u00e1': f'{SAMPLE_VALUE}\u00e1'}},
        f'{URL_A}\n  {SAMPLE_KEY}\u00e1: {SAMPLE_VALUE}\u00e1\n\n',
        id='latin_1_chars_in_metadata',
    ),
    pytest.param(
        URL_A,
        {URL_A: {SAMPLE_KEY: '\u0398'}},
        f'{URL_A}\n  {SAMPLE_KEY}: \u0398\n\n',
        id='character_outside_latin_1',
    ),
    pytest.param(
        URL_A,
        {URL_A: {SAMPLE_KEY: '\U0001f600'}},
        f'{URL_A}\n  {SAMPLE_KEY}: \U0001f600\n\n',
        id='character_outside_the_bmp',
    ),
    pytest.param(
        '\u00e1' + URL_A,
        {'\u00e1' + URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        f'\u00e1{URL_A}\n  {SAMPLE_KEY}: {SAMPLE_VALUE}\n\n',
        id='character_in_url',
    ),
])
# pylint: disable-next=unused-variable
def test_text_file_gateway_sink_encoding(tmp_path: Path, url: Url, results: SkimResults, expected: str) -> None:
    """Test that a text file gateway writes its sink as UTF-8.

    It is written without BOM, and any line ending is supported.
    """
    source_path = tmp_path / f'{SOURCE_STEM}.txt'
    source_path.write_bytes(f'{url}\n'.encode())
    gateway = TextFileGateway(str(source_path))

    gateway.save_metadata(results)

    assert gateway.sink_path.read_bytes().replace(b'\r\n', b'\n') == expected.encode('utf-8')


# pylint: disable-next=unused-variable
def test_text_file_gateway_replaces_existing_sink(tmp_path: Path) -> None:
    """Test that a text file gateway replaces sink file contents."""
    source_path = tmp_path / f'{SOURCE_STEM}.txt'
    source_path.write_bytes(f'{URL_A}\n'.encode())
    gateway = TextFileGateway(str(source_path))

    metadata = {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}}
    expected = f'{URL_A}\r\n  {SAMPLE_KEY}: {SAMPLE_VALUE}\r\n\r\n'

    gateway.sink_path.write_bytes(b'x' * len(expected.encode() * 2))
    gateway.save_metadata(metadata)

    assert gateway.sink_path.read_bytes() == expected.encode()


@pytest.mark.parametrize(('urls', 'results', 'expected'), [
    pytest.param(
        [URL_A],
        {URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1', f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'}},
        [(f'{SAMPLE_KEY}1', f'{SAMPLE_VALUE}1'), (f'{SAMPLE_KEY}2', f'{SAMPLE_VALUE}2')],
        id='pairs_in_given_order',
    ),
    pytest.param(
        [URL_A],
        {URL_A: {SAMPLE_KEY: f' {SAMPLE_VALUE}1  {SAMPLE_VALUE}2 / {SAMPLE_VALUE}3 \t'}},
        [(SAMPLE_KEY, f' {SAMPLE_VALUE}1  {SAMPLE_VALUE}2 / {SAMPLE_VALUE}3 \t')],
        id='value_kept_verbatim',
    ),
    pytest.param(
        [URL_C, URL_A],
        {URL_A: {f'{SAMPLE_KEY}1':  f'{SAMPLE_VALUE}1'}, URL_C: {f'{SAMPLE_KEY}2':  f'{SAMPLE_VALUE}2'}},
        [(f'{SAMPLE_KEY}2',  f'{SAMPLE_VALUE}2'), (f'{SAMPLE_KEY}1',  f'{SAMPLE_VALUE}1')],
        id='records_in_source_order',
    ),
])
# pylint: disable-next=unused-variable,too-many-arguments,too-many-positional-arguments
def test_text_file_gateway_debug_messages(  # ruff: ignore[PLR0913,PLR0917]
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    urls: list[Url],
    results: SkimResults,
    expected: list[tuple[str, str]],
) -> None:
    """Test that a text file gateway logs progress as it should.

    It should trace the sink it dumps to first, then each pair of each
    record in order.
    """
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)
    source_path = tmp_path / f'{SOURCE_STEM}.txt'
    source_path.write_bytes('\n'.join(urls).encode())
    gateway = TextFileGateway(str(source_path))
    expected_messages = [
        Debug.DUMPING_METADATA_TO_SINK.format(gateway.sink_path),
        *(Debug.DUMPING_METADATA_K_V.format(key, value) for key, value in expected),
    ]

    gateway.save_metadata(results)

    assert caplog.record_tuples == [(logger.name, logging.DEBUG, message) for message in expected_messages]


type SpreadSheetContents = list[list[object]]


def create_spreadsheet_gateway(
    path: Path,
    contents: list[SpreadSheetContents],
) -> SpreadSheetGateway:
    """Create a SpreadSheetGateway in *path*, containing *contents*.

    The *contents* are list of `SpreadSheetContents`, representing the
    contents for a single sheet. Each sheet contents is a list of rows,
    and each row is a list of `object`, corresponding to the cell values
    for that row, one per column.

    Finally, the active sheet of the workbook is set to the first sheet.
    """
    workbook = Workbook(write_only=True)
    for sheet_contents in contents:
        sheet = workbook.create_sheet()
        for row in sheet_contents:
            sheet.append(row)
    workbook.active = 0
    workbook.save(path)
    return SpreadSheetGateway(str(path))


@pytest.mark.parametrize(('contents', 'expected'), [
    pytest.param(
        [[URL_A]],
        [URL_A],
        id='one_url',
    ),
    pytest.param(
        [[URL_C], [URL_A], [URL_B]],
        [URL_C, URL_A, URL_B],
        id='urls_in_row_order',
    ),
    pytest.param(
        [[None, None, URL_A]],
        [URL_A],
        id='url_in_a_later_column',
    ),
    pytest.param(
        [[URL_A, URL_B]],
        [URL_A],
        id='first_url_of_the_row_only',
    ),
    pytest.param(
        [[SAMPLE_VALUE, URL_A]],
        [URL_A],
        id='text_before_the_url',
    ),
    pytest.param(
        [[1234, URL_A]],
        [URL_A],
        id='number_before_the_url',
    ),
    pytest.param(
        [[f'  {URL_A}  ']],
        [URL_A],
        id='url_stripped',
    ),
    pytest.param(
        [[URL_A], [], [None, None], [URL_B]],
        [URL_A, URL_B],
        id='empty_rows_skipped',
    ),
    pytest.param(
        [[SAMPLE_VALUE], [URL_A]],
        [URL_A],
        id='row_without_url_skipped',
    ),
    pytest.param(
        [[f'="{URL_A}"'], [URL_B]],
        [URL_B],
        id='formula_ignored',
    ),
    pytest.param(
        [],
        [],
        id='empty_sheet',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_get_urls(tmp_path: Path, contents: SpreadSheetContents, expected: list[Url]) -> None:
    """Test that a spreadsheet gateway reads URLs properly.

    It should read the first URL of each row of its sheet, stripped and
    return them in row order.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [contents])
    assert gateway.get_urls() == expected


@pytest.mark.parametrize(('contents', 'expected'), [
    pytest.param(
        [[[URL_A]], [[URL_B]], [[URL_C]]],
        [URL_A],
        id='other_sheets_ignored',
    ),
    pytest.param(
        [[], [[URL_A]]],
        [],
        id='empty_first_sheet',
    ),
    pytest.param(
        [[[SAMPLE_VALUE]], [[URL_A]]],
        [],
        id='first_sheet_without_urls',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_get_urls_sheets(
    tmp_path: Path,
    contents: list[SpreadSheetContents],
    expected: list[Url],
) -> None:
    """Test that a spreadsheet gateway reads only its first sheet."""
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', contents)
    assert gateway.get_urls() == expected


@pytest.mark.parametrize(('exception', 'expected'), [
    pytest.param(
        OSError(),
        Messages.GATEWAY_ERROR_INPUT_FILE_READ_FAILED,
        id='oserror_let_through',
    ),
    pytest.param(
        Exception(SAMPLE_MESSAGE),
        Messages.GATEWAY_ERROR_SOURCE_SHEET_IS_INVALID,
        id='any_other_error_wrapped',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_get_urls_load_errors(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected: str,
) -> None:
    """Test that a spreadsheet gateway handles exceptions properly.

    It should let `OSError` through and wrap any other exception raised
    when loading its workbook.
    """
    def mock_load_workbook(*_args: object, **_kwargs: object) -> NoReturn:
        raise exception

    monkeypatch.setattr('sacamantecas.load_workbook', mock_load_workbook)
    gateway = SpreadSheetGateway(SOURCE_LABEL)

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == expected


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_get_urls_without_worksheets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a workbook with no worksheets is considered invalid."""

    def mock_load_workbook(*_args: object, **_kwargs: object) -> Workbook:
        workbook = Workbook()
        workbook.remove(workbook.worksheets[0])
        return workbook

    monkeypatch.setattr('sacamantecas.load_workbook', mock_load_workbook)
    gateway = SpreadSheetGateway(SOURCE_LABEL)

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_NO_SHEETS_IN_SOURCE_WORKBOOK


@pytest.mark.parametrize('source_path', [
    pytest.param(
        f'missing_{SOURCE_STEM}.xlsx',
        id='missing_file',
    ),
    pytest.param(
        f'missing_directory/missing_{SOURCE_STEM}.xlsx',
        id='missing_directory',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_get_urls_missing_file(tmp_path: Path, source_path: str) -> None:
    """Test that a spreadsheet gateway raises for missing source files.

    It should raise a `GatewayError` if its source file does not exist.
    """
    gateway = SpreadSheetGateway(str(tmp_path / source_path))

    with pytest.raises(GatewayError) as excinfo:
        gateway.get_urls()

    assert str(excinfo.value) == Messages.GATEWAY_ERROR_INPUT_FILE_NOT_FOUND


@pytest.mark.parametrize('row_number', [
    pytest.param(
        None,
        id='missing-row-number',
    ),
    pytest.param(
        0,
        id='less-than-one-row-number',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_skips_rows_with_invalid_numbers(
    monkeypatch: pytest.MonkeyPatch,
    row_number: int | None,
) -> None:
    """Test that rows without a valid row number are skipped."""

    def mock_load_workbook(*_args: object, **_kwargs: object) -> Workbook:
        workbook = Workbook()
        cell = workbook.worksheets[0]['A1']
        cell.value = URL_A
        cell.row = row_number
        return workbook

    monkeypatch.setattr('sacamantecas.load_workbook', mock_load_workbook)
    gateway = SpreadSheetGateway(SOURCE_LABEL)

    assert not gateway.get_urls()
    assert not gateway.url_rows


@pytest.mark.parametrize(('contents', 'expected'), [
    pytest.param(
        [[[None], [None], [URL_A]]],
        [(URL_A, [3])],
        id='row_number_of_the_sheet',
    ),
    pytest.param(
        [[[URL_A], [URL_B], [URL_A]]],
        [(URL_A, [1, 3]), (URL_B, [2])],
        id='repeated_url_in_every_row',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_url_rows(
    tmp_path: Path,
    contents: list[SpreadSheetContents],
    expected: list[tuple[Url, list[int]]],
) -> None:
    """Test that a spreadsheet gateway records the URL rows.

    It should record the row of each URL, in order of first appearance.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', contents)
    gateway.get_urls()

    assert list(gateway.url_rows.items()) == expected


@pytest.mark.parametrize(('contents', 'ranges', 'expected'), [
    pytest.param(
        [[[URL_A], [URL_B]]],
        ['A1:B1'],
        [(URL_A, [1]), (URL_B, [2])],
        id='merged_across_columns',
    ),
    pytest.param(
        [[[URL_A], [None], [URL_B]]],
        ['A1:A2'],
        [(URL_A, [1]), (URL_B, [3])],
        id='merged_down_rows',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_url_rows_merged_ranges(
    tmp_path: Path,
    contents: list[SpreadSheetContents],
    ranges: list[str],
    expected: list[tuple[Url, list[int]]],
) -> None:
    """Test that a spreadsheet gateway handles merged ranges properly.

    It should record the URL rows of sheets with merged ranges so that
    merged ranges count only on the row of its first cell.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', contents)
    workbook = load_workbook(gateway.source_path)
    for merged_range in ranges:
        workbook.worksheets[0].merge_cells(merged_range)
    workbook.save(gateway.source_path)
    gateway.get_urls()

    assert list(gateway.url_rows.items()) == expected


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_save_uses_current_url_rows(tmp_path: Path) -> None:
    """Test that a spreadsheet gateway handles content-changing sources.

    When saving metadata, it should read the source spreadsheet again,
    and use the updated row positions.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A], [URL_B]]])
    gateway.get_urls()

    source_workbook = load_workbook(gateway.source_path)
    source_sheet = source_workbook.worksheets[0]
    source_sheet['A1'] = URL_B
    source_sheet['A2'] = URL_A
    source_workbook.save(gateway.source_path)
    source_workbook.close()

    gateway.save_metadata({
        URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}a'},
        URL_B: {SAMPLE_KEY: f'{SAMPLE_VALUE}b'},
    })

    sink_sheet = load_workbook(gateway.sink_path).worksheets[0]
    assert [
        (sink_sheet['A2'].value, sink_sheet['B2'].value),
        (sink_sheet['A3'].value, sink_sheet['B3'].value),
    ] == [
        (URL_B, f'{SAMPLE_VALUE}b'),
        (URL_A, f'{SAMPLE_VALUE}a'),
    ]


@pytest.mark.parametrize(('contents', 'results', 'expected'), [
    pytest.param(
        [[URL_A]],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        [
            [
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY),
            ],
            [
                URL_A,
                SAMPLE_VALUE,
            ],
        ],
        id='one_pair',
    ),
    pytest.param(
        [[URL_A]],
        {URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1', f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'}},
        [
            [
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(f'{SAMPLE_KEY}1'),
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(f'{SAMPLE_KEY}2'),
            ],
            [
                URL_A,
                f'{SAMPLE_VALUE}1',
                f'{SAMPLE_VALUE}2',
            ],
        ],
        id='two_keys_in_two_columns',
    ),
    pytest.param(
        [[URL_A, None, f'{SAMPLE_VALUE}x']],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        [
            [
                None,
                None,
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY),
            ],
            [
                URL_A,
                None,
                f'{SAMPLE_VALUE}x',
                SAMPLE_VALUE,
            ],
        ],
        id='columns_after_the_last_column',
    ),
    pytest.param(
        [[URL_A], [], [URL_A]],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        [
            [
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY),
            ],
            [
                URL_A,
                SAMPLE_VALUE,
            ],
            [
                None,
                None,
            ],
            [
                URL_A,
                SAMPLE_VALUE,
            ],
        ],
        id='repeated_url',
    ),
    pytest.param(
        [[URL_A], [URL_B]],
        {URL_A: {SAMPLE_KEY: f'{SAMPLE_VALUE}1'}, URL_B: {SAMPLE_KEY: f'{SAMPLE_VALUE}2'}},
        [
            [
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY),
            ],
            [
                URL_A,
                f'{SAMPLE_VALUE}1',
            ],
            [
                URL_B,
                f'{SAMPLE_VALUE}2',
            ],
        ],
        id='same_key_same_column',
    ),
    pytest.param(
        [[URL_A], [URL_B]],
        {
            URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1'},
            URL_B: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}2', f'{SAMPLE_KEY}x': f'{SAMPLE_VALUE}x'},
        },
        [
            [
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(f'{SAMPLE_KEY}1'),
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(f'{SAMPLE_KEY}x'),
            ],
            [
                URL_A,
                f'{SAMPLE_VALUE}1',
                None,
            ],
            [
                URL_B,
                f'{SAMPLE_VALUE}2',
                f'{SAMPLE_VALUE}x',
            ],
        ],
        id='new_key_in_a_later_url_new_column',
    ),
    pytest.param(
        [[URL_C], [URL_A]],
        {URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1'}, URL_C: {f'{SAMPLE_KEY}3': f'{SAMPLE_VALUE}3'}},
        [
            [
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(f'{SAMPLE_KEY}3'),
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(f'{SAMPLE_KEY}1'),
            ],
            [
                URL_C,
                f'{SAMPLE_VALUE}3',
                None,
            ],
            [
                URL_A,
                None,
                f'{SAMPLE_VALUE}1',
            ],
        ],
        id='columns_in_sheet_order',
    ),
    pytest.param(
        [[URL_A], [URL_B]],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        [
            [
                None,
                SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY),
            ],
            [
                URL_A,
                SAMPLE_VALUE,
            ],
            [
                URL_B,
                None,
            ],
        ],
        id='url_without_metadata_untouched',
    ),
    pytest.param(
        [[URL_A]],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}, URL_C: {f'{SAMPLE_KEY}3': f'{SAMPLE_VALUE}3'}},
        [[None, SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY)], [URL_A, SAMPLE_VALUE]],
        id='unknown_url_ignored',
    ),
    pytest.param(
        [[URL_A], [], [], [URL_B]],
        {URL_A: {SAMPLE_KEY: SAMPLE_VALUE}},
        [
            [None, SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY)],
            [URL_A, SAMPLE_VALUE],
            [None, None],
            [None, None],
            [URL_B, None],
        ],
        id='consecutive_empty_rows_kept',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_sink_columns(
    tmp_path: Path,
    contents: SpreadSheetContents,
    results: SkimResults,
    expected: SpreadSheetContents,
) -> None:
    """Test that a spreadsheet gateway adds a column per metadata key.

    It should add a proper header row and the metadata for each URL.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [contents])
    gateway.save_metadata(results)

    sink_sheet = load_workbook(gateway.sink_path).worksheets[0]
    sink_contents: SpreadSheetContents = [[cell.value for cell in row] for row in sink_sheet.iter_rows()]
    assert sink_contents == expected


@pytest.mark.parametrize('expected', [
    pytest.param(
        f'={SAMPLE_VALUE}',
        id='equals_sign',
    ),
    pytest.param(
        f'+{SAMPLE_VALUE}',
        id='plus_sign',
    ),
    pytest.param(
        f'-{SAMPLE_VALUE}',
        id='minus_sign',
    ),
    pytest.param(
        f'@{SAMPLE_VALUE}',
        id='at_sign',
    ),
    pytest.param(
        '#N/A',
        id='error_literal',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_sink_values_as_text(tmp_path: Path, expected: str) -> None:
    """Test that a spreadsheet gateway stores metadata as text.

    It should never be stored as a formula.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]]])
    gateway.save_metadata({URL_A: {SAMPLE_KEY: expected}})

    sink_cell = load_workbook(gateway.sink_path).worksheets[0]['B2']
    assert (sink_cell.value, sink_cell.data_type) == (expected, CELLTYPE_STRING)


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_added_columns_format(tmp_path: Path) -> None:
    """Test that a spreadsheet gateway formats added columns properly.

    It should give the cells a particular font, fill, and column width.
    """
    font = Font(name=SpreadSheetGateway.HEADER_FONT)
    fill = PatternFill(fgColor=SpreadSheetGateway.HEADER_COLOR, fill_type=SpreadSheetGateway.HEADER_FILL_TYPE)

    keys = [f'{SAMPLE_KEY}1', f'{SAMPLE_KEY}2', f'{SAMPLE_KEY}3', f'{SAMPLE_KEY}4']
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]]])
    gateway.save_metadata({URL_A: dict.fromkeys(keys, SAMPLE_VALUE)})

    sheet = load_workbook(gateway.sink_path).worksheets[0]
    assert sheet[1][0].font != font
    assert sheet[1][0].fill != fill
    assert [(cell.font, cell.fill) for cell in sheet[1][1:]] == [(font, fill)] * len(keys)

    assert sheet.column_dimensions.get('A') is None
    added_column_widths = [item.width for item in sheet.column_dimensions.values()]
    assert added_column_widths == [SpreadSheetGateway.HEADER_COLUMN_WIDTH] * len(keys)


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_added_column_does_not_extend_existing_dimension(tmp_path: Path) -> None:
    """Test that a new column does not inherit an oversized dimension.

    Some spreadsheets define the dimension of their last column with a
    `max` far beyond that column. The width given to a new column that
    reuses that dimension must not spread to the following columns.
    """
    last_excel_column = 16384
    source_path = tmp_path / f'{SOURCE_STEM}.xlsx'

    workbook = Workbook()
    sheet = workbook.worksheets[0]
    sheet['A1'] = URL_A
    oversized_dimension = sheet.column_dimensions['B']
    oversized_dimension.min = 2
    oversized_dimension.max = last_excel_column
    oversized_dimension.width = 10
    workbook.save(source_path)

    gateway = SpreadSheetGateway(str(source_path))
    gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    added_dimension = load_workbook(gateway.sink_path).worksheets[0].column_dimensions['B']
    assert (added_dimension.min, added_dimension.max) == (2, 2)
    assert added_dimension.width == SpreadSheetGateway.HEADER_COLUMN_WIDTH


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_save_changes_first_sheet_only(tmp_path: Path) -> None:
    """Test that only the first sheet gets modified.

    Only the first sheet should get a heading row and new columns, the
    rest of the sheets must be copied as they are, not shifted.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]], [[URL_B], [SAMPLE_VALUE]]])
    gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}, URL_B: {SAMPLE_KEY: SAMPLE_VALUE}})

    sink_workbook = load_workbook(gateway.sink_path)
    sheets_contents = [
        [[cell.value for cell in row] for row in sheet.iter_rows()]
        for sheet in sink_workbook.worksheets
    ]
    assert sheets_contents == [
        [[None, SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(SAMPLE_KEY)], [URL_A, SAMPLE_VALUE]],
        [[URL_B], [SAMPLE_VALUE]],
    ]


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_save_replaces_existing_sink(tmp_path: Path) -> None:
    """Test that a spreadsheet gateway replaces an existing sink.

    The sink of a previous run must not accumulate columns, or heading
    rows, it must be rebuilt from the source.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]]])
    gateway.save_metadata({URL_A: {f'{SAMPLE_KEY}1': f'{SAMPLE_VALUE}1'}})
    gateway.save_metadata({URL_A: {f'{SAMPLE_KEY}2': f'{SAMPLE_VALUE}2'}})

    sink_sheet = load_workbook(gateway.sink_path).worksheets[0]
    sink_contents: SpreadSheetContents = [[cell.value for cell in row] for row in sink_sheet.iter_rows()]
    assert sink_contents == [
        [None, SpreadSheetGateway.ADDED_METADATA_COLUMN_HEADER.format(f'{SAMPLE_KEY}2')],
        [URL_A, f'{SAMPLE_VALUE}2'],
    ]


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_save_leaves_source_untouched(tmp_path: Path) -> None:
    """Test that saving metadata does not modify the source spreadsheet.

    The metadata goes to a copy, the sink, so the source file must stay
    byte for byte as it was.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A], [URL_B]]])
    source_bytes_before_saving = gateway.source_path.read_bytes()

    gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert gateway.source_path.read_bytes() == source_bytes_before_saving


@pytest.mark.parametrize(('exception', 'expected'), [
    pytest.param(
        PermissionError(),
        Messages.GATEWAY_ERROR_OUTPUT_FILE_NO_PERMISSION,
        id='permission_error',
    ),
    pytest.param(
        OSError(),
        Messages.GATEWAY_ERROR_OUTPUT_FILE_WRITE_FAILED,
        id='other_os_error',
    ),
])
# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_save_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception: OSError,
    expected: str,
) -> None:
    """Test that workbook save errors are translated by the gateway."""
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]]])

    def mock_save(*_args: object, **_kwargs: object) -> NoReturn:
        raise exception

    monkeypatch.setattr(Workbook, 'save', mock_save)

    with pytest.raises(GatewayError) as excinfo:
        gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert str(excinfo.value) == expected


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_workbook_warnings(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a spreadsheet gateway logs `openpyxl` warnings."""

    def mock_load_workbook(*_args: object, **_kwargs: object) -> Workbook:
        for _ in range(2):
            warnings.warn(f'{SAMPLE_MESSAGE}U', UserWarning, stacklevel=2)
        warnings.warn(f'{SAMPLE_MESSAGE}D', DeprecationWarning, stacklevel=2)
        return Workbook()

    monkeypatch.setattr('sacamantecas.load_workbook', mock_load_workbook)
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)

    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]]])
    gateway.get_urls()

    assert all(record.name == logger.name for record in caplog.records)
    assert all(record.levelno == logging.DEBUG for record in caplog.records)
    assert [record.message for record in caplog.records if str(gateway.source_path) in record.message] == [
        Debug.WORKBOOK_WARNING.format('UserWarning', gateway.source_path, f'{SAMPLE_MESSAGE}U'),
        Debug.WORKBOOK_WARNING.format('UserWarning', gateway.source_path, f'{SAMPLE_MESSAGE}U'),
        Debug.WORKBOOK_WARNING.format('DeprecationWarning', gateway.source_path, f'{SAMPLE_MESSAGE}D'),
    ]


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_workbook_warnings_before_load_failure(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that `openpyxl` warnings are logged even on load failure."""

    def mock_load_workbook(*_args: object, **_kwargs: object) -> NoReturn:
        warnings.warn(SAMPLE_MESSAGE, UserWarning, stacklevel=2)
        raise ValueError(SAMPLE_MESSAGE)

    monkeypatch.setattr('sacamantecas.load_workbook', mock_load_workbook)
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)
    gateway = SpreadSheetGateway(SOURCE_LABEL)

    with pytest.raises(GatewayError):
        gateway.get_urls()

    assert Debug.WORKBOOK_WARNING.format('UserWarning', gateway.source_path, SAMPLE_MESSAGE) in caplog.messages


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_workbook_warnings_when_saving(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that `openpyxl` warnings at sink loading time are logged."""

    def mock_load_workbook(workbook_path: Path) -> Workbook:
        if workbook_path == gateway.sink_path:
            warnings.warn(SAMPLE_MESSAGE, UserWarning, stacklevel=2)
        return real_load_workbook(workbook_path)

    real_load_workbook = load_workbook
    monkeypatch.setattr('sacamantecas.load_workbook', mock_load_workbook)
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)

    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]]])
    gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    assert Debug.WORKBOOK_WARNING.format('UserWarning', gateway.sink_path, SAMPLE_MESSAGE) in caplog.messages


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_get_urls_debug_messages(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a spreadsheet gateway traces how it reads its source.

    It should trace the sheet, then each row, then the cells ignored
    for not being text and the cell where a URL is found.
    """
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)

    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[1234, URL_A], [SAMPLE_VALUE, None]]])

    sheet_title = load_workbook(gateway.source_path).worksheets[0].title
    expected_messages = [
        Debug.WORKING_SHEET.format(sheet_title),
        Debug.PROCESSING_ROW.format(1),
        Debug.NONSTRING_CELL.format('A1'),
        Debug.URL_FOUND_IN_CELL.format('B1', URL_A),
        Debug.PROCESSING_ROW.format(2),
        Debug.NONSTRING_CELL.format('B2'),
    ]

    gateway.get_urls()

    assert caplog.messages == expected_messages


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_save_metadata_debug_messages(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a spreadsheet gateway traces how it writes its sink.

    After the traces from reading the source again, it should trace the
    copy, the heading row, and each metadata pair. New keys are traced
    only the first time, even if their URL is repeated.
    """
    monkeypatch.setattr(logger, 'propagate', True)
    caplog.set_level(logging.DEBUG)

    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A], [URL_A]]])
    gateway.get_urls()
    reading_messages = list(caplog.messages)

    caplog.clear()

    first_key, second_key = f'{SAMPLE_KEY}1', f'{SAMPLE_KEY}2'
    first_value, second_value = f'{SAMPLE_VALUE}1', f'{SAMPLE_VALUE}2'

    expected_messages = [
        *reading_messages,
        Debug.COPYING_WORKBOOK.format(gateway.sink_path),
        Debug.INSERTING_HEADING_ROW,
        Debug.NEW_METADATA_FOUND.format(first_key),
        Debug.METADATA_STORED_IN_COLUMN.format(first_key, 'B'),
        Debug.DUMPING_METADATA_K_V.format(first_key, first_value),
        Debug.NEW_METADATA_FOUND.format(second_key),
        Debug.METADATA_STORED_IN_COLUMN.format(second_key, 'C'),
        Debug.DUMPING_METADATA_K_V.format(second_key, second_value),
        Debug.DUMPING_METADATA_K_V.format(first_key, first_value),
        Debug.DUMPING_METADATA_K_V.format(second_key, second_value),
    ]

    gateway.save_metadata({URL_A: {first_key: first_value, second_key: second_value}})

    assert caplog.messages == expected_messages


# pylint: disable-next=unused-variable
def test_spreadsheet_gateway_releases_files(tmp_path: Path) -> None:
    """Test that a spreadsheet gateway does not keep files open.

    On Windows, a file with an open handle cannot be deleted.
    """
    gateway = create_spreadsheet_gateway(tmp_path / f'{SOURCE_STEM}.xlsx', [[[URL_A]]])
    gateway.save_metadata({URL_A: {SAMPLE_KEY: SAMPLE_VALUE}})

    gateway.source_path.unlink()
    gateway.sink_path.unlink()

    assert not gateway.source_path.exists()
    assert not gateway.sink_path.exists()
