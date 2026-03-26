#! /usr/bin/env python3
"""Test suite for profiles handling."""
from contextlib import AbstractContextManager, nullcontext
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import ClassVar

import pytest

from sacamantecas import (
    BaratzParser,
    Constants,
    ExitCodes,
    get_parser,
    load_profiles,
    main,
    OldRegimeParser,
    Profile,
    ProfilesError,
    SkimmingError,
)


# pylint: disable-next=unused-variable
def test_missing_ini_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test for missing main INI file."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    path = tmp_path / 'non_existent.ini'

    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(path)

    assert str(excinfo.value) == f'No se encontró o no se pudo leer el fichero de perfiles «{path}».'

    monkeypatch.setattr(Constants, 'INIFILE_PATH', path)

    assert main('') == ExitCodes.ERROR

    result = '\n'.join(capsys.readouterr().err.split('\n')[0:2])
    expected = f'\n*** Error: no se encontró o no se pudo leer el fichero de perfiles «{path}».'

    assert result == expected


# pylint: disable-next=unused-variable
def test_ini_syntax_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test for syntax errors in INI file."""
    monkeypatch.setattr(Constants, 'MAIN_OUTPUT_PATH', None)
    monkeypatch.setattr(Constants, 'FULL_OUTPUT_PATH', None)

    path = tmp_path / 'profiles_syntax_error.ini'
    path.write_text('o')
    monkeypatch.setattr(Constants, 'INIFILE_PATH', path)

    assert main('') == ExitCodes.ERROR

    result = '\n'.join(capsys.readouterr().err.split('\n')[0:2])
    expected = '\n*** Error: error de sintaxis «MissingSectionHeader» leyendo el fichero de perfiles.'

    assert result == expected

    path.unlink()


@pytest.mark.parametrize('unreadable_path', [
    Path('unreadable_profiles.ini'),
], ids=[
    'test_unreadable_ini_file',
], indirect=True)
def test_unreadable_ini_file(unreadable_path: Path) -> None:  # pylint: disable=unused-variable
    """Test for unreadable profiles configuration file."""
    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(unreadable_path)

    assert str(excinfo.value) == f'No se encontró o no se pudo leer el fichero de perfiles «{unreadable_path}».'


@pytest.mark.parametrize('text', [
    pytest.param('', id='test_totally_empty_ini_file'),
    pytest.param('[s]', id='test_section_empty_ini_file'),
])
def test_empty(tmp_path: Path, text: str) -> None:  # pylint: disable=unused-variable
    """Test for empty profiles configuration file."""
    path = tmp_path / 'profiles_empty.ini'
    path.write_text(text)

    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(path)

    assert str(excinfo.value) == f'No hay perfiles definidos en el fichero de perfiles «{path}».'


@pytest.mark.parametrize(('text', 'error'), [
    pytest.param(
        'o',
        'MissingSectionHeader',
        id='test_ini_file_missing_section_header_error',
    ),
    pytest.param(
        '[s]\no',
        'Parsing',
        id='test_ini_file_parsing_error',
    ),
    pytest.param(
        '[s]\no = v\no = v',
        'DuplicateOption',
        id='test_ini_file_duplicate_option_error',
    ),
    pytest.param(
        '[s]\no = (',
        'BadRegex',
        id='test_ini_file_bad_regex_error',
    ),
])
def test_syntax_errors(tmp_path: Path, text: str, error: str) -> None:  # pylint: disable=unused-variable
    """Test for syntax errors in profiles configuration file."""
    path = tmp_path / 'profiles_syntax_error.ini'
    path.write_text(text)
    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(path)

    assert str(excinfo.value).startswith(f'Error de sintaxis «{error}» leyendo el fichero de perfiles.')

    path.unlink()


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
            'm_value': re.compile(r'value', re.IGNORECASE),
        },
    ),
    'profile_old_regime': Profile(
        url_pattern = re.compile(r'profile2.domain.tld', re.IGNORECASE),
        parser = OldRegimeParser(),
        parser_config = {
            'k_class': re.compile(r'key_class', re.IGNORECASE),
            'v_class': re.compile(r'value_class', re.IGNORECASE),
        },
    ),
}
def test_profile_loading(tmp_path: Path) -> None:   # pylint: disable=unused-variable
    """Test full profile loading."""
    path = tmp_path / 'profiles.ini'
    path.write_text(INIFILE_CONTENTS)

    profiles = load_profiles(path)

    path.unlink()

    assert profiles.keys() == EXPECTED_PROFILES.keys()

    for profile_name, result_profile in profiles.items():
        expected_profile = EXPECTED_PROFILES[profile_name]
        assert result_profile.url_pattern == expected_profile.url_pattern
        assert result_profile.parser_config == expected_profile.parser_config
        # pylint: disable-next=unidiomatic-typecheck
        assert type(result_profile.parser) == type(expected_profile.parser)  # noqa: E721


class MockBaseParser(HTMLParser):
    """Mock base parser."""  # noqa: D204
    PARAMETERS: ClassVar[set[str]] = set()
class AParser(MockBaseParser):  # pylint: disable=unused-variable
    """Mock `Type A` parser."""  # noqa: D204
    PARAMETERS = MockBaseParser.PARAMETERS | {'akey_1', 'akey_2', 'akey_3'}
class BParser(MockBaseParser):  # pylint: disable=unused-variable
    """Mock `Type B` parser."""  # noqa: D204
    PARAMETERS = MockBaseParser.PARAMETERS | {'bkey_1', 'bkey_2', 'bkey_3'}
@pytest.mark.parametrize(('inifile_contents', 'context_manager'), [
    pytest.param(
        '[ok_a]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\n',
        nullcontext(),
        id='test_extra_keys_profile',
    ),
    pytest.param(
        '[ok_b]\nurl=v\nbkey_1=v\nbkey_2=v\nbkey_3=v\n',
        nullcontext(),
        id='test_ok_B_parser_profile',
    ),
    pytest.param(
        '[bad_extra_keys]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\nk=v\n',
        pytest.raises(ProfilesError),
        id='test_ok_A_parser_profile',
    ),
    pytest.param(
        '[bad_missing_keys]\nurl=url\nbkey_1=v\nbkey_2=v\n',
        pytest.raises(ProfilesError),
        id='test_missing_keys_profile',
    ),
    pytest.param(
        '[bad_empty_keys]\nurl=url\nbkey_1=v\nbkey_2=v\nbkey= ',
        pytest.raises(ProfilesError),
        id='test_empty_keys_profile',
    ),
    pytest.param(
        '[bad_different]\nkey_1=url\nkey_2=v\nkey_3=v\n',
        pytest.raises(ProfilesError),
        id='test_wrong_keys_profile',
    ),
])
# pylint: disable-next=unused-variable
def test_profile_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    inifile_contents: str,
    context_manager: AbstractContextManager[None | Exception],
) -> None:
    """Test profile validation using declared parsers."""
    monkeypatch.setitem(load_profiles.__globals__, 'BaseParser', MockBaseParser)

    with context_manager:
        inifile_path = tmp_path / 'profiles.ini'
        inifile_path.write_text(inifile_contents)
        load_profiles(inifile_path)
        inifile_path.unlink()


PROFILES = {
    'profile_baratz': Profile(
        url_pattern = re.compile(r'(optional\.)?(?<!forbidden\.)profile1\.tld', re.IGNORECASE),
        parser = BaratzParser(),
        parser_config = {
            'm_tag': re.compile(r'tag', re.IGNORECASE),
            'm_attr': re.compile(r'attr', re.IGNORECASE),
            'm_value': re.compile(r'value', re.IGNORECASE),
        },
    ),
    'profile_old_regime': Profile(
        url_pattern = re.compile(r'(optional\.)?mandatory\.profile2\.tld', re.IGNORECASE),
        parser = OldRegimeParser(),
        parser_config = {
            'k_class': re.compile(r'key_class', re.IGNORECASE),
            'v_class': re.compile(r'value_class', re.IGNORECASE),
        },
    ),
}


@pytest.mark.parametrize(('url', 'expected'), [
    pytest.param(
        'http://profile1.tld',
        PROFILES['profile_baratz'].parser,
        id='test_get_parser_base_url',
    ),
    pytest.param(
        'http://optional.profile1.tld',
        PROFILES['profile_baratz'].parser,
        id='test_get_parser_url_with_optional',
    ),
    pytest.param(
        'http://mandatory.profile2.tld',
        PROFILES['profile_old_regime'].parser,
        id='test_get_parser_url_with_mandatory',
    ),
    pytest.param(
        'http://optional.mandatory.profile2.tld',
        PROFILES['profile_old_regime'].parser,
        id='test_get_parser_url_with_both',
    ),
])
def test_get_url_parser(url: str, expected: Profile) -> None:  # pylint: disable=unused-variable
    """Test finding parser for *url*."""
    result = get_parser(url, PROFILES)

    assert type(result) is type(expected)


@pytest.mark.parametrize('url', [
    pytest.param('http://profile2.tld', id='test_no_profile_base_url'),
    pytest.param('http://optional.forbidden.profile1.tld', id='test_no_profile_url_with_forbidden'),
])
def test_no_matching_profile(url: str) -> None:  # pylint: disable=unused-variable
    """Test *url* with no matching profile (no parser)."""
    with pytest.raises(SkimmingError) as excinfo:
        get_parser(url, PROFILES)

    assert str(excinfo.value) == 'No se encontró un perfil para procesar el URL.'
