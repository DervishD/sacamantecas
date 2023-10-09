#! /usr/bin/env python3
"""Test suite for parse_sources()."""
from contextlib import nullcontext
import pytest
import sacamantecas as sm


@pytest.mark.parametrize('arguments, exception, expected', [
    (['source'], pytest.raises(sm.UnsupportedSourceError), None),
    (['http://source'], nullcontext(), sm.URLSourceHandler),
    (['file://source'], nullcontext(), sm.URLSourceHandler),
    (['source.txt'], nullcontext(), sm.TextSourceHandler),
    (['source.xlsx'], nullcontext(), sm.ExcelSourceHandler)
])
def test_source_identification(arguments, exception, expected):  # pylint: disable=unused-variable
    """Test identification of different sources."""
    with exception:
        result = list(sm.parse_arguments(arguments))[0]
        assert isinstance(result, expected)
