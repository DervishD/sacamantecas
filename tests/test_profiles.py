#! /usr/bin/env python3
"""Test suite for profiles handling."""
from contextlib import nullcontext
from pathlib import Path
import re

import pytest

from sacamantecas import INIFILE_PATH, load_profiles, Messages, validate_profiles, ProfilesError


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
    assert str(excinfo.value).startswith(Messages.PROFILES_WRONG_SYNTAX.format(error))

    filename.unlink()


INIFILE_CONTENTS = """
[profile1]
url = profile1.domain.tld
m_tag = tag
m_attr = attr
m_value = value

[profile2]
url = profile2.domain.tld
k_class = key_class
v_class = value_class
"""
EXPECTED_PROFILES_DICT = {
    'profile1': {
        'url': re.compile(r'profile1.domain.tld', re.IGNORECASE),
        'm_tag': re.compile(r'tag', re.IGNORECASE),
        'm_attr': re.compile(r'attr', re.IGNORECASE),
        'm_value': re.compile(r'value', re.IGNORECASE),
    },
    'profile2': {
        'url': re.compile(r'profile2.domain.tld', re.IGNORECASE),
        'k_class': re.compile(r'key_class', re.IGNORECASE),
        'v_class': re.compile(r'value_class', re.IGNORECASE),
    }
}
def test_profile_loading(tmp_path):  # pylint: disable=unused-variable
    """Test full profile loading."""
    filename = tmp_path / INIFILE_PATH.name
    filename.write_text(INIFILE_CONTENTS)
    profiles = load_profiles(filename)
    filename.unlink()
    assert profiles == EXPECTED_PROFILES_DICT


PROFILE_SCHEMAS = (
    {'id': 'Schema A', 'keys': ('url', 'akey_1', 'akey_2', 'akey_3'), 'parser': None},
    {'id': 'Schema B', 'keys': ('url', 'bkey_1', 'bkey_2', 'bkey_3'), 'parser': None},
)
@pytest.mark.parametrize('profiles, exception', [
    ({'ok_a': {'url': '', 'akey_1': '','akey_2': '', 'akey_3': ''}}, nullcontext()),
    ({'ok_b': {'url': '', 'bkey_1': '','bkey_2': '', 'bkey_3': ''}}, nullcontext()),
    ({'bad_extra_keys': {'url': '', 'akey_1': '','akey_2': '', 'akey_3': '', 'k': ''}}, pytest.raises(ProfilesError)),
    ({'bad_missing_keys': {'url': '', 'bkey_1': '','bkey_2': ''}}, pytest.raises(ProfilesError)),
    ({'bad_different': {'key1': '', 'key2': '', 'key3': ''}}, pytest.raises(ProfilesError))
])
def test_schemas(monkeypatch, profiles, exception):  # pylint: disable=unused-variable
    """Test profile validation using schemas."""
    monkeypatch.setattr('sacamantecas.PROFILE_SCHEMAS', PROFILE_SCHEMAS)
    with exception:
        validate_profiles(profiles)
