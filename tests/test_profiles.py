#! /usr/bin/env python3
"""Test suite for profiles handling."""
from pathlib import Path
import re

import pytest

from sacamantecas import INIFILE_PATH, load_profiles, Messages, ProfilesError


def test_missing(tmp_path):  # pylint: disable=unused-variable
    """Test for missing profiles configuration file."""
    filename = str(tmp_path / 'non_existent.ini')
    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(filename)
    assert str(excinfo.value) == Messages.MISSING_PROFILES.format(filename)


@pytest.mark.parametrize('unreadable_file', ['unreadable_profiles.ini'])
def test_unreadable(unreadable_file):  # pylint: disable=unused-variable
    """Test for unreadable profiles configuration file."""
    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(str(unreadable_file))
    assert str(excinfo.value) == Messages.MISSING_PROFILES.format(unreadable_file)


@pytest.mark.parametrize('text', ['', '[s]'])
def test_empty(tmp_path: Path, text: str) -> None:  # pylint: disable=unused-variable
    """Test for empty profiles configuration file."""
    filename = tmp_path / 'profiles_empty.ini'
    filename.write_text(text)

    assert load_profiles(str(filename)) == {}


@pytest.mark.parametrize('text, error', [
    ('o', 'MissingSectionHeader'),
    ('[s]\no', 'Parsing'),
    ('[s]\no = v\no = v', 'DuplicateOption'),
    ('[s]\no = (', 'BadRegex')
])
def test_syntax_errors(tmp_path, text, error):  # pylint: disable=unused-variable
    """Test for syntax errors in profiles configuration file."""
    filename = tmp_path / 'profiles_syntax_error.ini'
    filename.write_text(text)

    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(str(filename))
    assert str(excinfo.value).startswith(Messages.PROFILES_WRONG_SYNTAX.format(error, ''))

    filename.unlink()


INIFILE_CONTENTS = """
[profile1]
url = profile1.domain.tld
m_tag = tag
m_attr = attr
m_value = value

[profile2]
url = profile1.domain.tld
k_class = key_class
v_class = value_class
"""
EXPECTED_PROFILES_DICT = {
    'profile1': {
        'url': re.compile('profile1.domain.tld', re.IGNORECASE),
        'm_tag': re.compile('tag', re.IGNORECASE),
        'm_attr': re.compile('attr', re.IGNORECASE),
        'm_value': re.compile('value', re.IGNORECASE),
    },
   'profile2': {
        'url': re.compile('profile1.domain.tld', re.IGNORECASE),
        'k_class': re.compile('key_class', re.IGNORECASE),
        'v_class': re.compile('value_class', re.IGNORECASE),
    }
}
def test_profile_loading(tmp_path):  # pylint: disable=unused-variable
    """Test full profile loading."""
    filename = tmp_path / INIFILE_PATH.name
    filename.write_text(INIFILE_CONTENTS)
    profiles = load_profiles(filename)
    filename.unlink()
    assert profiles == EXPECTED_PROFILES_DICT
