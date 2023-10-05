#! /usr/bin/env python3
"""Test suite for uri_to_filename()."""

from sacamantecas import uri_to_filename


def test_uri_to_filename():  # pylint: disable=unused-variable
    """Test URI to filename conversion."""
    result = uri_to_filename('uri://subdomain.domain.toplevel/path?param1=value1&param2=value2')
    expected = 'uri___subdomain_domain_toplevel_path_param1_value1_param2_value2'

    assert result == expected
