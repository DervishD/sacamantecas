#! /usr/bin/env python3
"""Test suite for parse_arguments()."""
import inspect

import pytest

from sacamantecas import parse_arguments, single_url_handler, spreadsheet_handler, textfile_handler


def test_unsupported_source():  # pylint: disable=unused-variable
    """Test unsupported source."""
    sources = 'source'
    source, handler = list(parse_arguments(sources))[0]
    assert source == sources
    assert handler is None


@pytest.mark.parametrize('sources, expected', [
    ('http://source', single_url_handler),
    ('file://source', single_url_handler),
    ('source.txt', textfile_handler),
    ('source.xlsx', spreadsheet_handler)
])
def test_source_identification(sources, expected):  # pylint: disable=unused-variable
    """Test identification of different sources."""
    source, handler = list(parse_arguments(sources))[0]
    assert source == sources
    assert inspect.isgenerator(handler)
    assert inspect.isgeneratorfunction(expected)
    assert handler.gi_code.co_name == expected.__name__
