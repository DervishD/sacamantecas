#! /usr/bin/env python3
"""Test suite for argument handling."""
import inspect

import pytest

from sacamantecas import (
    bootstrap,
    Handler,
    Messages,
    parse_arguments,
    single_url_handler,
    SourceError,
    spreadsheet_handler,
    textfile_handler,
    unsupported_source_handler,
)


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
    assert str(excinfo.value) == Messages.UNSUPPORTED_SOURCE


@pytest.mark.parametrize(('sources', 'expected'), [
    ('http://source', single_url_handler),
    ('file://source', single_url_handler),
    ('source.txt', textfile_handler),
    ('source.xlsx', spreadsheet_handler),
])
def test_source_identification(sources: str, expected: Handler) -> None:  # pylint: disable=unused-variable
    """Test identification of different sources."""
    source, handler = next(parse_arguments(sources))

    assert source == sources
    assert inspect.isgenerator(handler)
    assert inspect.isgeneratorfunction(expected)
    assert handler.gi_code.co_name == expected.__name__
