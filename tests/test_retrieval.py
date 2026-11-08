"""Test suite for URL retrieval area."""

import errno
from http.client import BadStatusLine, HTTPMessage, IncompleteRead, RemoteDisconnected
import socket
import ssl
import sys
from typing import Self, TYPE_CHECKING
from urllib.error import HTTPError, URLError

import pytest

from sacamantecas import (
    CharsetError,
    detect_html_charset,
    get_redirected_url,
    Messages,
    resolve_file_url,
    retrieval_error_message,
    retrieve_url,
    Settings,
    TooManyRedirectionsError,
    Url,
)
from sacamantecas.about import USER_AGENT

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from urllib.request import Request

FALLBACK_CHARSET = 'ISO-8859-1'
PRESCAN_SIZE = 1024
PRESCAN_LIMIT_TEST_TAG = b'<meta charset="charset">'


@pytest.mark.parametrize(('contents', 'expected'), [
    # Declarations through the `content` attribute.
    pytest.param(
        b'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">',
        'utf-8',
        id='http_equiv',
    ),
    pytest.param(
        b"<meta http-equiv='Content-Type' content='text/html; charset=utf-8'>",
        'utf-8',
        id='http_equiv_single_quotes',
    ),
    pytest.param(
        b'<meta content="text/html; charset=utf-8" http-equiv="Content-Type">',
        'utf-8',
        id='http_equiv_swapped_order',
    ),
    # Declarations through the `charset` attribute.
    pytest.param(
        b'<meta charset="iso-8859-1">',
        'iso-8859-1',
        id='meta_charset',
    ),
    pytest.param(
        b"<meta charset='iso-8859-1'>",
        'iso-8859-1',
        id='meta_charset_single_quotes',
    ),
    pytest.param(
        b'<meta charset=iso-8859-1>',
        'iso-8859-1',
        id='meta_charset_unquoted',
    ),
    pytest.param(
        b'<meta charset=utf-8/>',
        'utf-8',
        id='meta_charset_self_closed',
    ),
    pytest.param(
        b'<meta name="x" charset="utf-8">',
        'utf-8',
        id='extra_attribute_first',
    ),
    pytest.param(
        b'<meta charset = "utf-8">',
        'utf-8',
        id='spaces_around_equals',
    ),
    pytest.param(
        b'<META CHARSET="UTF-8">',
        'UTF-8',
        id='uppercase',
    ),
    pytest.param(
        b'<meta\n  http-equiv="Content-Type"\n  content="text/html;\n  charset=utf-8">',
        'utf-8',
        id='multiline',
    ),
    # Which declaration wins.
    pytest.param(
        b'<meta name="viewport" content="width=device-width"><meta charset="cp850">',
        'cp850',
        id='unrelated_meta_first',
    ),
    pytest.param(
        b'<meta charset="cp850"><meta http-equiv="Content-Type" content="text/html; charset=cp1252">',
        'cp850',
        id='charset_first',
    ),
    pytest.param(
        b'<meta http-equiv="Content-Type" content="text/html; charset=cp1252"><meta charset="cp850">',
        'cp1252',
        id='http_equiv_first',
    ),
    # Nothing to detect.
    pytest.param(
        b'',
        FALLBACK_CHARSET,
        id='empty',
    ),
    pytest.param(
        b'<html><head><title>Title</title></head></html>',
        FALLBACK_CHARSET,
        id='no_meta',
    ),
    pytest.param(
        b'<meta name="viewport" content="width=device-width">',
        FALLBACK_CHARSET,
        id='meta_without_charset',
    ),
    pytest.param(
        b'<p>charset=utf-8</p>',
        FALLBACK_CHARSET,
        id='charset_outside_meta',
    ),
    # The prescan limit.
    pytest.param(
        b' ' * (PRESCAN_SIZE - len(PRESCAN_LIMIT_TEST_TAG)) + PRESCAN_LIMIT_TEST_TAG,
        'charset',
        id='ends_at_limit',
    ),
    pytest.param(
        b' ' * (PRESCAN_SIZE - len(PRESCAN_LIMIT_TEST_TAG) + 1) + PRESCAN_LIMIT_TEST_TAG,
        FALLBACK_CHARSET,
        id='straddles_limit',
    ),
    pytest.param(
        b' ' * PRESCAN_SIZE + PRESCAN_LIMIT_TEST_TAG,
        FALLBACK_CHARSET,
        id='after_limit',
    ),
])
# pylint: disable-next=unused-variable
def test_detect_html_charset(contents: bytes, expected: str) -> None:
    """Test `detect_html_charset()`."""
    assert detect_html_charset(contents) == expected


SAMPLE_URL = 'http://example.com/dir/page.html'
TARGET_URL = 'http://example.com/new'


