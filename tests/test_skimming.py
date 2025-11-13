#! /usr/bin/env python3
"""Test suite for the skimming process (sacar las mantecas)."""
from errno import errorcode
from http.client import HTTPConnection, HTTPException, HTTPMessage
from socket import socket
from urllib.error import HTTPError, URLError

import pytest

from sacamantecas import BaseParser, Messages, saca_las_mantecas, SkimmingError

MOCK_PARSER = BaseParser()
MOCK_HOST = 'localhost'

CONNREFUSED_ERRNO = 10061
CONNREFUSED_MSG = 'No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión'
GETADDRINFO_ERRNO = 11001
GETADDRINFO_MSG = 'getaddrinfo failed'
UNKNOWN_URL_TYPE_MESSAGE = (Messages.UNKNOWN_URL_TYPE[0].lower() + Messages.UNKNOWN_URL_TYPE[1:]).rstrip('.')
@pytest.mark.parametrize(('url', 'side_effect', 'expected'), [
    (
        f'scheme://{MOCK_HOST}',
        Exception(),
        Messages.GENERIC_URLERROR.format('', UNKNOWN_URL_TYPE_MESSAGE.format(f'scheme://{MOCK_HOST}')),
    ),
    (
        f'https://{MOCK_HOST}/status/404',
        HTTPError(url=f'https://{MOCK_HOST}/status/404', code=404, msg='Not Found', hdrs=HTTPMessage(), fp=None),
        Messages.HTTP_PROTOCOL_URLERROR.format('404', 'not found'),
    ),
    (
        f'https://{MOCK_HOST}/status/200',
        HTTPError(url='https://{MOCK_URL}/status/200', code=200, msg='Bad Request', hdrs=HTTPMessage(), fp=None),
        Messages.HTTP_PROTOCOL_URLERROR.format('200', 'bad request'),
    ),
    (
        f'http://{MOCK_HOST}:7',
        URLError(OSError(CONNREFUSED_ERRNO, CONNREFUSED_MSG)),
        Messages.OSLIKE_URLERROR.format(errorcode[CONNREFUSED_ERRNO], CONNREFUSED_MSG.lower()),
    ),
    (
        f'http://{MOCK_HOST}/nonexistent',
        URLError(OSError(GETADDRINFO_ERRNO, GETADDRINFO_MSG)),
        Messages.OSLIKE_URLERROR.format(GETADDRINFO_ERRNO, GETADDRINFO_MSG),
    ),
])
def test_url_errors(  # pylint: disable=unused-variable
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    side_effect: Exception,
    expected: str) -> None:
    """Test URL retrieval errors."""
    def mock_urlopen(_: str) -> None:
        raise side_effect

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'urlopen', mock_urlopen)

    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, MOCK_PARSER)

    assert str(excinfo.value) == Messages.URL_ACCESS_ERROR
    assert excinfo.value.details == expected


def test_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test HTTP errors."""
    host = MOCK_HOST
    port = 'port'
    url = f'http://{host}:{port}'

    def patched_retrieve_url(_: str) -> HTTPConnection:
        return HTTPConnection(f'{host}:{port}')

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'retrieve_url', patched_retrieve_url)

    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, MOCK_PARSER)

    assert isinstance(excinfo.value.__cause__, HTTPException)
    assert str(excinfo.value) == Messages.HTTP_RETRIEVAL_ERROR
    assert excinfo.value.details == f"InvalidURL: nonnumeric port: '{port}'."


def test_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=unused-variable
    """Test connection errors."""
    host = MOCK_HOST
    port = 9999
    url = f'http://{host}:{port}'

    def patched_retrieve_url(_: str) -> None:
        return socket().connect((host, port))

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'retrieve_url', patched_retrieve_url)

    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, MOCK_PARSER)

    assert isinstance(excinfo.value.__cause__, ConnectionError)
    assert str(excinfo.value) == Messages.CONNECTION_ERROR.format(errorcode[CONNREFUSED_ERRNO])
    assert excinfo.value.details == f'{CONNREFUSED_MSG}.'
