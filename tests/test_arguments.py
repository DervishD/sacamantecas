#! /usr/bin/env python3
"""Test suite for argument handling."""
import inspect
from typing import TYPE_CHECKING

import pytest

from sacamantecas import (
    bootstrap,
    Handler,
    parse_arguments,
    single_url_handler,
    SourceError,
    spreadsheet_handler,
    textfile_handler,
    unsupported_source_handler,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_unsupported_source() -> None:  # pylint: disable=unused-variable
    """Test unsupported source."""
    sources = 'source'
    source, handler = next(parse_arguments(sources))

    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)

    assert source == sources
    assert inspect.isgenerator(handler)
    assert inspect.isgeneratorfunction(unsupported_source_handler)
    assert handler.gi_code.co_name == unsupported_source_handler.__name__
    assert str(excinfo.value) == 'La fuente no es de un tipo admitido.'


@pytest.mark.parametrize(('sources', 'expected'), [
    pytest.param('http://source', single_url_handler, id='test_http_source_identification'),
    pytest.param('file://source', single_url_handler, id='test_file_source_identification'),
    pytest.param('source.txt', textfile_handler, id='test_txt_source_identification'),
    pytest.param('source.xlsx', spreadsheet_handler, id='test_xlsx_source_identification'),
])
def test_source_identification(sources: str, expected: Handler) -> None:  # pylint: disable=unused-variable
    """Test identification of different *sources*."""
    source, handler = next(parse_arguments(sources))

    assert source == sources
    assert inspect.isgenerator(handler)
    assert inspect.isgeneratorfunction(expected)
    assert handler.gi_code.co_name == expected.__name__


@pytest.mark.parametrize(('suffix', 'handler_factory'), [
    pytest.param('.txt', textfile_handler, id='test_missing_txt_source'),
    pytest.param('.xlsx', spreadsheet_handler, id='test_missing_xlsx_source'),
])
# pylint: disable-next=unused-variable
def test_missing_source(tmp_path: Path, suffix: str, handler_factory: Callable[[Path], Handler]) -> None:
    """Test handling of missing sources."""
    handler = handler_factory(tmp_path / f'non_existent{suffix}')

    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)

    assert str(excinfo.value).startswith('No se encontró el fichero de entrada.')