@pytest.mark.parametrize(('contents', 'expected'), [
    # Forms of the declaration.
    pytest.param(
        f'<meta http-equiv="refresh" content="0; URL={TARGET_URL}">',
        TARGET_URL,
        id='canonical',
    ),
    pytest.param(
        f'<meta http-equiv="refresh" content="0; url={TARGET_URL}">',
        TARGET_URL,
        id='lowercase_url',
    ),
    pytest.param(
        f'<meta http-equiv="Refresh" content="0; URL={TARGET_URL}">',
        TARGET_URL,
        id='mixed_case_refresh',
    ),
    pytest.param(
        f'<META HTTP-EQUIV="REFRESH" CONTENT="0; URL={TARGET_URL}">',
        TARGET_URL,
        id='uppercase_tag',
    ),
    pytest.param(
        f'<meta http-equiv="refresh" content="0;URL={TARGET_URL}">',
        TARGET_URL,
        id='no_space_after_semicolon',
    ),
    pytest.param(
        f'<meta http-equiv="refresh" content="0, URL={TARGET_URL}">',
        TARGET_URL,
        id='comma_separator',
    ),
    pytest.param(
        f'<meta http-equiv="refresh" content="URL={TARGET_URL}">',
        TARGET_URL,
        id='no_time',
    ),
    pytest.param(
        f'<meta http-equiv="refresh" content="0; URL=\'{TARGET_URL}\'">',
        TARGET_URL,
        id='quoted_target',
    ),
    pytest.param(
        f"<meta http-equiv='refresh' content='0; URL={TARGET_URL}'>",
        TARGET_URL,
        id='single_quote_attributes',
    ),
    pytest.param(
        f'<meta content="0; URL={TARGET_URL}" http-equiv="refresh">',
        TARGET_URL,
        id='swapped_attribute_order',
    ),
    pytest.param(
        f'<meta http-equiv="refresh" id="x" content="0; URL={TARGET_URL}">',
        TARGET_URL,
        id='extra_attribute_between',
    ),
    pytest.param(
        f'<meta\n  http-equiv="refresh"\n  content="0;\n  URL={TARGET_URL}">',
        TARGET_URL,
        id='multiline',
    ),
    # The target itself.
    pytest.param(
        f'<meta http-equiv="refresh" content="0; URL={TARGET_URL}?a=1&amp;b=2">',
        f'{TARGET_URL}?a=1&b=2',
        id='entity_in_query',
    ),
    pytest.param(
        '<meta http-equiv="refresh" content="0; URL=http://example.com:8080/new?x=1">',
        'http://example.com:8080/new?x=1',
        id='port_and_query',
    ),
    # Which declaration wins.
    pytest.param(
        f'<meta charset="utf-8"><meta http-equiv="refresh" content="0; URL={TARGET_URL}">',
        TARGET_URL,
        id='unrelated_meta_first',
    ),
    pytest.param(
        f'<meta http-equiv="refresh" content="0; URL={TARGET_URL}/first">'
        f'<meta http-equiv="refresh" content="0; URL={TARGET_URL}/second">',
        f'{TARGET_URL}/first',
        id='first_refresh_wins',
    ),
    pytest.param(
        '<meta http-equiv="refresh" content="30">'
        f'<meta http-equiv="refresh" content="0; URL={TARGET_URL}">',
        TARGET_URL,
        id='refresh_without_url_skipped',
    ),
    # No redirection.
    pytest.param(
        '',
        None,
        id='empty',
    ),
    pytest.param(
        '<html><head><title>Title</title></head></html>',
        None,
        id='no_meta',
    ),
    pytest.param(
        '<meta http-equiv="refresh" content="30">',
        None,
        id='refresh_without_url',
    ),
    pytest.param(
        f'<meta http-equiv="content-type" content="text/html; url={TARGET_URL}">',
        None,
        id='other_http_equiv',
    ),
    pytest.param(
        f'<p>refresh url={TARGET_URL}</p>',
        None,
        id='url_outside_meta',
    ),
])
# pylint: disable-next=unused-variable
def test_get_redirected_url(contents: str, expected: Url | None) -> None:
    """Test `get_redirected_url()` detection of redirections."""
    assert get_redirected_url(contents.encode('ascii'), SAMPLE_URL) == expected


@pytest.mark.parametrize(('base_url', 'target', 'expected'), [
    pytest.param(
        SAMPLE_URL,
        'other.html',
        'http://example.com/dir/other.html',
        id='relative_path',
    ),
    pytest.param(
        SAMPLE_URL,
        '/root.html',
        'http://example.com/root.html',
        id='absolute_path',
    ),
    pytest.param(
        SAMPLE_URL,
        '../up.html',
        'http://example.com/up.html',
        id='parent_path',
    ),
    pytest.param(
        SAMPLE_URL,
        '?page=2',
        'http://example.com/dir/page.html?page=2',
        id='query_only',
    ),
    pytest.param(
        SAMPLE_URL,
        '//other.example.org/new',
        'http://other.example.org/new',
        id='scheme_relative',
    ),
    pytest.param(
        SAMPLE_URL,
        'https://other.example.org/new',
        'https://other.example.org/new',
        id='absolute_url',
    ),
    pytest.param(
        'http://example.com/dir/page.html?x=1',
        'other.html',
        'http://example.com/dir/other.html',
        id='base_with_query',
    ),
    pytest.param(
        'file:///C:/dir/page.html',
        'other.html',
        'file:///C:/dir/other.html',
        id='file_base',
    ),
])
# pylint: disable-next=unused-variable
def test_get_redirected_url_resolves_target(base_url: Url, target: str, expected: Url) -> None:
    """Test `get_redirected_url()` resolves the target against the base URL."""
    contents = f'<meta http-equiv="refresh" content="0; URL={target}">'.encode('ascii')
    assert get_redirected_url(contents, base_url) == expected


