"""Test suite for program configuration (the INI file)."""

from pathlib import Path
import re
from typing import NoReturn

import pytest

from sacamantecas import (
    BaratzParser,
    BaseParser,
    IniFileError,
    load_inifile,
    Messages,
    OldRegimeParser,
    parse_profiles,
    parse_settings,
    ParserConfig,
    ProfileError,
    Settings,
    SettingsError,
)


@pytest.mark.parametrize(('contents', 'expected'), [
    pytest.param(
        {'url_retrieval_timeout_seconds': '7', 'max_url_redirections': '3'},
        Settings(url_retrieval_timeout_seconds=7, max_url_redirections=3),
        id='all_settings',
    ),
    pytest.param(
        {'url_retrieval_timeout_seconds': '7'},
        Settings(url_retrieval_timeout_seconds=7),
        id='timeout_only',
    ),
    pytest.param(
        {'max_url_redirections': '3'},
        Settings(max_url_redirections=3),
        id='redirections_only',
    ),
    pytest.param(
        {},
        Settings(),
        id='no_settings',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_settings(contents: dict[str, str], expected: Settings) -> None:
    """Test the parsing of valid settings."""
    assert parse_settings(contents) == expected


SAMPLE_K = 'sample_k'
SAMPLE_V = 'sample_v'
@pytest.mark.parametrize(('contents', 'expected'), [
    # Unknown settings.
    pytest.param(
        {SAMPLE_K: '1'},
        Messages.SETTINGS_ERROR_UNKNOWN_KEYS.format(Messages.QUOTED.format(SAMPLE_K)),
        id='unknown_1',
    ),
    pytest.param(
        {SAMPLE_K: '1', f'o{SAMPLE_K}': '1'},
        Messages.SETTINGS_ERROR_UNKNOWN_KEYS.format(
            Messages.LIST_SEPARATOR.join((Messages.QUOTED.format(SAMPLE_K), Messages.QUOTED.format(f'o{SAMPLE_K}'))),
        ),
        id='unknown_2',
    ),
    pytest.param(
        {'max_url_redirections': '3', SAMPLE_K: '1'},
        Messages.SETTINGS_ERROR_UNKNOWN_KEYS.format(Messages.QUOTED.format(SAMPLE_K)),
        id='unknown_and_valid',
    ),
    pytest.param(
        {'max_url_redirections': SAMPLE_V, SAMPLE_K: '1'},
        Messages.SETTINGS_ERROR_UNKNOWN_KEYS.format(Messages.QUOTED.format(SAMPLE_K)),
        id='unknown_and_invalid',
    ),

    # Invalid values.
    pytest.param(
        {'url_retrieval_timeout_seconds': SAMPLE_V},
        Messages.SETTINGS_ERROR_INVALID_VALUE.format('url_retrieval_timeout_seconds', SAMPLE_V),
        id='text',
    ),
    pytest.param(
        {'url_retrieval_timeout_seconds': ''},
        Messages.SETTINGS_ERROR_INVALID_VALUE.format('url_retrieval_timeout_seconds', ''),
        id='empty',
    ),
    pytest.param(
        {'url_retrieval_timeout_seconds': '1.5'},
        Messages.SETTINGS_ERROR_INVALID_VALUE.format('url_retrieval_timeout_seconds', '1.5'),
        id='float',
    ),
    pytest.param(
        {'url_retrieval_timeout_seconds': SAMPLE_V, 'max_url_redirections': f'o{SAMPLE_V}'},
        Messages.SETTINGS_ERROR_INVALID_VALUE.format('url_retrieval_timeout_seconds', SAMPLE_V),
        id='first_invalid',
    ),
    pytest.param(
        {'url_retrieval_timeout_seconds': '7', 'max_url_redirections': SAMPLE_V},
        Messages.SETTINGS_ERROR_INVALID_VALUE.format('max_url_redirections', SAMPLE_V),
        id='second_invalid',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_settings_errors(contents: dict[str, str], expected: str) -> None:
    """Test the errors raised for invalid settings."""
    with pytest.raises(SettingsError) as exc_info:
        parse_settings(contents)

    assert str(exc_info.value) == expected


type ProfileSummary = tuple[str, re.Pattern[str], type[BaseParser], ParserConfig]

OLD_REGIME_PROFILE_NAME = 'old_regime_sample_profile'
OLD_REGIME_URL_PATTERN = 'old_regime_url_pattern'
OLD_REGIME_CONTENTS = {
    'url': OLD_REGIME_URL_PATTERN,
    OldRegimeParser.K_CLASS: 'sample_k_pattern',
    OldRegimeParser.V_CLASS: 'sample_v_pattern',
}
OLD_REGIME_PROFILE = (
    OLD_REGIME_PROFILE_NAME,
    re.compile(OLD_REGIME_CONTENTS['url'], re.IGNORECASE),
    OldRegimeParser,
    {
        OldRegimeParser.K_CLASS: re.compile(OLD_REGIME_CONTENTS[OldRegimeParser.K_CLASS], re.IGNORECASE),
        OldRegimeParser.V_CLASS: re.compile(OLD_REGIME_CONTENTS[OldRegimeParser.V_CLASS], re.IGNORECASE),
    },
)
BARATZ_PROFILE_NAME = 'baratz_sample_profile'
BARATZ_URL_PATTERN = 'baratz_url_pattern'
BARATZ_CONTENTS = {
    'url': BARATZ_URL_PATTERN,
    BaratzParser.M_TAG: 'sample_tag_pattern',
    BaratzParser.M_ATTR: 'sample_attr_pattern',
    BaratzParser.M_VALUE: 'sample_value_pattern',
}
BARATZ_PROFILE = (
    BARATZ_PROFILE_NAME,
    re.compile(BARATZ_CONTENTS['url'], re.IGNORECASE),
    BaratzParser,
    {
        BaratzParser.M_TAG: re.compile(BARATZ_CONTENTS[BaratzParser.M_TAG], re.IGNORECASE),
        BaratzParser.M_ATTR: re.compile(BARATZ_CONTENTS[BaratzParser.M_ATTR], re.IGNORECASE),
        BaratzParser.M_VALUE: re.compile(BARATZ_CONTENTS[BaratzParser.M_VALUE], re.IGNORECASE),
    },
)


@pytest.mark.parametrize(('contents', 'expected'), [
    pytest.param(
        {},
        [],
        id='no_profiles',
    ),
    pytest.param(
        {OLD_REGIME_PROFILE_NAME: OLD_REGIME_CONTENTS},
        [OLD_REGIME_PROFILE],
        id='old_regime',
    ),
    pytest.param(
        {BARATZ_PROFILE_NAME: BARATZ_CONTENTS},
        [BARATZ_PROFILE],
        id='baratz',
    ),
    pytest.param(
        {BARATZ_PROFILE_NAME: BARATZ_CONTENTS, OLD_REGIME_PROFILE_NAME: OLD_REGIME_CONTENTS},
        [BARATZ_PROFILE, OLD_REGIME_PROFILE],
        id='two_profiles',
    ),
    pytest.param(
        {OLD_REGIME_PROFILE_NAME: {**OLD_REGIME_CONTENTS, BaratzParser.M_TAG: ''}},
        [OLD_REGIME_PROFILE],
        id='empty_pattern_ignored',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_profiles(contents: dict[str, dict[str, str]], expected: list[ProfileSummary]) -> None:
    """Test the parsing of valid profiles."""
    actual = [
        (profile.name, profile.url_pattern, type(profile.parser), profile.parser_config)
        for profile in parse_profiles(contents)
    ]

    assert actual == expected


PROFILE_NAME = 'sample_profile_name'
OTHER_PROFILE_NAME = 'other_sample_profile_name'
URL_PATTERN = 'sample_url_pattern'
K_PATTERN = 'sample_k_pattern'
V_PATTERN = 'sample_v_pattern'
EXTRA_PATTERN = 'sample_x_pattern'
BARATZ_PARAMETERS = {
    BaratzParser.M_TAG: EXTRA_PATTERN,
    BaratzParser.M_ATTR: EXTRA_PATTERN,
    BaratzParser.M_VALUE: EXTRA_PATTERN,
}


@pytest.mark.parametrize(('contents', 'expected'), [
    # Empty profile.
    pytest.param(
        {PROFILE_NAME: {}},
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(PROFILE_NAME),
        id='empty_profile',
    ),

    # Missing URL pattern.
    pytest.param(
        {PROFILE_NAME: {OldRegimeParser.K_CLASS: K_PATTERN, OldRegimeParser.V_CLASS: V_PATTERN}},
        Messages.PROFILE_ERROR_PROFILE_WITHOUT_URL.format(PROFILE_NAME),
        id='no_url',
    ),
    pytest.param(
        {PROFILE_NAME: {**OLD_REGIME_CONTENTS, 'url': ''}},
        Messages.PROFILE_ERROR_PROFILE_WITHOUT_URL.format(PROFILE_NAME),
        id='empty_url',
    ),

    # Parameters not matching any parser.
    pytest.param(
        {PROFILE_NAME: {'url': URL_PATTERN}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(PROFILE_NAME),
        id='only_url',
    ),
    pytest.param(
        {PROFILE_NAME: {'url': URL_PATTERN, OldRegimeParser.K_CLASS: K_PATTERN}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(PROFILE_NAME),
        id='missing_parameter',
    ),
    pytest.param(
        {PROFILE_NAME: {**OLD_REGIME_CONTENTS, 'nope': EXTRA_PATTERN}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(PROFILE_NAME),
        id='unknown_parameter',
    ),
    pytest.param(
        {PROFILE_NAME: {**OLD_REGIME_CONTENTS, **BARATZ_PARAMETERS}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(PROFILE_NAME),
        id='mixed_parameters',
    ),

    # Several profiles.
    pytest.param(
        {PROFILE_NAME: OLD_REGIME_CONTENTS, OTHER_PROFILE_NAME: {}},
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(OTHER_PROFILE_NAME),
        id='second_profile',
    ),
    pytest.param(
        {PROFILE_NAME: {}, OTHER_PROFILE_NAME: {'url': URL_PATTERN}},
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(PROFILE_NAME),
        id='first_error',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_profiles_errors(contents: dict[str, dict[str, str]], expected: str) -> None:
    """Test the errors raised for invalid profiles."""
    with pytest.raises(ProfileError) as exc_info:
        parse_profiles(contents)

    assert str(exc_info.value) == expected


@pytest.mark.parametrize(('key', 'pattern'), [
    pytest.param(
        'url',
        '(',
        id='url_pos_0',
    ),
    pytest.param(
        OldRegimeParser.K_CLASS,
        'a)',
        id='parameter_pos_1',
    ),
])
# pylint: disable-next=unused-variable
def test_parse_profiles_invalid_regex(key: str, pattern: str) -> None:
    """Test the error raised for a profile with an invalid regex."""
    with pytest.raises(re.PatternError) as exc:
        re.compile(pattern)
    expected = Messages.PROFILE_ERROR_INVALID_REGEX.format(
        PROFILE_NAME, key, pattern, exc.value.pos or 0, type(exc.value).__name__, exc.value.msg,
    )

    with pytest.raises(ProfileError) as exc_info:
        parse_profiles({PROFILE_NAME: {**OLD_REGIME_CONTENTS, key: pattern}})

    assert str(exc_info.value) == expected


SETTINGS_INI = (
    'url_retrieval_timeout_seconds = 7\n'
    'max_url_redirections = 3\n'
)
OLD_REGIME_INI = (
    f'[{OLD_REGIME_PROFILE_NAME}]\n'
    f'url = {OLD_REGIME_CONTENTS['url']}\n'
    f'{OldRegimeParser.K_CLASS} = {OLD_REGIME_CONTENTS[OldRegimeParser.K_CLASS]}\n'
    f'{OldRegimeParser.V_CLASS} = {OLD_REGIME_CONTENTS[OldRegimeParser.V_CLASS]}\n'
)
BARATZ_INI = (
    f'[{BARATZ_PROFILE_NAME}]\n'
    f'url = {BARATZ_CONTENTS['url']}\n'
    f'{BaratzParser.M_TAG} = {BARATZ_CONTENTS[BaratzParser.M_TAG]}\n'
    f'{BaratzParser.M_ATTR} = {BARATZ_CONTENTS[BaratzParser.M_ATTR]}\n'
    f'{BaratzParser.M_VALUE} = {BARATZ_CONTENTS[BaratzParser.M_VALUE]}\n'
)
PERCENT_PATTERN = 'sample_%_pattern'


@pytest.mark.parametrize(('contents', 'expected_settings', 'expected_profiles'), [
    pytest.param(
        f'{SETTINGS_INI}\n{OLD_REGIME_INI}',
        Settings(url_retrieval_timeout_seconds=7, max_url_redirections=3),
        [OLD_REGIME_PROFILE],
        id='settings_and_profile',
    ),
    pytest.param(
        OLD_REGIME_INI,
        Settings(),
        [OLD_REGIME_PROFILE],
        id='no_settings',
    ),
    pytest.param(
        f'{OLD_REGIME_INI}\n{BARATZ_INI}',
        Settings(),
        [OLD_REGIME_PROFILE, BARATZ_PROFILE],
        id='two_profiles',
    ),
    pytest.param(
        f'\ufeff{SETTINGS_INI}\n{OLD_REGIME_INI}',
        Settings(url_retrieval_timeout_seconds=7, max_url_redirections=3),
        [OLD_REGIME_PROFILE],
        id='bom',
    ),
    pytest.param(
        OLD_REGIME_INI.replace(OLD_REGIME_URL_PATTERN, PERCENT_PATTERN),
        Settings(),
        [(OLD_REGIME_PROFILE_NAME, re.compile(PERCENT_PATTERN, re.IGNORECASE), *OLD_REGIME_PROFILE[2:])],
        id='percent_sign',
    ),
])
# pylint: disable-next=unused-variable
def test_load_inifile(
    tmp_path: Path,
    contents: str,
    expected_settings: Settings,
    expected_profiles: list[ProfileSummary],
) -> None:
    """Test the loading of a valid INI file."""
    inifile_path = tmp_path / 'file.ini'
    inifile_path.write_text(contents, encoding='utf-8')

    settings, profiles = load_inifile(inifile_path)

    actual_profiles = [
        (profile.name, profile.url_pattern, type(profile.parser), profile.parser_config)
        for profile in profiles
    ]

    assert settings == expected_settings
    assert actual_profiles == expected_profiles


# The path is not known until the test runs, so in the expected messages
# a '{}' placeholder is kept to fill in the INI file path.
INI_PATH_PLACEHOLDER = '{}'


@pytest.mark.parametrize(('contents', 'expected_error', 'expected_message'), [
    # Syntax errors.
    pytest.param(
        f'[{PROFILE_NAME}]\n'
        'line with a missing equals sign, not a key value pair\n',
        IniFileError,
        Messages.INIFILE_ERROR_WRONG_SYNTAX.format('Parsing', INI_PATH_PLACEHOLDER),
        id='no_equals',
    ),
    pytest.param(
        f'{OLD_REGIME_INI}{OLD_REGIME_INI}',
        IniFileError,
        Messages.INIFILE_ERROR_WRONG_SYNTAX.format('DuplicateSection', INI_PATH_PLACEHOLDER),
        id='duplicate_section',
    ),
    pytest.param(
        f'[{PROFILE_NAME}]\n'
        f'url = {URL_PATTERN}\n'
        f'url = {URL_PATTERN}\n',
        IniFileError,
        Messages.INIFILE_ERROR_WRONG_SYNTAX.format('DuplicateOption', INI_PATH_PLACEHOLDER),
        id='duplicate_option',
    ),

    # No profiles.
    pytest.param(
        '',
        ProfileError,
        Messages.INIFILE_ERROR_NO_VALID_PROFILES.format(INI_PATH_PLACEHOLDER),
        id='empty_file',
    ),
    pytest.param(
        SETTINGS_INI,
        ProfileError,
        Messages.INIFILE_ERROR_NO_VALID_PROFILES.format(INI_PATH_PLACEHOLDER),
        id='only_settings',
    ),

    # Errors raised when parsing settings and profiles.
    pytest.param(
        f'{URL_PATTERN} = 1\n'
        f'{OLD_REGIME_INI}',
        SettingsError,
        Messages.SETTINGS_ERROR_UNKNOWN_KEYS.format(Messages.QUOTED.format(URL_PATTERN)),
        id='unknown_setting',
    ),
    pytest.param(
        f'[{PROFILE_NAME}]\n',
        ProfileError,
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(PROFILE_NAME),
        id='empty_profile',
    ),
])
# pylint: disable-next=unused-variable
def test_load_inifile_content_errors(
    tmp_path: Path,
    contents: str,
    expected_error: type[Exception],
    expected_message: str,
) -> None:
    """Test the errors raised for INI files with wrong contents."""
    inifile_path = tmp_path / 'file.ini'
    inifile_path.write_text(contents, encoding='utf-8')

    with pytest.raises(expected_error) as exc_info:
        load_inifile(inifile_path)

    assert str(exc_info.value) == expected_message.format(inifile_path)


@pytest.mark.parametrize('contents', [
    pytest.param(
        'ñáéíóúüçÑÁÉÍÓÚÜÇ'.encode('latin-1'),
        id='latin_1',
    ),
    pytest.param(
        'ñáéíóúüçÑÁÉÍÓÚÜÇ'.encode('utf-16'),
        id='utf_16',
    ),
])
# pylint: disable-next=unused-variable
def test_load_inifile_not_utf_8(tmp_path: Path, contents: bytes) -> None:
    """Test the error raised for an INI file not encoded in UTF-8."""
    inifile_path = tmp_path / 'file.ini'
    inifile_path.write_bytes(contents)

    with pytest.raises(IniFileError) as exc_info:
        load_inifile(inifile_path)

    assert str(exc_info.value) == Messages.INIFILE_ERROR_FILE_NOT_UTF_8.format(inifile_path)


@pytest.mark.parametrize(('error', 'expected'), [
    pytest.param(
        FileNotFoundError,
        Messages.INIFILE_ERROR_FILE_NOT_FOUND,
        id='not_found',
    ),
    pytest.param(
        PermissionError,
        Messages.INIFILE_ERROR_FILE_NO_PERMISSION,
        id='no_permission',
    ),
    pytest.param(
        OSError,
        Messages.INIFILE_ERROR_FILE_READ_FAILED,
        id='read_failed',
    ),
])
# pylint: disable-next=unused-variable
def test_load_inifile_open_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: type[OSError],
    expected: str,
) -> None:
    """Test the errors raised when opening the INI file fails."""
    def failing_open(*_args: object, **_kwargs: object) -> NoReturn:
        raise error

    monkeypatch.setattr(Path, 'open', failing_open)
    inifile_path = tmp_path / 'file.ini'

    with pytest.raises(IniFileError) as exc_info:
        load_inifile(inifile_path)

    assert str(exc_info.value) == expected.format(inifile_path)
