#! /usr/bin/env python3
"""Test suite for metadata parsers."""

from sacamantecas import BaseParser

INPUT_DATA = ''
EXPECTED = {}
def test_base_parser_parsing():  # pylint: disable=unused-variable
    """Test the basic functionality of BaseParser."""
    parser = BaseParser()
    parser.feed(INPUT_DATA)
    result = parser.get_metadata()
    assert result == EXPECTED


EMPTY_METADATA = {}
def test_parser_reset():  # pylint: disable=unused-variable
    """Test parser state after a reset."""
    parser = BaseParser()
    parser.feed(INPUT_DATA)
    parser.reset()
    result = parser.get_metadata()
    assert result == EMPTY_METADATA