@pytest.fixture(name='working_directory')
# pylint: disable-next=unused-variable
def working_directory_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Make a temporary directory the current working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path.resolve()


@pytest.mark.parametrize(('url', 'expected'), [
    # Absolute paths, with a drive.
    pytest.param(
        'file:///C:/dir/file.txt',
        'file:///C:/dir/file.txt',
        id='absolute',
    ),
    pytest.param(
        'file:///C:/dir/../file.txt',
        'file:///C:/file.txt',
        id='absolute_parent_segment',
    ),
    pytest.param(
        'file:///C:/dir/./file.txt',
        'file:///C:/dir/file.txt',
        id='absolute_current_segment',
    ),
    pytest.param(
        'file:///C:\\dir\\file.txt',
        'file:///C:/dir/file.txt',
        id='absolute_backslashes',
    ),
    pytest.param(
        'file:///C:/dir/',
        'file:///C:/dir',
        id='absolute_trailing_slash',
    ),
    pytest.param(
        'file:///C:/',
        'file:///C:/',
        id='absolute_drive_root',
    ),
    pytest.param(
        'file:///C:/a%20file%20%C3%B1.txt',
        'file:///C:/a%20file%20%C3%B1.txt',
        id='absolute_encoded_chars',
    ),
    pytest.param(  # '%25' is '%' itself, do NOT CHANGE!
        'file:///C:/42%25.txt',
        'file:///C:/42%25.txt',
        id='absolute_percent_sign',
    ),
    pytest.param(
        'file:///C:/42%42.txt',
        'file:///C:/42B.txt',
        id='absolute_percent_decoded',
    ),
    pytest.param(
        'file:///C:/a file.txt',
        'file:///C:/a%20file.txt',
        id='absolute_raw_space',
    ),
    pytest.param(
        'file:///C:/a(b)+c,d@e.txt',
        'file:///C:/a%28b%29%2Bc%2Cd%40e.txt',
        id='absolute_reencoded_chars',
    ),
    # Relative paths: the first slash is not a root.
    pytest.param(
        'file:///dir/file.txt',
        '{cwd}/dir/file.txt',
        id='relative',
    ),
    pytest.param(
        'file:///file.txt',
        '{cwd}/file.txt',
        id='relative_no_directory',
    ),
    pytest.param(
        'file:relative.txt',
        '{cwd}/relative.txt',
        id='relative_no_slashes',
    ),
    pytest.param(
        'file:///./file.txt',
        '{cwd}/file.txt',
        id='relative_current_segment',
    ),
    pytest.param(
        'file:///dir/../file.txt',
        '{cwd}/file.txt',
        id='relative_inner_parent_segment',
    ),
    pytest.param(
        'file:///../file.txt',
        '{parent}/file.txt',
        id='relative_parent_directory',
    ),
    pytest.param(
        'file:///dir\\file.txt',
        '{cwd}/dir/file.txt',
        id='relative_backslashes',
    ),
    pytest.param(
        'file:///a%20dir/n%C3%B1.txt',
        '{cwd}/a%20dir/n%C3%B1.txt',
        id='relative_encoded_chars',
    ),
    # Hosts which are not network locations.
    pytest.param(
        'file://localhost/C:/dir/file.txt',
        'file:///C:/dir/file.txt',
        id='localhost',
    ),
    pytest.param(
        'file://LOCALHOST/C:/dir/file.txt',
        'file:///C:/dir/file.txt',
        id='localhost_uppercase',
    ),
    pytest.param(
        'file://localhost/dir/file.txt',
        '{cwd}/dir/file.txt',
        id='localhost_relative',
    ),
    pytest.param(
        'file://C:/dir/file.txt',
        'file:///C:/dir/file.txt',
        id='drive_as_host',
    ),
    pytest.param(
        'file://C:\\dir\\file.txt',
        'file:///C:/dir/file.txt',
        id='drive_as_host_backslashes',
    ),
    pytest.param(
        'file://C:/',
        'file:///C:/',
        id='drive_as_host_root',
    ),
    # UNC paths: absolute, not resolved.
    pytest.param(
        'file://server/share/file.txt',
        'file:////server/share/file.txt',
        id='unc',
    ),
    pytest.param(
        'file:////server/share/file.txt',
        'file:////server/share/file.txt',
        id='unc_four_slashes',
    ),
    pytest.param(
        'file://SERVER/share/file.txt',
        'file:////SERVER/share/file.txt',
        id='unc_host_case_preserved',
    ),
    pytest.param(
        'file://server/share/../file.txt',
        'file:////server/share/../file.txt',
        id='unc_not_resolved',
    ),
    pytest.param(
        'file://server/a%20share/n%C3%B1.txt',
        'file:////server/a%20share/n%C3%B1.txt',
        id='unc_encoded_chars',
    ),
    pytest.param(
        'file://127.0.0.1/c$/dir/file.txt',
        'file:////127.0.0.1/c%24/dir/file.txt',
        id='unc_admin_share',
    ),
    # Query and fragment are kept.
    pytest.param(
        'file:///C:/dir/file.txt?query=42#fragment',
        'file:///C:/dir/file.txt?query=42#fragment',
        id='query_and_fragment',
    ),
    # Empty paths resolve to the working directory.
    pytest.param(
        'file://',
        '{cwd}',
        id='empty_path',
    ),
    pytest.param(
        'file:///',
        '{cwd}',
        id='slash_only',
    ),
    pytest.param(
        'file://localhost',
        '{cwd}',
        id='localhost_empty_path',
    ),
])
# pylint: disable-next=unused-variable
def test_resolve_file_url(working_directory: Path, url: Url, expected: Url) -> None:
    """Test `resolve_file_url()`."""
    expected_url = expected.format(cwd=working_directory.as_uri(), parent=working_directory.parent.as_uri())
    assert resolve_file_url(url) == expected_url


