#! /usr/bin/env python3
"""Test suite for the different sources."""
import sacamantecas as sm


def test_text_file(tmp_path):  # pylint: disable=unused-variable
    """Test text files containing URLs."""
    expected = [
        'url://sampleɑ.url',
        'url://sampleö.url',
        'url://sampleω.url',
    ]
    source_file = tmp_path / 'sample.txt'
    source_file.write_text('\n'.join(expected), encoding='utf-8')
    source = sm.TextURLSource(source_file)
    assert list(source.get_urls()) == expected


def test_single_url():  # pylint: disable=unused-variable
    """Test single URL sources."""
    url = 'url://sample.url'
    source = sm.SingleURLSource(url)

    assert list(source.get_urls()) == [url,]
