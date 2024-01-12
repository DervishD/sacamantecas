#! /usr/bin/env python3
"""Test suite for all URL handling functions."""
from pathlib import Path

import pytest

from sacamantecas import Config, detect_html_charset, get_redirected_url, resolve_file_url, retrieve_url


@pytest.mark.parametrize('netloc, base, extra', [
    ('', '/abspath', ''),
    ('netloc.url', '/abspath', ''),
    ('', '/abspath', '?query#fragment'),
    ('netloc.url', '/abspath', '?query#fragment'),
    ('', '/./relpath', ''),
    ('netloc.url', '/./relpath', ''),
    ('', '/./relpath', '?query#fragment'),
    ('netloc.url', '/./relpath', '?query#fragment')
])
def test_file_url_resolution(request, netloc, base, extra):  # pylint: disable=unused-variable
    """Test resolution of file:// URLs."""
    rootpath = Path(request.config.rootpath).as_posix()
    rootpath = f'{rootpath[0].upper()}{rootpath[1:]}'

    base = f'{base}/path/filename.suffix'
    if base.startswith('/./'):
        base = base.lstrip('/')

    expected = f'file://{netloc}/{Path(base).resolve().as_posix()}{extra}'
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
@pytest.mark.parametrize('url, expected', [
    (f'{RSCHEME}{RNETLOC}{RPATH}', f'{RSCHEME}{RNETLOC}{RPATH}'),
    (f'{RPATH}', f'{SCHEME}{NETLOC}{RPATH}'),
])
def test_url_redirection(delay, url, extra, expected):  # pylint: disable=unused-variable
    """Test URL redirections."""
    contents = fr'<meta http-equiv="refresh" content="{delay}url={url}{extra}"'.encode()
    result = get_redirected_url(BASE_URL, contents)
    assert result == expected + extra


@pytest.mark.parametrize('contents, expected', [
    ('<meta http-equiv="content-type" charset="{}">', 'cp1252'),
    ('<meta charset="{}">', 'cp850'),
    ('{}', Config.FALLBACK_HTML_CHARSET)
])
def test_charset_detection(contents, expected):  # pylint: disable=unused-variable
    """Test different ways of detecting the contents charset."""
    contents = contents.format(expected).encode('ascii')
    result = detect_html_charset(contents)
    assert result == expected


def test_url_retrieval():  # pylint: disable=unused-variable
    """Test full URL retrieval against a live server returning a UTF-8 encoded body."""
    contents, charset = retrieve_url('https://httpbin.org/encoding/utf8')
    contents = contents.decode(charset)
    assert 'STARGΛ̊TE SG-1, a = v̇ = r̈, a⃑ ⊥ b⃑' in contents
    assert '((V⍳V)=⍳⍴V)/V←,V    ⌷←⍳→⍴∆∇⊃‾⍎⍕⌈' in contents
