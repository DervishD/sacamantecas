#! /usr/bin/env python3
"""Test suite for url_to_filename()."""
from pathlib import Path

from sacamantecas import url_to_filename


def test_url_to_filename():  # pylint: disable=unused-variable
    """Test URL to filename conversion."""
    result = url_to_filename('url://subdomain.domain.toplevel/path?param1=value1&param2=value2')
    expected = Path('url___subdomain_domain_toplevel_path_param1_value1_param2_value2')

    assert result == expected
