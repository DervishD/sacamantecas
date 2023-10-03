#! /usr/bin/env python3
"""Test suite for parse_sources()."""
from pathlib import Path
import pytest
from sacamantecas import parse_sources

# The 'expected' argument is a tuple containing three items:
#   - The expected source type detected.
#   - The expected computed source name.
#   - The expected computed sink name.
#
# The different sources are tested in normal and 'dump' modes.
@pytest.mark.parametrize('source, expected', [
    ('source', (None, 'source', None)),
    ('http://source', ('uri', Path('http://source'), Path('http___source_out.txt'))),
    ('file://source', ('uri', Path('file://source'), Path('file___source_out.txt'))),
    ('source.txt', ('txt', Path('source.txt'), Path('source_out.txt'))),
    ('source.xlsx', ('xls', Path('source.xlsx'), Path('source_out.xlsx')))
])
def test_parse_sources(source, expected):  # pylint: disable=unused-variable
    """Test parsing of Manteca sources from command line."""
    assert list(parse_sources([source])) == [expected + (False,)]
    assert list(parse_sources([f'dump://{source}'])) == [expected + (True,)]
