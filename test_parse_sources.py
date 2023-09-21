#! /usr/bin/env python3
"""Test suite for parse_argv."""
from pathlib import Path
import pytest
from sacamantecas import parse_sources


@pytest.mark.parametrize("source, source_name, dumpmode", [
    ('source', 'source', False),
    ('dump://source_dump', 'source_dump', True),
])
def test_invalid_source(source, source_name, dumpmode):  # pylint: disable=unused-variable
    """Test for invalid (unsupported) sources."""
    assert list(parse_sources([source])) == [(None, source_name, None, dumpmode)]


@pytest.mark.parametrize("source, manteca_source, sink_name, dumpmode", [
    ('http://source', Path('http://source'), Path('http___source_out.txt'), False),
    ('dump://http://source_dump', Path('http://source_dump'), Path('http___source_dump_out.txt'), True),
    ('file://source', Path('file://source'), Path('file___source_out.txt'), False),
    ('dump://file://source_dump', Path('file://source_dump'), Path('file___source_dump_out.txt'), True)
])
def test_uri_source(source, manteca_source, sink_name, dumpmode):  # pylint: disable=unused-variable
    """Test for single URI sources."""
    assert list(parse_sources([source])) == [('uri', manteca_source, sink_name, dumpmode)]


@pytest.mark.parametrize("source, source_name, sink_name, dumpmode", [
    ('source.txt', Path('source.txt'), Path('source_out.txt'), False),
    ('dump://source_dump.txt', Path('source_dump.txt'), Path('source_dump_out.txt'), True)
])
def test_txt_source(source, source_name, sink_name, dumpmode):  # pylint: disable=unused-variable
    """Test for text file sources."""
    assert list(parse_sources([source])) == [('txt', source_name, sink_name, dumpmode)]


@pytest.mark.parametrize("source, source_name, sink_name, dumpmode", [
    ('source.xlsx', Path('source.xlsx'), Path('source_out.xlsx'), False),
    ('dump://source_dump.xlsx', Path('source_dump.xlsx'), Path('source_dump_out.xlsx'), True)
])
def test_xls_source(source, source_name, sink_name, dumpmode):  # pylint: disable=unused-variable
    """Test for Excel file sources."""
    assert list(parse_sources([source])) == [('xls', source_name, sink_name, dumpmode)]