@pytest.mark.usefixtures('working_directory')
@pytest.mark.parametrize('url', [
    pytest.param(
        'file:///C:/dir/file.txt',
        id='absolute',
    ),
    pytest.param(
        'file:///dir/../file.txt',
        id='relative',
    ),
    pytest.param(
        'file://C:/dir/file.txt',
        id='drive_as_host',
    ),
    pytest.param(
        'file://localhost/C:/dir/file.txt',
        id='localhost',
    ),
    pytest.param(
        'file://server/share/file.txt',
        id='unc',
    ),
    pytest.param(
        'file:///a file n%C3%B1.txt',
        id='encoded_chars',
    ),
])
# pylint: disable-next=unused-variable
def test_resolve_file_url_is_idempotent(url: Url) -> None:
    """Test `resolve_file_url()` leaves already resolved URLs alone."""
    resolved_url = resolve_file_url(url)
    assert resolve_file_url(resolved_url) == resolved_url


EXCEPTION_MESSAGE = 'Text of the exception, which must never reach the user!'


def http_error(code: int) -> HTTPError:
    """Return an `HTTPError` with status *code*."""
    return HTTPError('http://example.com', code, EXCEPTION_MESSAGE, HTTPMessage(), None)


def url_access_message(reason: str) -> str:
    """Return the URL access error message for *reason*."""
    return Messages.SKIMMING_ERROR_URL_ACCESS.format(reason)


