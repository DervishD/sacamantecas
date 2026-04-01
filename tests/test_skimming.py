#! /usr/bin/env python3
"""Test suite for the skimming process (sacar las mantecas)."""
from errno import errorcode
from http.client import HTTPException, HTTPMessage
from urllib.error import HTTPError, URLError

import pytest

from sacamantecas import (
    BaseParser,
    saca_las_mantecas,
    SkimmingError,
)

MOCK_PARSER = BaseParser()
MOCK_HOST = 'localhost'
MOCK_URL = f'https://{MOCK_HOST}'

CONNREFUSED_ERRNO = 10061
CONNREFUSED_MSG = 'No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión'
GETADDRINFO_ERRNO = 11001
GETADDRINFO_MSG = 'getaddrinfo failed'
URL_ACCESS_ERROR_MESSAGE = 'No resultó posible acceder a la dirección especificada.'
HTTP_RETRIEVAL_ERROR_MESSAGE = 'No se obtuvieron contenidos.'
@pytest.mark.parametrize(('url', 'mock_exception', 'error_message'), [
    pytest.param(
        f'{MOCK_URL}/status/404',
        HTTPError(url=f'{MOCK_URL}/status/404', code=404, msg='Not Found', hdrs=HTTPMessage(), fp=None),
        (URL_ACCESS_ERROR_MESSAGE, 'Error de protocolo HTTP 404: not found.'),
        id='test_skimming_http_error_404_status',
    ),
    pytest.param(
        f'{MOCK_URL}/status/200',
        HTTPError(url='https://{MOCK_URL}/status/200', code=200, msg='Bad Request', hdrs=HTTPMessage(), fp=None),
        (URL_ACCESS_ERROR_MESSAGE, 'Error de protocolo HTTP 200: bad request.'),
        id='test_skimming_http_error_200_status',
    ),
    pytest.param(
        f'{MOCK_URL}:port',
        HTTPException("InvalidURL: nonnumeric port: 'port'"),
        (HTTP_RETRIEVAL_ERROR_MESSAGE, "HTTPException: InvalidURL: nonnumeric port: 'port'."),
        id='test_skimming_http_error_invalid_port',
    ),
    pytest.param(
        f'scheme://{MOCK_HOST}',
        Exception(),
        (URL_ACCESS_ERROR_MESSAGE, f'Error de URL: el URL «scheme://{MOCK_HOST}» es de tipo desconocido.'),
        id='test_skimming_url_error_bad_scheme',
    ),
    pytest.param(
        f'{MOCK_URL}:7',
        URLError(OSError(CONNREFUSED_ERRNO, CONNREFUSED_MSG)),
        (URL_ACCESS_ERROR_MESSAGE, f'Error de red {errorcode[CONNREFUSED_ERRNO]}: {CONNREFUSED_MSG.lower()}.'),
        id='test_skimming_url_error_connection_refused',
    ),
    pytest.param(
        f'{MOCK_URL}/nonexistent',
        URLError(OSError(GETADDRINFO_ERRNO, GETADDRINFO_MSG)),
        (URL_ACCESS_ERROR_MESSAGE, f'Error de red {GETADDRINFO_ERRNO}: {GETADDRINFO_MSG}.'),
        id='test_skimming_url_error_nonexistent_url',
    ),
    pytest.param(
        MOCK_URL,
        URLError(OSError(None, 'No se sabe qué ha pasado')),
        (URL_ACCESS_ERROR_MESSAGE, 'Error de red desconocido: no se sabe qué ha pasado.'),
        id='test_skimming_url_error_no_errno',
    ),
    pytest.param(
        MOCK_URL,
        ConnectionError(CONNREFUSED_ERRNO, CONNREFUSED_MSG),
        (f'Se produjo un error de conexión {errorcode[CONNREFUSED_ERRNO]} accediendo al URL.', f'{CONNREFUSED_MSG}.'),
        id='test_skimming_connection_error_baseline',
    ),
    pytest.param(
        MOCK_URL,
        ConnectionError(None, 'no se pudo establecer una conexión'),
        ('Se produjo un error de conexión desconocido accediendo al URL.', 'No se pudo establecer una conexión.'),
        id='test_skimming_connection_error_no_errno',
    ),
    pytest.param(
        MOCK_URL,
        ConnectionError(CONNREFUSED_ERRNO, None),
        (f'Se produjo un error de conexión {errorcode[CONNREFUSED_ERRNO]} accediendo al URL.', ''),
        id='test_skimming_connection_error_no_strerror',
    ),
    pytest.param(
        MOCK_URL,
        ConnectionError(),
        ('Se produjo un error de conexión desconocido accediendo al URL.', ''),
        id='test_skimming_connection_error_empty_exception',
    ),
])
def test_skimming_url_retrieval_errors(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    mock_exception: Exception,
    error_message: tuple[str, str],
) -> None:
    """Test *url* retrieval errors."""
    def mock_urlopen(_: str) -> None:
        raise mock_exception

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'urlopen', mock_urlopen)

    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(url, MOCK_PARSER)

    assert (str(excinfo.value), excinfo.value.details) == error_message


def test_skimming_no_contents(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test retrieving no contents from the URL."""
    def mock_retrieve_url(_: str) -> tuple[None, None]:
        return None, None

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'retrieve_url', mock_retrieve_url)

    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(MOCK_URL, MOCK_PARSER)

    assert str(excinfo.value) == 'No se recibieron contenidos del URL.'


def test_skimming_no_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test retrieving no metadata from the URL."""
    def mock_retrieve_url(_: str) -> tuple[bytes, str]:
        return b'mock_contents', 'utf-8'

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'retrieve_url', mock_retrieve_url)

    with pytest.raises(SkimmingError) as excinfo:
        saca_las_mantecas(MOCK_URL, MOCK_PARSER)

    assert str(excinfo.value) == 'No se obtuvieron metadatos.'


def test_skimming_proper_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test retrieving proper metadata from the URL."""
    expected_metadata = {'mock_key' : 'mock_value'}
    def mock_retrieve_url(_: str) -> tuple[bytes, str]:
        return b'mock_contents', 'utf-8'

    def mock_get_metadata(_: object) -> dict[str, str]:
        return expected_metadata

    monkeypatch.setitem(saca_las_mantecas.__globals__, 'retrieve_url', mock_retrieve_url)
    monkeypatch.setattr(BaseParser, 'get_metadata', mock_get_metadata)

    result = saca_las_mantecas(MOCK_URL, MOCK_PARSER)

    assert result == expected_metadata
