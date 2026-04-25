"""Test suite for profiles handling."""
from contextlib import AbstractContextManager, nullcontext
from html.parser import HTMLParser
import re
import subprocess
from textwrap import dedent
from typing import ClassVar, TYPE_CHECKING

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

if TYPE_CHECKING:
    from pathlib import Path


# pylint: disable-next=unused-variable
def test_profiles_missing_ini_file(
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
def test_profiles_unreadable_ini_file(tmp_path: Path) -> None:
    """Test for unreadable profiles configuration file."""
    unreadable_profiles_ini = tmp_path / 'unreadable_profiles_ini'
    unreadable_profiles_ini.write_text('')

    subprocess.run(  # noqa: S603
        ['icacls', str(unreadable_profiles_ini), '/inheritance:r'],  # noqa: S607
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(unreadable_profiles_ini)
    unreadable_profiles_ini.unlink()

    assert str(excinfo.value) == f'No se encontró o no se pudo leer el fichero de perfiles «{unreadable_profiles_ini}».'


@pytest.mark.parametrize('text', [
    pytest.param('', id='test_profiles_empty_ini_file_empty_contents'),
    pytest.param('[s]', id='test_profiles_empty_ini_file_empty_section'),
])
# pylint: disable-next=unused-variable
def test_profiles_empty_ini_file(tmp_path: Path, text: str) -> None:
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
        id='test_profiles_syntax_errors_missing_section_header',
    ),
    pytest.param(
        '[s]\no',
        'Parsing',
        id='test_profiles_syntax_errors_parsing',
    ),
    pytest.param(
        '[s]\no = v\no = v',
        'DuplicateOption',
        id='test_profiles_syntax_errors_duplicate_option',
    ),
    pytest.param(
        '[s]\no = (',
        'BadRegex',
        id='test_profiles_syntax_errors_bad_regex',
    ),
])
# pylint: disable-next=unused-variable
def test_profiles_syntax_errors(tmp_path: Path, text: str, error: str) -> None:
    """Test for syntax errors in profiles configuration file."""
    path = tmp_path / 'profiles_syntax_error.ini'
    path.write_text(text)
    with pytest.raises(ProfilesError) as excinfo:
        load_profiles(path)

    assert str(excinfo.value).startswith(f'Error de sintaxis «{error}» leyendo el fichero de perfiles.')

    path.unlink()


# pylint: disable-next=unused-variable
def test_profiles_parsing(tmp_path: Path) -> None:
    """Test full profile loading."""
    inifile_contents = dedent("""
        [profile_baratz]
        url = profile1.domain.tld
        m_tag = tag
        m_attr = attr
        m_value = value

        [profile_old_regime]
        url = profile2.domain.tld
        k_class = key_class
        v_class = value_class
    """)

    expected_profiles = {
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

    path = tmp_path / 'profiles.ini'
    path.write_text(inifile_contents)

    profiles = load_profiles(path)

    path.unlink()

    assert profiles.keys() == expected_profiles.keys()

    for profile_name, result_profile in profiles.items():
        expected_profile = expected_profiles[profile_name]
        assert result_profile.url_pattern == expected_profile.url_pattern
        assert result_profile.parser_config == expected_profile.parser_config
        assert type(result_profile.parser) is type(expected_profile.parser)


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
        '[bad_extra_keys]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\nk=v\n',
        pytest.raises(ProfilesError),
        id='test_profile_validation_ok_A_parser',
    ),
    pytest.param(
        '[ok_b]\nurl=v\nbkey_1=v\nbkey_2=v\nbkey_3=v\n',
        nullcontext(),
        id='test_profile_validation_ok_B_parser',
    ),
    pytest.param(
        '[ok_a]\nurl=v\nakey_1=v\nakey_2=v\nakey_3=v\n',
        nullcontext(),
        id='test_profile_validation_extra_keys',
    ),
    pytest.param(
        '[bad_missing_keys]\nurl=url\nbkey_1=v\nbkey_2=v\n',
        pytest.raises(ProfilesError),
        id='test_profile_validation_missing_keys',
    ),
    pytest.param(
        '[bad_empty_keys]\nurl=url\nbkey_1=v\nbkey_2=v\nbkey= ',
        pytest.raises(ProfilesError),
        id='test_profile_validation_empty_keys',
    ),
    pytest.param(
        '[bad_different]\nkey_1=url\nkey_2=v\nkey_3=v\n',
        pytest.raises(ProfilesError),
        id='test_profile_validation_wrong_keys',
    ),
])
# pylint: disable-next=unused-variable
def test_profile_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    inifile_contents: str,
    context_manager: AbstractContextManager[None | pytest.ExceptionInfo[ProfilesError]],
) -> None:
    """Test profile validation using declared parsers."""
    monkeypatch.setitem(load_profiles.__globals__, 'BaseParser', MockBaseParser)

    with context_manager:
        inifile_path = tmp_path / 'profiles.ini'
        inifile_path.write_text(inifile_contents)
        load_profiles(inifile_path)
        inifile_path.unlink()


@pytest.mark.parametrize(('url', 'context_manager', 'expected_profile_name'), [
    pytest.param(
        'http://profile1.tld',
        nullcontext(),
        'profile_baratz',
        id='test_get_parser_base_url',
    ),
    pytest.param(
        'http://optional.profile1.tld',
        nullcontext(),
        'profile_baratz',
        id='test_get_parser_optional_subdomain',
    ),
    pytest.param(
        'http://mandatory.profile2.tld',
        nullcontext(),
        'profile_old_regime',
        id='test_get_parser_mandatory_subdomain',
    ),
    pytest.param(
        'http://optional.mandatory.profile2.tld',
        nullcontext(),
        'profile_old_regime',
        id='test_get_parser_full_subdomains',
    ),
    pytest.param(
        'http://optional.forbidden.profile1.tld',
        pytest.raises(SkimmingError),
        None,
        id='test_get_parser_forbidden_url',
    ),
    pytest.param(
        'http://profile2.tld',
        pytest.raises(SkimmingError),
        None,
        id='test_get_parser_no_matching_profile',
    ),
])
# pylint: disable-next=unused-variable
def test_get_parser(
    url: str,
    context_manager: AbstractContextManager[None | pytest.ExceptionInfo[SkimmingError]],
    expected_profile_name: str | None,
) -> None:
    """Test finding parser for *url*."""
    profiles = {
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

    with context_manager as excinfo:
        result = get_parser(url, profiles)

    if excinfo is None:
        assert expected_profile_name is not None
        assert type(result) is type(profiles[expected_profile_name].parser)
    else:
        assert str(excinfo.value) == 'No se encontró un perfil para procesar el URL.'
