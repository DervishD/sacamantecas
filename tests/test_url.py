#! /usr/bin/env python3
"""Test suite for all URL handling functions."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
from os import chdir
from pathlib import Path
import threading
from urllib.parse import quote

import pytest

from sacamantecas import (
    detect_html_charset,
    get_redirected_url,
    resolve_file_url,
    retrieve_url,
)


@pytest.mark.parametrize(('netloc', 'base', 'extra'), [
    pytest.param('', '/abspath', '', id='test_file_url_resolution_abspath'),
    pytest.param('netloc.url', '/abspath', '', id='test_file_url_resolution_netloc_abspath'),
    pytest.param('', '/abspath', '?query#fragment', id='test_file_url_resolution_abspath_query'),
    pytest.param('netloc.url', '/abspath', '?query#fragment', id='test_file_url_resolution_netloc_abspath_query'),
    pytest.param('', '/./relpath', '', id='test_file_url_resolution_relpath'),
    pytest.param('netloc.url', '/./relpath', '', id='test_file_url_resolution_netloc_relpath'),
    pytest.param('', '/./relpath', '?query#fragment', id='test_file_url_resolution_relpath_query'),
    pytest.param('netloc.url', '/./relpath', '?query#fragment', id='test_file_url_resolution_netloc_relpath_query'),
])
# pylint: disable-next=unused-variable
def test_file_url_resolution(request: pytest.FixtureRequest, netloc:str, base:str, extra:str) -> None:
    """Test resolution of `file:` URLs."""
    rootpath = Path(request.config.rootpath).as_posix()
    rootpath = f'{rootpath[0].upper()}{rootpath[1:]}'

    base = f'{base}/path/filename.suffix'
    if base.startswith('/./'):
        base = base.lstrip('/')

    expected = f'file://{netloc}/{quote(Path(base).resolve().as_posix(), safe=':/')}{extra}'
    result = resolve_file_url(f'file://{netloc}/{base}{extra}')

    assert result == expected


SCHEME = 'http://'
RSCHEME = 'https://'
NETLOC = 'sub.domain.tld:80'
RNETLOC = 'rsub.rdomain.rtld:8080'
PATH = '/root/sub/p.html'
RPATH = '/rroot/rsub/rp.html'
EXTRA = ';pr?k1=v1&k2=v2#fr'
REXTRA = ';rpr?rk1=rv1&rk2=rv2#rfr'
BASE_URL = f'{SCHEME}{NETLOC}{PATH}{EXTRA}'
@pytest.mark.parametrize('delay', [
    pytest.param('0; ', id='0_delay'),
    pytest.param('1234; ', id='1234_delay'),
    pytest.param('', id='no_delay'),
])
@pytest.mark.parametrize('extra', [
    pytest.param(REXTRA, id='extra'),
    pytest.param('', id='no_extra'),
])
@pytest.mark.parametrize(('url', 'expected'), [
    pytest.param(f'{RSCHEME}{RNETLOC}{RPATH}', f'{RSCHEME}{RNETLOC}{RPATH}', id='test_full_url_redirection'),
    pytest.param(f'{RPATH}', f'{SCHEME}{NETLOC}{RPATH}', id='test_partial_url_redirection'),
])
def test_url_redirection(delay: str, url: str, extra: str, expected: str) -> None:  # pylint: disable=unused-variable
    """Test *url* redirections using *delay* and *extra* fields."""
    contents = fr'<meta http-equiv="refresh" content="{delay}url={url}{extra}"'.encode()
    result = get_redirected_url(contents, BASE_URL)

    assert result == expected + extra


@pytest.mark.parametrize(('contents', 'expected'), [
    pytest.param('<meta http-equiv="content-type" charset="{}">', 'cp1252', id='test_cp1252_charset_detection'),
    pytest.param('<meta charset="{}">', 'cp850', id='test_cp850_charset_detection'),
    pytest.param('{}', 'ISO-8859-1', id='test_ISO-8859-1_charset_detection'),
])
def test_charset_detection(contents: str, expected: str) -> None:  # pylint: disable=unused-variable
    """Test different ways of detecting the *contents* charset."""
    result = detect_html_charset(contents.format(expected).encode('ascii'))

    assert result == expected


MOCK_HOST = 'localhost'
SERVER_ROOT = Path(__file__).resolve().parent
SAMPLE_FILE_PATH = SERVER_ROOT / 'utf-8.html'
def test_utf8_url_retrieval() -> None:  # pylint: disable=unused-variable
    """Test full URL retrieval of UTF-8 encoded data.

    Both `https:` and `file:` URL schemes are tested.

    The first one, against a live server returning a UTF-8 encoded body.
    The second, using a temporary file with fake contents.
    """
    expected_contents = SAMPLE_FILE_PATH.read_text(encoding='utf-8')

    previous_cwd = Path.cwd()
    chdir(SERVER_ROOT)

    http_server = HTTPServer((MOCK_HOST, 0), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)

    try:
        thread.start()

        url = f'http://{MOCK_HOST}:{http_server.server_port}/{SAMPLE_FILE_PATH.name}'
        contents, encoding = retrieve_url(url)
        assert encoding.lower() == 'utf-8'
        assert contents.decode(encoding) == expected_contents

        url = f'file:///{SAMPLE_FILE_PATH}'
        contents, encoding = retrieve_url(url)
        assert encoding.lower() == 'utf-8'
        assert contents.decode(encoding) == expected_contents

    finally:
        http_server.shutdown()
        thread.join()
        chdir(previous_cwd)
