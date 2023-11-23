#! /usr/bin/env python3
"""Test suite for the skimming process (sacar las mantecas)."""
from errno import errorcode
from http.client import HTTPConnection, HTTPException
from socket import socket

import pytest

from sacamantecas import Messages, saca_las_mantecas, SkimmingError

CONNREFUSED_ERRNO = 10061
CONNREFUSED_MSG = 'No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión'
GETADDRINFO_ERRNO = 11001
GETADDRINFO_MSG = 'getaddrinfo failed'
UNKNOWN_URL_TYPE = (Messages.UNKNOWN_URL_TYPE[0].lower() + Messages.UNKNOWN_URL_TYPE[1:]).rstrip('.')
@pytest.mark.parametrize('url, expected', [
    ('scheme://example.com', Messages.GENERIC_URLERROR.format('', UNKNOWN_URL_TYPE.format('scheme://example.com'))),
    ('https://httpbin.org/status/404', Messages.HTTP_PROTOCOL_URLERROR.format('404', 'not found')),
    ('https://httpbin.org/status/200:', Messages.HTTP_PROTOCOL_URLERROR.format('400', 'bad request')),
    ('http://127.0.0.1:9999', Messages.OSLIKE_URLERROR.format(errorcode[CONNREFUSED_ERRNO], CONNREFUSED_MSG.lower())),
    ('http://nonexistent', Messages.OSLIKE_URLERROR.format(GETADDRINFO_ERRNO, GETADDRINFO_MSG))
])
def test_url_errors(url, expected):  # pylint: disable=unused-variable
    """Test URL retrieval errors."""
    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, None)
    assert str(excinfo.value) == Messages.URL_ACCESS_ERROR
    assert excinfo.value.details == expected


def test_http_errors(monkeypatch):  # pylint: disable=unused-variable
    """Test HTTP errors."""
    host = 'domain.tld'
    port = 'port'
    url = f'http://{host}:{port}'
    monkeypatch.setattr('sacamantecas.retrieve_url', lambda _: HTTPConnection(f'{host}:{port}'))
    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, None)
    assert isinstance(excinfo.value.__cause__, HTTPException)
    assert str(excinfo.value) == Messages.HTTP_RETRIEVAL_ERROR
    assert excinfo.value.details == f"InvalidURL: nonnumeric port: '{port}'."


def test_connection_errors(monkeypatch):  # pylint: disable=unused-variable
    """Test connection errors."""
    host = '127.0.0.1'
    port = 9999
    url = f'http://{host}:{port}'
    monkeypatch.setattr('sacamantecas.retrieve_url', lambda _: socket().connect((host, port)))
    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, None)
    assert isinstance(excinfo.value.__cause__, ConnectionError)
    assert str(excinfo.value) == Messages.CONNECTION_ERROR.format(errorcode[CONNREFUSED_ERRNO])
    assert excinfo.value.details == f'{CONNREFUSED_MSG}.'
