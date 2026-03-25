#! /usr/bin/env python3
"""Test suite for the skimming process (sacar las mantecas)."""
from errno import errorcode
from http.client import HTTPConnection, HTTPException, HTTPMessage
from socket import socket
from urllib.error import HTTPError, URLError

import pytest

from sacamantecas import BaseParser, saca_las_mantecas, SkimmingError

MOCK_PARSER = BaseParser()
MOCK_HOST = 'localhost'

CONNREFUSED_ERRNO = 10061
CONNREFUSED_MSG = 'No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión'
GETADDRINFO_ERRNO = 11001
GETADDRINFO_MSG = 'getaddrinfo failed'
@pytest.mark.parametrize(('url', 'side_effect', 'expected'), [
    (
        f'scheme://{MOCK_HOST}',
        Exception(),
        f'Error de URL: el URL «scheme://{MOCK_HOST}» es de tipo desconocido.',
    ),
    (
        f'https://{MOCK_HOST}/status/404',
        HTTPError(url=f'https://{MOCK_HOST}/status/404', code=404, msg='Not Found', hdrs=HTTPMessage(), fp=None),
        'Error de protocolo HTTP 404: not found.',
    ),
    (
        f'https://{MOCK_HOST}/status/200',
        HTTPError(url='https://{MOCK_URL}/status/200', code=200, msg='Bad Request', hdrs=HTTPMessage(), fp=None),
        'Error de protocolo HTTP 200: bad request.',
    ),
    (
        f'http://{MOCK_HOST}:7',
        URLError(OSError(CONNREFUSED_ERRNO, CONNREFUSED_MSG)),
        f'Error de red {errorcode[CONNREFUSED_ERRNO]}: {CONNREFUSED_MSG.lower()}.',
    ),
    (
        f'http://{MOCK_HOST}/nonexistent',
        URLError(OSError(GETADDRINFO_ERRNO, GETADDRINFO_MSG)),
        f'Error de red {GETADDRINFO_ERRNO}: {GETADDRINFO_MSG}.',
    ),
], ids=[
    'test_bad_scheme_url_error',
    'test_404_status_url_error',
    'test_200_status_url_error',
    'test_connection_refused_url_error',
    'test_nonexistent_url_error',
])
def test_url_errors(  # pylint: disable=unused-variable
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    side_effect: Exception,
    expected: str) -> None:
    """Test *url* retrieval errors."""
    def mock_urlopen(_: str) -> None:
        raise side_effect

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'urlopen', mock_urlopen)

    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, MOCK_PARSER)

    assert str(excinfo.value) == 'No resultó posible acceder a la dirección especificada.'
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
    assert str(excinfo.value) == 'No se obtuvieron contenidos.'
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
    assert str(excinfo.value) == f'Se produjo un error de conexión «{errorcode[CONNREFUSED_ERRNO]}» accediendo al URL.'
    assert excinfo.value.details == f'{CONNREFUSED_MSG}.'
