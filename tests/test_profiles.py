#! /usr/bin/env python3
"""Test suite for profiles handling."""
from contextlib import nullcontext
from html.parser import HTMLParser
import re

import pytest

from sacamantecas import (
    BaratzParser,
    get_parser,
    INIFILE_PATH,
    load_profiles,
    Messages,
    OldRegimeParser,
    Profile,
    ProfilesError
)


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
def test_empty(tmp_path, text):  # pylint: disable=unused-variable
    """Test for empty profiles configuration file."""
    filename = tmp_path / 'profiles_empty.ini'
    filename.write_text(text)

    assert not load_profiles(str(filename))


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
EXPECTED_PROFILES = {
    'profile1': Profile(
        url_pattern = re.compile(r'profile1.domain.tld', re.IGNORECASE),
        parser = BaratzParser(),
        config = {
            'm_tag': re.compile(r'tag', re.IGNORECASE),
            'm_attr': re.compile(r'attr', re.IGNORECASE),
            'm_value': re.compile(r'value', re.IGNORECASE)
        }
    ),
    'profile2': Profile(
        url_pattern = re.compile(r'profile2.domain.tld', re.IGNORECASE),
        parser = OldRegimeParser(),
        config = {
            'k_class': re.compile(r'key_class', re.IGNORECASE),
            'v_class': re.compile(r'value_class', re.IGNORECASE)
        }
    )
}
def test_profile_loading(tmp_path):  # pylint: disable=unused-variable
    """Test full profile loading."""
    filename = tmp_path / INIFILE_PATH.name
    filename.write_text(INIFILE_CONTENTS)
    profiles = load_profiles(filename)
    filename.unlink()
    for profile_id, profile in profiles.items():
        assert type(profile.parser).__name__ == type(EXPECTED_PROFILES[profile_id].parser).__name__
        # Parser objects will be different, and their type is already checked, so get rid of them.
        EXPECTED_PROFILES[profile_id] = EXPECTED_PROFILES[profile_id]._replace(parser=profile.parser)
    assert profiles == EXPECTED_PROFILES


class BaseParser(HTMLParser):
    """Mock base parser."""
    PARAMETERS = set()
class AParser(BaseParser):  # pylint: disable=unused-variable
    """Mock 'Type A' parser."""
    PARAMETERS = BaseParser.PARAMETERS | {'akey_1', 'akey_2', 'akey_3'}
class BParser(BaseParser):  # pylint: disable=unused-variable
    """Mock 'Type B' parser."""
    PARAMETERS = BaseParser.PARAMETERS | {'bkey_1', 'bkey_2', 'bkey_3'}
@pytest.mark.parametrize('inifile_contents, exception', [
    ('[ok_a]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\n', nullcontext()),
    ('[ok_b]\nurl=v\nbkey_1=v\nbkey_2=v\nbkey_3=v\n', nullcontext()),
    ('[bad_extra_keys]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\nk=v\n', pytest.raises(ProfilesError)),
    ('[bad_missing_keys]\nurl=url\nbkey_1=v\nbkey_2=v\n', pytest.raises(ProfilesError)),
    ('[bad_empty_keys]\nurl=url\nbkey_1=v\nbkey_2=v\nbkey= ', pytest.raises(ProfilesError)),
    ('[bad_different]\nkey_1=url\nkey_2=v\nkey_3=v\n', pytest.raises(ProfilesError)),
])
def test_profile_validation(monkeypatch, tmp_path, inifile_contents, exception):  # pylint: disable=unused-variable
    """Test profile validation using declared parsers."""
    monkeypatch.setattr('sacamantecas.BaseParser', BaseParser)
    with exception:
        inifile = tmp_path / INIFILE_PATH.name
        inifile.write_text(inifile_contents)
        load_profiles(inifile)
        inifile.unlink()


PROFILES = {
    'profile1': Profile(
        url_pattern = re.compile(r'(optional\.)?(?<!forbidden\.)profile1\.tld', re.IGNORECASE),
        parser = BaratzParser(),
        config = {
            'm_tag': re.compile(r'tag', re.IGNORECASE),
            'm_attr': re.compile(r'attr', re.IGNORECASE),
            'm_value': re.compile(r'value', re.IGNORECASE)
        }
    ),
    'profile2': Profile(
        url_pattern = re.compile(r'(optional\.)?mandatory\.profile2\.tld', re.IGNORECASE),
        parser = OldRegimeParser(),
        config = {
            'k_class': re.compile(r'key_class', re.IGNORECASE),
            'v_class': re.compile(r'value_class', re.IGNORECASE)
        }
    )
}
@pytest.mark.parametrize('url, expected', [
    ('http://profile1.tld', PROFILES['profile1']),
    ('http://optional.profile1.tld', PROFILES['profile1']),
    ('http://mandatory.profile2.tld', PROFILES['profile2']),
    ('http://optional.mandatory.profile2.tld', PROFILES['profile2']),
    ('http://optional.forbidden.profile1.tld', Profile(None, None, None)),
    ('http://profile2.tld', Profile(None, None, None)),
])
def test_get_url_parser(url, expected):  # pylint: disable=unused-variable
    """Test finding parser for URL."""
    result = get_parser(url, PROFILES)
    assert type(result).__name__ == type(expected.parser).__name__
