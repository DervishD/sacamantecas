#! /usr/bin/env python3
"""Test suite for all URL handling functions."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
from os import chdir
from pathlib import Path
import threading
from urllib.parse import quote

import pytest

from sacamantecas import Constants, detect_html_charset, get_redirected_url, resolve_file_url, retrieve_url


@pytest.mark.parametrize(('netloc', 'base', 'extra'), [
    ('', '/abspath', ''),
    ('netloc.url', '/abspath', ''),
    ('', '/abspath', '?query#fragment'),
    ('netloc.url', '/abspath', '?query#fragment'),
    ('', '/./relpath', ''),
    ('netloc.url', '/./relpath', ''),
    ('', '/./relpath', '?query#fragment'),
    ('netloc.url', '/./relpath', '?query#fragment'),
])
# pylint: disable-next=unused-variable
def test_file_url_resolution(request: pytest.FixtureRequest, netloc:str, base:str, extra:str) -> None:
    """Test resolution of file:// URLs."""
    rootpath = Path(request.config.rootpath).as_posix()
    rootpath = f'{rootpath[0].upper()}{rootpath[1:]}'

    base = f'{base}/path/filename.suffix'
    if base.startswith('/./'):
        base = base.lstrip('/')

    expected = f'file://{netloc}/{quote(Path(base).resolve().as_posix(), safe=Constants.FILE_URL_SAFE_CHARS)}{extra}'
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
@pytest.mark.parametrize('delay', ['0; ', '1234; ', ''])
@pytest.mark.parametrize('extra', [REXTRA, ''])
@pytest.mark.parametrize(('url', 'expected'), [
    (f'{RSCHEME}{RNETLOC}{RPATH}', f'{RSCHEME}{RNETLOC}{RPATH}'),
    (f'{RPATH}', f'{SCHEME}{NETLOC}{RPATH}'),
])
def test_url_redirection(delay: str, url: str, extra: str, expected: str) -> None:  # pylint: disable=unused-variable
    """Test URL redirections."""
    contents = fr'<meta http-equiv="refresh" content="{delay}url={url}{extra}"'.encode()
    result = get_redirected_url(BASE_URL, contents)

    assert result == expected + extra


@pytest.mark.parametrize(('contents', 'expected'), [
    ('<meta http-equiv="content-type" charset="{}">', 'cp1252'),
    ('<meta charset="{}">', 'cp850'),
    ('{}', Constants.FALLBACK_HTML_CHARSET),
])
def test_charset_detection(contents: str, expected: str) -> None:  # pylint: disable=unused-variable
    """Test different ways of detecting the contents charset."""
    result = detect_html_charset(contents.format(expected).encode('ascii'))

    assert result == expected


MOCK_HOST = 'localhost'
SERVER_ROOT = Path(__file__).resolve().parent
SAMPLE_FILE_PATH = SERVER_ROOT / 'utf-8.html'
def test_utf8_url_retrieval() -> None:  # pylint: disable=unused-variable
    """Test full URL retrieval of UTF-8 encoded data.

    Both https:// and file:// URls are tested.

    The first one, against a live server returning a UTF-8 encoded body.
    The second, using a temporary file with fake contents.
    """
    expected_contents = SAMPLE_FILE_PATH.read_text(encoding=Constants.UTF8)

    previous_cwd = Path.cwd()
    chdir(SERVER_ROOT)

    http_server = HTTPServer((MOCK_HOST, 0), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)

    try:
        thread.start()

        url = f'http://{MOCK_HOST}:{http_server.server_port}/{SAMPLE_FILE_PATH.name}'
        contents, encoding = retrieve_url(url)
        assert encoding.lower() == Constants.UTF8.lower()
        assert contents.decode(encoding) == expected_contents

        url = f'{Constants.FILE_SCHEME}/{SAMPLE_FILE_PATH}'
        contents, encoding = retrieve_url(url)
        assert encoding.lower() == Constants.UTF8.lower()
        assert contents.decode(encoding) == expected_contents

    finally:
        http_server.shutdown()
        thread.join()
        chdir(previous_cwd)
