#! /usr/bin/env python3
"""Test suite for parse_sources()."""
from contextlib import nullcontext
import inspect
import pytest
import sacamantecas as sm


@pytest.mark.parametrize('sources, exception, expected', [
    (['source'], pytest.raises(sm.UnsupportedSourceError), None),
    (['http://source'], nullcontext(), sm.single_url_handler),
    (['file://source'], nullcontext(), sm.single_url_handler),
    (['source.txt'], nullcontext(), sm.textfile_handler),
    (['source.xlsx'], nullcontext(), sm.spreadsheet_handler)
])
def test_source_identification(sources, exception, expected):  # pylint: disable=unused-variable
    """Test identification of different sources."""
    with exception:
        source, handler = list(sm.parse_sources(sources))[0]
        assert source == sources[0]
        assert inspect.isgenerator(handler)
        assert inspect.isgeneratorfunction(expected)
        assert handler.gi_code.co_name == expected.__name__
