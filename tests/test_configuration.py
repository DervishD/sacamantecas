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

type ProfileSummary = tuple[str, re.Pattern[str], type[BaseParser], ParserConfig]


SAMPLE_K = 'sample_k'
SAMPLE_V = 'sample_v'
SAMPLE_PROFILE_NAME = 'a_profile_name'
SAMPLE_URL_PATTERN = 'a_url_pattern'
SAMPLE_K_PATTERN = 'a_k_pattern'
SAMPLE_V_PATTERN = 'a_v_pattern'
SAMPLE_PERCENT_PATTERN = 'a_%_pattern'


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
OLD_REGIME_INI = (
    f'[{OLD_REGIME_PROFILE_NAME}]\n'
    f'url = {OLD_REGIME_CONTENTS['url']}\n'
    f'{OldRegimeParser.K_CLASS} = {OLD_REGIME_CONTENTS[OldRegimeParser.K_CLASS]}\n'
    f'{OldRegimeParser.V_CLASS} = {OLD_REGIME_CONTENTS[OldRegimeParser.V_CLASS]}\n'
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
BARATZ_INI = (
    f'[{BARATZ_PROFILE_NAME}]\n'
    f'url = {BARATZ_CONTENTS['url']}\n'
    f'{BaratzParser.M_TAG} = {BARATZ_CONTENTS[BaratzParser.M_TAG]}\n'
    f'{BaratzParser.M_ATTR} = {BARATZ_CONTENTS[BaratzParser.M_ATTR]}\n'
    f'{BaratzParser.M_VALUE} = {BARATZ_CONTENTS[BaratzParser.M_VALUE]}\n'
)

SETTINGS_INI = (
    'url_retrieval_timeout_seconds = 7\n'
    'max_url_redirections = 3\n'
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





@pytest.mark.parametrize(('contents', 'expected'), [
    # Empty profile.
    pytest.param(
        {SAMPLE_PROFILE_NAME: {}},
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(SAMPLE_PROFILE_NAME),
        id='empty_profile',
    ),

    # Missing URL pattern.
    pytest.param(
        {SAMPLE_PROFILE_NAME: {OldRegimeParser.K_CLASS: SAMPLE_K_PATTERN, OldRegimeParser.V_CLASS: SAMPLE_V_PATTERN}},
        Messages.PROFILE_ERROR_PROFILE_WITHOUT_URL.format(SAMPLE_PROFILE_NAME),
        id='no_url',
    ),
    pytest.param(
        {SAMPLE_PROFILE_NAME: {**OLD_REGIME_CONTENTS, 'url': ''}},
        Messages.PROFILE_ERROR_PROFILE_WITHOUT_URL.format(SAMPLE_PROFILE_NAME),
        id='empty_url',
    ),

    # Parameters not matching any parser.
    pytest.param(
        {SAMPLE_PROFILE_NAME: {'url': SAMPLE_URL_PATTERN}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(SAMPLE_PROFILE_NAME),
        id='only_url',
    ),
    pytest.param(
        {SAMPLE_PROFILE_NAME: {'url': SAMPLE_URL_PATTERN, OldRegimeParser.K_CLASS: SAMPLE_K_PATTERN}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(SAMPLE_PROFILE_NAME),
        id='missing_parameter',
    ),
    pytest.param(
        {SAMPLE_PROFILE_NAME: {**OLD_REGIME_CONTENTS, 'nope': 'nope'}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(SAMPLE_PROFILE_NAME),
        id='unknown_parameter',
    ),
    pytest.param(
        {SAMPLE_PROFILE_NAME: {**OLD_REGIME_CONTENTS, **{k: v for k, v in BARATZ_CONTENTS.items() if k != 'url'}}},
        Messages.PROFILE_ERROR_PROFILE_WRONG_PARAMETERS.format(SAMPLE_PROFILE_NAME),
        id='mixed_parameters',
    ),

    # Several profiles.
    pytest.param(
        {SAMPLE_PROFILE_NAME: OLD_REGIME_CONTENTS, f'{SAMPLE_PROFILE_NAME}o': {}},
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(f'{SAMPLE_PROFILE_NAME}o'),
        id='second_profile',
    ),
    pytest.param(
        {SAMPLE_PROFILE_NAME: {}, f'{SAMPLE_PROFILE_NAME}o': {'url': SAMPLE_URL_PATTERN}},
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(SAMPLE_PROFILE_NAME),
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
        SAMPLE_PROFILE_NAME, key, pattern, exc.value.pos or 0, type(exc.value).__name__, exc.value.msg,
    )

    with pytest.raises(ProfileError) as exc_info:
        parse_profiles({SAMPLE_PROFILE_NAME: {**OLD_REGIME_CONTENTS, key: pattern}})

    assert str(exc_info.value) == expected






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
        OLD_REGIME_INI.replace(OLD_REGIME_URL_PATTERN, SAMPLE_PERCENT_PATTERN),
        Settings(),
        [(OLD_REGIME_PROFILE_NAME, re.compile(SAMPLE_PERCENT_PATTERN, re.IGNORECASE), *OLD_REGIME_PROFILE[2:])],
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
@pytest.mark.parametrize(('contents', 'expected_error', 'expected_message'), [
    # Syntax errors.
    pytest.param(
        f'[{SAMPLE_PROFILE_NAME}]\nline with a missing equals sign, not a key value pair\n',
        IniFileError,
        Messages.INIFILE_ERROR_WRONG_SYNTAX.format('Parsing', '{}'),
        id='no_equals',
    ),
    pytest.param(
        f'{OLD_REGIME_INI}{OLD_REGIME_INI}',
        IniFileError,
        Messages.INIFILE_ERROR_WRONG_SYNTAX.format('DuplicateSection', '{}'),
        id='duplicate_section',
    ),
    pytest.param(
        f'[{SAMPLE_PROFILE_NAME}]\nurl = {SAMPLE_URL_PATTERN}\nurl = {SAMPLE_URL_PATTERN}\n',
        IniFileError,
        Messages.INIFILE_ERROR_WRONG_SYNTAX.format('DuplicateOption', '{}'),
        id='duplicate_option',
    ),

    # No profiles.
    pytest.param(
        '',
        ProfileError,
        Messages.INIFILE_ERROR_NO_VALID_PROFILES.format('{}'),
        id='empty_file',
    ),
    pytest.param(
        SETTINGS_INI,
        ProfileError,
        Messages.INIFILE_ERROR_NO_VALID_PROFILES.format('{}'),
        id='only_settings',
    ),

    # Errors raised when parsing settings and profiles.
    pytest.param(
        f'{SAMPLE_URL_PATTERN} = 1\n{OLD_REGIME_INI}',
        SettingsError,
        Messages.SETTINGS_ERROR_UNKNOWN_KEYS.format(Messages.QUOTED.format(SAMPLE_URL_PATTERN)),
        id='unknown_setting',
    ),
    pytest.param(
        f'[{SAMPLE_PROFILE_NAME}]\n',
        ProfileError,
        Messages.PROFILE_ERROR_EMPTY_PROFILE.format(SAMPLE_PROFILE_NAME),
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
