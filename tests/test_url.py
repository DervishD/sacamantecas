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
    pytest.param('', id='without_delay'),
])
@pytest.mark.parametrize('extra', [
    pytest.param(REXTRA, id='with_extra'),
    pytest.param('', id='without_extra'),
])
@pytest.mark.parametrize(('url', 'expected'), [
    pytest.param(f'{RSCHEME}{RNETLOC}{RPATH}', f'{RSCHEME}{RNETLOC}{RPATH}', id='test_url_redirection_full'),
    pytest.param(f'{RPATH}', f'{SCHEME}{NETLOC}{RPATH}', id='test_url_redirection_partial'),
])
def test_url_redirection(delay: str, url: str, extra: str, expected: str) -> None:
    """Test *url* redirections using *delay* and *extra* fields."""
    contents = fr'<meta http-equiv="refresh" content="{delay}url={url}{extra}"'.encode()
    result = get_redirected_url(contents, BASE_URL)

    assert result == expected + extra


@pytest.mark.parametrize(('contents', 'expected'), [
    pytest.param('<meta http-equiv="content-type" charset="{}">', 'cp1252', id='test_url_charset_detection_cp1252'),
    pytest.param('<meta charset="{}">', 'cp850', id='test_url_charset_detection_cp850'),
    pytest.param('{}', 'iso-8859-1', id='test_url_charset_detection_iso-8859-1'),
])
def test_url_charset_detection(contents: str, expected: str) -> None:
    """Test different ways of detecting the *contents* charset."""
    result = detect_html_charset(contents.format(expected).encode('ascii')).lower()

    assert result == expected


def test_url_retrieve_utf8_data() -> None:
    """Test full URL retrieval of UTF-8 encoded data.

    Both `https:` and `file:` URL schemes are tested.

    The first one, against a live server returning a UTF-8 encoded body.
    The second, using a temporary file with fake contents.
    """
    mock_hostname = 'localhost'
    server_root_path = Path(__file__).resolve().parent
    sample_file_path = server_root_path / 'utf-8.html'

    expected_contents = sample_file_path.read_text(encoding='utf-8')

    previous_cwd = Path.cwd()
    chdir(server_root_path)

    http_server = HTTPServer((mock_hostname, 0), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)

    try:
        thread.start()

        url = f'http://{mock_hostname}:{http_server.server_port}/{sample_file_path.name}'
        contents, encoding = retrieve_url(url)
        assert encoding.lower() == 'utf-8'
        assert contents.decode(encoding) == expected_contents

        url = f'file:///{sample_file_path}'
        contents, encoding = retrieve_url(url)
        assert encoding.lower() == 'utf-8'
        assert contents.decode(encoding) == expected_contents

    finally:
        http_server.shutdown()
        thread.join()
        chdir(previous_cwd)