@pytest.mark.parametrize(('exception', 'expected'), [
    # `HTTPError` is also a `URLError` and an `OSError`, but it wins.
    pytest.param(
        http_error(404),
        url_access_message(Messages.URL_ACCESS_REASON_HTTP_ERROR.format(404)),
        id='http_error_404',
    ),
    # `URLError` wrapping other exceptions.
    # A timeout is also an `OSError`, but it wins.
    pytest.param(
        URLError(TimeoutError()),
        Messages.SKIMMING_ERROR_TIMEOUT,
        id='urlerror_timeout',
    ),
    pytest.param(
        URLError(FileNotFoundError()),
        url_access_message(Messages.URL_ACCESS_REASON_OSLIKE_ERROR.format('FileNotFoundError')),
        id='urlerror_file_not_found',
    ),
    pytest.param(
        URLError(socket.gaierror(11001, 'getaddrinfo failed')),
        url_access_message(Messages.URL_ACCESS_REASON_OSLIKE_ERROR.format('gaierror')),
        id='urlerror_name_resolution',
    ),
    pytest.param(
        URLError(ssl.SSLCertVerificationError()),
        url_access_message(Messages.URL_ACCESS_REASON_OSLIKE_ERROR.format('SSLCertVerificationError')),
        id='urlerror_certificate',
    ),
    # A connection error inside a `URLError` is reported with its class
    # name, it does not take the errno path.
    pytest.param(
        URLError(ConnectionResetError(errno.ECONNRESET, EXCEPTION_MESSAGE)),
        url_access_message(Messages.URL_ACCESS_REASON_OSLIKE_ERROR.format('ConnectionResetError')),
        id='urlerror_connection_reset',
    ),
    pytest.param(
        URLError(EXCEPTION_MESSAGE),
        url_access_message(Messages.URL_ACCESS_REASON_UNEXPECTED_ERROR),
        id='urlerror_text_reason',
    ),
    # Connection errors which are not wrapped.
    pytest.param(
        ConnectionResetError(errno.ECONNRESET, EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED.format(errno.errorcode[errno.ECONNRESET]),
        id='connection_reset',
    ),
    pytest.param(
        ConnectionRefusedError(errno.ECONNREFUSED, EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED.format(errno.errorcode[errno.ECONNREFUSED]),
        id='connection_refused',
    ),
    pytest.param(
        ConnectionError(99999, EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED_UNKNOWN_REASON,
        id='connection_unknown_errno',
    ),
    pytest.param(
        ConnectionError(EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED_UNKNOWN_REASON,
        id='connection_no_errno',
    ),
    # `RemoteDisconnected` is also an `HTTPException`,
    # but the connection error case goes first.
    pytest.param(
        RemoteDisconnected(EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED_UNKNOWN_REASON,
        id='remote_disconnected',
    ),
    # Other HTTP protocol exceptions.
    pytest.param(
        IncompleteRead(EXCEPTION_MESSAGE.encode()),
        Messages.SKIMMING_ERROR_ERROR_HTTP_RETRIEVAL.format('IncompleteRead'),
        id='incomplete_read',
    ),
    pytest.param(
        BadStatusLine(EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_ERROR_HTTP_RETRIEVAL.format('BadStatusLine'),
        id='bad_status_line',
    ),
    # Timeouts and any other `OSError`.
    # A certificate error is also a `ValueError`, but `OSError` wins.
    pytest.param(
        TimeoutError(),
        Messages.SKIMMING_ERROR_TIMEOUT,
        id='timeout',
    ),
    pytest.param(
        OSError(EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED.format('OSError'),
        id='os_error',
    ),
    pytest.param(
        ssl.SSLCertVerificationError(),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED.format('SSLCertVerificationError'),
        id='certificate_error',
    ),
    pytest.param(
        ssl.SSLError(EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED.format('SSLError'),
        id='ssl_error',
    ),
    pytest.param(
        ssl.SSLEOFError(),
        Messages.SKIMMING_ERROR_CONNECTION_FAILED.format('SSLEOFError'),
        id='ssl_eof_error',
    ),
    # The program own exceptions.
    pytest.param(
        TooManyRedirectionsError(42),
        Messages.SKIMMING_ERROR_TOO_MANY_REDIRECTIONS.format(42),
        id='too_many_redirections',
    ),
    pytest.param(
        CharsetError(''),
        Messages.SKIMMING_ERROR_EMPTY_CHARSET,
        id='empty_charset',
    ),
    pytest.param(
        CharsetError('42'),
        Messages.SKIMMING_ERROR_UNKNOWN_CHARSET.format('42'),
        id='unknown_charset',
    ),
    # Decoding and invalid URLs.
    # `UnicodeDecodeError` is a `ValueError`, but it wins.
    pytest.param(
        UnicodeDecodeError('utf-8', b'\xff', 0, 1, EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_UNDECODABLE_CONTENTS.format('utf-8'),
        id='undecodable_contents',
    ),
    pytest.param(
        ValueError(EXCEPTION_MESSAGE),
        Messages.SKIMMING_ERROR_INVALID_URL,
        id='invalid_url',
    ),
    # No message: the caller lets these propagate.
    pytest.param(
        RuntimeError(EXCEPTION_MESSAGE),
        None,
        id='runtime_error',
    ),
    pytest.param(
        # Needed to check the parent of `CharsetError` is not caught.
        LookupError(EXCEPTION_MESSAGE),
        None,
        id='lookup_error',
    ),
])
# pylint: disable-next=unused-variable
def test_retrieval_error_message(exception: Exception, expected: str | None) -> None:
    """Test `retrieval_error_message()`."""
    message = retrieval_error_message(exception)
    assert message == expected
    # The exception own text must never be shown to the end user.
    assert message is None or EXCEPTION_MESSAGE not in message


REDIRECTION_PAGE = '<meta http-equiv="refresh" content="0; URL={target}">'
PAGE_CONTENTS = '<meta charset="utf-8">\nSome placeholder text\nmultiline and utf-8\u00f1\u20ac.'
DEFAULT_PAGE_NAME = 'page.html'
MISSING_PAGE_NAME = 'missing.html'

# The default values for the mocked `Settings()`.
URL_RETRIEVAL_TIMEOUT_SECONDS = 42
MAX_URL_REDIRECTIONS = 42


@pytest.fixture(name='set_settings', autouse=True)
# pylint: disable-next=unused-variable
def set_settings_fixture(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Install the test settings and return a function to override some of them."""
    program_module = sys.modules[retrieve_url.__module__]

    def set_settings(**overrides: int) -> None:
        values = {
            'url_retrieval_timeout_seconds': URL_RETRIEVAL_TIMEOUT_SECONDS,
            'max_url_redirections': MAX_URL_REDIRECTIONS,
        } | overrides
        monkeypatch.setattr(program_module, 'program_settings', Settings(**values))

    set_settings()
    return set_settings


# pylint: disable-next=unused-variable
def test_retrieve_url_reads_file(tmp_path: Path) -> None:
    """Test `retrieve_url()` reads the contents of a `file:` URL."""
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path.write_bytes(PAGE_CONTENTS.encode())
    assert retrieve_url(page_path.as_uri()) == PAGE_CONTENTS


# pylint: disable-next=unused-variable
def test_retrieve_url_reads_empty_file(tmp_path: Path) -> None:
    """Test `retrieve_url()` handles empty files."""
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path.write_bytes(b'')
    assert not retrieve_url(page_path.as_uri())


@pytest.mark.usefixtures('working_directory')
# pylint: disable-next=unused-variable
def test_retrieve_url_reads_relative_url(tmp_path: Path) -> None:
    """Test `retrieve_url()` resolves relative `file:` URLs."""
    (tmp_path / DEFAULT_PAGE_NAME).write_bytes(PAGE_CONTENTS.encode())
    assert retrieve_url(f'file:///{DEFAULT_PAGE_NAME}') == PAGE_CONTENTS


# pylint: disable-next=unused-variable
def test_retrieve_url_reads_encoded_path(tmp_path: Path) -> None:
    """Test `retrieve_url()` handles percent-encoded `file:` URLs."""
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path = page_path.with_stem(f'{page_path.stem} \u00f1')
    page_path.write_bytes(PAGE_CONTENTS.encode())
    assert retrieve_url(page_path.as_uri()) == PAGE_CONTENTS


# pylint: disable-next=unused-variable
def test_retrieve_url_missing_file(tmp_path: Path) -> None:
    """Test `retrieve_url()` propagates `FileNotFoundError`.

    Please note that it is wrapped in `URLError`.
    """
    with pytest.raises(URLError) as exception_info:
        retrieve_url((tmp_path / MISSING_PAGE_NAME).as_uri())
    assert isinstance(exception_info.value.reason, FileNotFoundError)


@pytest.mark.parametrize(('page', 'encoding'), [
    pytest.param(
        '<meta charset="iso-8859-1">\u00e1\u00f1',
        'iso-8859-1',
        id='meta_latin1',
    ),
    pytest.param(
        '<meta charset="windows-1252">\u20ac',
        'cp1252',
        id='meta_windows1252',
    ),
])
# pylint: disable-next=unused-variable
def test_retrieve_url_decodes_declared_charset(tmp_path: Path, page: str, encoding: str) -> None:
    """Test `retrieve_url()` decodes the contents properly."""
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path.write_bytes(page.encode(encoding))
    assert retrieve_url(page_path.as_uri()) == page


# pylint: disable-next=unused-variable
def test_retrieve_url_fallback_charset(tmp_path: Path) -> None:
    """Test `retrieve_url()` uses ISO-8859-1 as fallback charset."""
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path.write_bytes('\u00f1'.encode('utf-8'))
    assert retrieve_url(page_path.as_uri()) == '\u00c3\u00b1'


# pylint: disable-next=unused-variable
def test_retrieve_url_unknown_charset(tmp_path: Path) -> None:
    """Test `retrieve_url()` raises `CharsetError`.

    This error should be raised for unknown charsets found in the URL
    contents, too.
    """
    unknown_charset = 'unknown_charset'
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path.write_bytes(f'<meta charset="{unknown_charset}">'.encode('ascii'))
    with pytest.raises(CharsetError) as exception_info:
        retrieve_url(page_path.as_uri())
    assert exception_info.value.charset == unknown_charset


# pylint: disable-next=unused-variable
def test_retrieve_url_undecodable_contents(tmp_path: Path) -> None:
    """Test `retrieve_url()` propagates `UnicodeDecodeError`."""
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path.write_bytes(b'<meta charset="utf-8">\xff')
    with pytest.raises(UnicodeDecodeError):
        retrieve_url(page_path.as_uri())


@pytest.mark.parametrize('target_template', [
    pytest.param(
        'second.html',
        id='relative_target',
    ),
    pytest.param(
        '{second_url}',
        id='absolute_target',
    ),
])
# pylint: disable-next=unused-variable
def test_retrieve_url_follows_redirection(tmp_path: Path, target_template: str) -> None:
    """Test `retrieve_url()` follows a `meta refresh` redirection."""
    second_path = tmp_path / 'second.html'
    second_path.write_bytes(PAGE_CONTENTS.encode())
    target = target_template.format(second_url=second_path.as_uri())
    first_path = tmp_path / 'first.html'
    first_path.write_bytes(REDIRECTION_PAGE.format(target=target).encode('ascii'))
    assert retrieve_url(first_path.as_uri()) == PAGE_CONTENTS


@pytest.mark.usefixtures('working_directory')
# pylint: disable-next=unused-variable
def test_retrieve_url_follows_redirection_from_relative_url(tmp_path: Path) -> None:
    """Test `retrieve_url()` follows a relative redirection."""
    (tmp_path / 'first.html').write_bytes(REDIRECTION_PAGE.format(target='second.html').encode('ascii'))
    (tmp_path / 'second.html').write_bytes(PAGE_CONTENTS.encode())
    assert retrieve_url('file:///first.html') == PAGE_CONTENTS


# pylint: disable-next=unused-variable
def test_retrieve_url_redirections_limit(tmp_path: Path) -> None:
    """Test `retrieve_url()` honors URL redirection limits."""
    # Every page redirects to the next one, except the last.
    # From `page0.html` there is one redirection more than the limit.
    # From `page1.html` there are exactly as many as the limit.
    base = tmp_path / DEFAULT_PAGE_NAME
    last_number = MAX_URL_REDIRECTIONS + 1
    for number in range(last_number):
        redirection = REDIRECTION_PAGE.format(target=f'{base.stem}{number + 1}.html')
        base.with_stem(f'{base.stem}{number}').write_bytes(redirection.encode('ascii'))
    base.with_stem(f'{base.stem}{last_number}').write_bytes(PAGE_CONTENTS.encode('utf-8'))

    assert retrieve_url(base.with_stem(f'{base.stem}1').as_uri()) == PAGE_CONTENTS
    with pytest.raises(TooManyRedirectionsError) as exception_info:
        retrieve_url(base.with_stem(f'{base.stem}0').as_uri())
    assert exception_info.value.limit == MAX_URL_REDIRECTIONS


# pylint: disable-next=unused-variable
def test_retrieve_url_no_redirections_allowed(set_settings: Callable[..., None], tmp_path: Path) -> None:
    """Test `retrieve_url()` honors zero as URL redirection limit.

    The redirection target does not exist, so the unit also checks that
    the limit is enforced *before* trying to retrieve it.
    """
    redirection_limit = 0
    set_settings(max_url_redirections=redirection_limit)
    page_path = tmp_path / DEFAULT_PAGE_NAME
    page_path.write_bytes(REDIRECTION_PAGE.format(target=MISSING_PAGE_NAME).encode('ascii'))
    with pytest.raises(TooManyRedirectionsError) as exception_info:
        retrieve_url(page_path.as_uri())
    assert exception_info.value.limit == redirection_limit


# pylint: disable-next=unused-variable
def test_retrieve_url_redirection_uses_last_page_charset(tmp_path: Path) -> None:
    """Test `retrieve_url()` decodes with the last charset found."""
    second_page = '<meta charset="utf-8">\u00f1'
    (tmp_path / 'second.html').write_bytes(second_page.encode('utf-8'))
    first_path = tmp_path / 'first.html'
    first_path.write_bytes(
        ('<meta charset="iso-8859-1">' + REDIRECTION_PAGE.format(target='second.html')).encode('iso-8859-1'),
    )
    assert retrieve_url(first_path.as_uri()) == second_page


REDIRECTION_TARGET_URL = 'http://example.com/second'
REDIRECTION_TO_TARGET = REDIRECTION_PAGE.format(target=REDIRECTION_TARGET_URL).encode('ascii')


class FakeResponse:
    """Minimal stand-in for the object returned by `urlopen()`."""

    def __init__(self, contents: bytes, content_type: str | None) -> None:
        """Build a response with *contents* and *content_type*."""
        self.contents = contents
        self.headers = HTTPMessage()
        if content_type is not None:
            self.headers['Content-Type'] = content_type
        self.closed = False

    def read(self) -> bytes:
        """Return the response contents."""
        return self.contents

    def __enter__(self) -> Self:
        """Enter the context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit the context manager, closing the response."""
        self.closed = True


class FakeUrlopen:
    """Replacement for `urlopen()`.

    Serve canned responses and record the calls.
    """

    def __init__(self) -> None:
        """Initialize object."""
        self.responses: dict[str, FakeResponse | Exception] = {}
        self.served: list[FakeResponse] = []
        self.requests: list[Request] = []
        self.timeouts: list[float] = []

    def set_response(self, url: str, contents: bytes, content_type: str | None = None) -> None:
        """Serve a response with *contents* for *url*."""
        self.responses[url] = FakeResponse(contents, content_type)

    def set_exception(self, url: str, exception: Exception) -> None:
        """Raise *exception* when *url* is requested."""
        self.responses[url] = exception

    def __call__(self, request: Request, timeout: float) -> FakeResponse:
        """Record the call and serve the response for the URL."""
        self.requests.append(request)
        self.timeouts.append(timeout)
        response = self.responses[request.full_url]
        if isinstance(response, Exception):
            raise response
        self.served.append(response)
        return response


@pytest.fixture(name='fake_urlopen')
# pylint: disable-next=unused-variable
def fake_urlopen_fixture(monkeypatch: pytest.MonkeyPatch) -> FakeUrlopen:
    """Replace `urlopen()` in the program by a fake one."""
    fake = FakeUrlopen()
    monkeypatch.setattr(sys.modules[retrieve_url.__module__], 'urlopen', fake)
    return fake


# pylint: disable-next=unused-variable
def test_retrieve_url_header_charset_beats_meta(fake_urlopen: FakeUrlopen) -> None:
    """Test `retrieve_url()` charset from header beats one from meta."""
    fake_urlopen.set_response(SAMPLE_URL, PAGE_CONTENTS.encode(), 'text/html; charset=utf-8')
    assert retrieve_url(SAMPLE_URL) == PAGE_CONTENTS


# pylint: disable-next=unused-variable
def test_retrieve_url_unknown_header_charset(fake_urlopen: FakeUrlopen) -> None:
    """Test `retrieve_url()` raises `CharsetError`.

    This error should be raised for unknown charsets present in the HTTP
    headers, too.
    """
    unknown_charset = 'unknown_charset'
    fake_urlopen.set_response(SAMPLE_URL, PAGE_CONTENTS.encode('utf-8'), f'text/html; charset={unknown_charset}')
    with pytest.raises(CharsetError) as exception_info:
        retrieve_url(SAMPLE_URL)
    assert exception_info.value.charset == unknown_charset


# pylint: disable-next=unused-variable
def test_retrieve_url_blank_header_charset(fake_urlopen: FakeUrlopen) -> None:
    """Test `retrieve_url()` raises `CharsetError`.

    This error should be raised for whitespace-only charsets, too.

    The detected charset in this case is **EMPTY** and not the literal
    whitespace present in the headers.
    """
    fake_urlopen.set_response(SAMPLE_URL, PAGE_CONTENTS.encode('utf-8'), 'text/html; charset=" "')
    with pytest.raises(CharsetError) as exception_info:
        retrieve_url(SAMPLE_URL)
    assert exception_info.value.charset == ''  # pylint: disable=use-implicit-booleaness-not-comparison-to-string


# pylint: disable-next=unused-variable
def test_retrieve_url_header_charset_is_not_carried_over(fake_urlopen: FakeUrlopen) -> None:
    """Test `retrieve_url()` uses the charset in the last response."""
    fake_urlopen.set_response(SAMPLE_URL, REDIRECTION_TO_TARGET, 'text/html; charset=iso-8859-1')
    fake_urlopen.set_response(REDIRECTION_TARGET_URL, PAGE_CONTENTS.encode('utf-8'))
    assert retrieve_url(SAMPLE_URL) == PAGE_CONTENTS


# pylint: disable-next=unused-variable
def test_retrieve_url_requests_url_unchanged(fake_urlopen: FakeUrlopen) -> None:
    """Test `retrieve_url()` does not alter a non-`file:` URL."""
    url = 'http://example.com/page(1)?c=d'
    fake_urlopen.set_response(url, PAGE_CONTENTS.encode('utf-8'))
    retrieve_url(url)
    assert [request.full_url for request in fake_urlopen.requests] == [url]


# pylint: disable-next=unused-variable
def test_retrieve_url_requests_every_redirection(fake_urlopen: FakeUrlopen) -> None:
    """Test `retrieve_url()` requests all redirections."""
    fake_urlopen.set_response(SAMPLE_URL, REDIRECTION_TO_TARGET)
    fake_urlopen.set_response(REDIRECTION_TARGET_URL, PAGE_CONTENTS.encode('utf-8'))
    retrieve_url(SAMPLE_URL)
    assert [request.full_url for request in fake_urlopen.requests] == [SAMPLE_URL, REDIRECTION_TARGET_URL]
    assert [request.get_header('User-agent') for request in fake_urlopen.requests] == [USER_AGENT, USER_AGENT]
    assert fake_urlopen.timeouts == [URL_RETRIEVAL_TIMEOUT_SECONDS, URL_RETRIEVAL_TIMEOUT_SECONDS]


# pylint: disable-next=unused-variable
def test_retrieve_url_closes_responses(fake_urlopen: FakeUrlopen) -> None:
    """Test `retrieve_url()` closes every response."""
    fake_urlopen.set_response(SAMPLE_URL, REDIRECTION_TO_TARGET)
    fake_urlopen.set_response(REDIRECTION_TARGET_URL, PAGE_CONTENTS.encode('utf-8'))
    retrieve_url(SAMPLE_URL)
    assert [response.closed for response in fake_urlopen.served] == [True, True]


@pytest.mark.parametrize('exception', [
    pytest.param(
        URLError(EXCEPTION_MESSAGE),
        id='url_error',
    ),
    pytest.param(
        http_error(404),
        id='http_error',
    ),
    pytest.param(
        TimeoutError(),
        id='timeout',
    ),
    pytest.param(
        ConnectionResetError(errno.ECONNRESET, EXCEPTION_MESSAGE),
        id='connection_reset',
    ),
])
# pylint: disable-next=unused-variable
def test_retrieve_url_propagates_urlopen_exceptions(fake_urlopen: FakeUrlopen, exception: Exception) -> None:
    """Test `retrieve_url()` propagates `urlopen()` exceptions."""
    fake_urlopen.set_exception(SAMPLE_URL, exception)
    with pytest.raises(type(exception)) as exception_info:
        retrieve_url(SAMPLE_URL)
    assert exception_info.value is exception
