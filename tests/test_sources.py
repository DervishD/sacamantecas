#! /usr/bin/env python3
"""Test suite for the different sources."""
import sacamantecas as sm


def test_single_url():  # pylint: disable=unused-variable
    """Test single URL sources."""
    url = 'url://sample.url'
    source = sm.SingleURLSource(url)

    assert list(source.get_urls()) == [url,]
