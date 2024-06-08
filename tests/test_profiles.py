#! /usr/bin/env python3
"""Test suite for profiles handling."""
from contextlib import AbstractContextManager, nullcontext
from html.parser import HTMLParser
from pathlib import Path
import re

import pytest

from sacamantecas import (
    BaseParser,
    BaratzParser,
    Constants,
    get_parser,
    load_profiles,
    Messages,
    OldRegimeParser,
    Profile,
    ProfilesError
)


def test_missing(tmp_path: Path) -> None: # pylint: disable=unused-variable
    """Test for missing profiles configuration file."""
    filename = tmp_path / 'non_existent.ini'
    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(filename)
    assert str(excinfo.value) == Messages.MISSING_PROFILES.format(filename)


@pytest.mark.parametrize('unreadable_file', ['unreadable_profiles.ini'])
def test_unreadable(unreadable_file: Path) -> None:  # pylint: disable=unused-variable
    """Test for unreadable profiles configuration file."""
    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(unreadable_file)
    assert str(excinfo.value) == Messages.MISSING_PROFILES.format(unreadable_file)


@pytest.mark.parametrize('text', ['', '[s]'])
def test_empty(tmp_path: Path, text: str) -> None:  # pylint: disable=unused-variable
    """Test for empty profiles configuration file."""
    filename = tmp_path / 'profiles_empty.ini'
    filename.write_text(text)

    assert not load_profiles(filename)


@pytest.mark.parametrize('text, error', [
    ('o', 'MissingSectionHeader'),
    ('[s]\no', 'Parsing'),
    ('[s]\no = v\no = v', 'DuplicateOption'),
    ('[s]\no = (', 'BadRegex')
])
def test_syntax_errors(tmp_path: Path, text: str, error: str) -> None:  # pylint: disable=unused-variable
    """Test for syntax errors in profiles configuration file."""
    filename = tmp_path / 'profiles_syntax_error.ini'
    filename.write_text(text)

    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(filename)
    assert str(excinfo.value).startswith(Messages.PROFILES_WRONG_SYNTAX.format(error))

    filename.unlink()


# cspell: ignore baratz
INIFILE_CONTENTS = """
[profile_baratz]
url = profile1.domain.tld
m_tag = tag
m_attr = attr
m_value = value

[profile_old_regime]
url = profile2.domain.tld
k_class = key_class
v_class = value_class
"""
EXPECTED_PROFILES = {
    'profile_baratz': Profile(
        url_pattern = re.compile(r'profile1.domain.tld', re.IGNORECASE),
        parser = BaratzParser(),
        parser_config = {
            'm_tag': re.compile(r'tag', re.IGNORECASE),
            'm_attr': re.compile(r'attr', re.IGNORECASE),
            'm_value': re.compile(r'value', re.IGNORECASE)
        }
    ),
    'profile_old_regime': Profile(
        url_pattern = re.compile(r'profile2.domain.tld', re.IGNORECASE),
        parser = OldRegimeParser(),
        parser_config = {
            'k_class': re.compile(r'key_class', re.IGNORECASE),
            'v_class': re.compile(r'value_class', re.IGNORECASE)
        }
    )
}
def test_profile_loading(tmp_path: Path) -> None:   # pylint: disable=unused-variable
    """Test full profile loading."""
    filename = tmp_path / Constants.INIFILE_PATH.name
    filename.write_text(INIFILE_CONTENTS)
    profiles = load_profiles(filename)
    filename.unlink()
    assert profiles == EXPECTED_PROFILES


class MockBaseParser(HTMLParser):
    """Mock base parser."""
    PARAMETERS: set[str] = set()
class AParser(MockBaseParser):  # pylint: disable=unused-variable
    """Mock 'Type A' parser."""
    PARAMETERS = MockBaseParser.PARAMETERS | {'akey_1', 'akey_2', 'akey_3'}
class BParser(MockBaseParser):  # pylint: disable=unused-variable
    """Mock 'Type B' parser."""
    PARAMETERS = MockBaseParser.PARAMETERS | {'bkey_1', 'bkey_2', 'bkey_3'}
@pytest.mark.parametrize('inifile_contents, context_manager', [
    ('[ok_a]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\n', nullcontext()),
    ('[ok_b]\nurl=v\nbkey_1=v\nbkey_2=v\nbkey_3=v\n', nullcontext()),
    ('[bad_extra_keys]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\nk=v\n', pytest.raises(ProfilesError)),
    ('[bad_missing_keys]\nurl=url\nbkey_1=v\nbkey_2=v\n', pytest.raises(ProfilesError)),
    ('[bad_empty_keys]\nurl=url\nbkey_1=v\nbkey_2=v\nbkey= ', pytest.raises(ProfilesError)),
    ('[bad_different]\nkey_1=url\nkey_2=v\nkey_3=v\n', pytest.raises(ProfilesError)),
])
# pylint: disable-next=unused-variable
def test_profile_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    inifile_contents: str,
    context_manager: AbstractContextManager[None | Exception]
) -> None:
    """Test profile validation using declared parsers."""
    monkeypatch.setattr('sacamantecas.BaseParser', MockBaseParser)

    with context_manager:
        inifile = tmp_path / Constants.INIFILE_PATH.name
        inifile.write_text(inifile_contents)
        load_profiles(inifile)
        inifile.unlink()


PROFILES = {
    'profile_baratz': Profile(
        url_pattern = re.compile(r'(optional\.)?(?<!forbidden\.)profile1\.tld', re.IGNORECASE),
        parser = BaratzParser(),
        parser_config = {
            'm_tag': re.compile(r'tag', re.IGNORECASE),
            'm_attr': re.compile(r'attr', re.IGNORECASE),
            'm_value': re.compile(r'value', re.IGNORECASE)
        }
    ),
    'profile_old_regime': Profile(
        url_pattern = re.compile(r'(optional\.)?mandatory\.profile2\.tld', re.IGNORECASE),
        parser = OldRegimeParser(),
        parser_config = {
            'k_class': re.compile(r'key_class', re.IGNORECASE),
            'v_class': re.compile(r'value_class', re.IGNORECASE)
        }
    ),
}
class NoneProfile(Profile):  # pylint: disable=too-few-public-methods
    """Mock profile for non-matching URLs."""
    def __init__(self) -> None:
        super().__init__(re.compile(''), BaseParser(), {})
        self.url_pattern = None
        self.parser = None
        self.parser_config = None
@pytest.mark.parametrize('url, expected', [
    ('http://profile1.tld', PROFILES['profile_baratz']),
    ('http://optional.profile1.tld', PROFILES['profile_baratz']),
    ('http://mandatory.profile2.tld', PROFILES['profile_old_regime']),
    ('http://optional.mandatory.profile2.tld', PROFILES['profile_old_regime']),
    ('http://optional.forbidden.profile1.tld', NoneProfile()),
    ('http://profile2.tld', NoneProfile()),
])
def test_get_url_parser(url: str, expected: Profile) -> None:  # pylint: disable=unused-variable
    """Test finding parser for URL."""
    result = get_parser(url, PROFILES)
    assert type(result).__name__ == type(expected.parser).__name__
