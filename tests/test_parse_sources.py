#! /usr/bin/env python3
"""Test suite for parse_sources()."""
from pathlib import Path
import pytest
from sacamantecas import parse_sources, DUMPMODE_PREFIX, SourceTypes

# The 'expected' argument is a tuple containing three items:
#   - The expected computed source name.
#   - The expected computed sink name.
#   - The expected source type detected.
#
# The different sources are tested in normal and 'dump' modes.
@pytest.mark.parametrize('source, expected', [
    ('source', ('source', None, None)),
    ('http://source', (Path('http://source'), Path('http___source_out.txt'), SourceTypes.URL)),
    ('file://source', (Path('file://source'), Path('file___source_out.txt'), SourceTypes.URL)),
    ('source.txt', (Path('source.txt'), Path('source_out.txt'), SourceTypes.TEXT)),
    ('source.xlsx', (Path('source.xlsx'), Path('source_out.xlsx'), SourceTypes.EXCEL))
])
def test_parse_sources(source, expected):  # pylint: disable=unused-variable
    """Test parsing of Manteca sources from command line."""
    assert list(parse_sources([source])) == [expected + (False,)]
    assert list(parse_sources([f'{DUMPMODE_PREFIX}{source}'])) == [expected + (True,)]
