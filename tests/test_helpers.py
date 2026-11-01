"""Test suite for the pure helpers."""
import pytest

from sacamantecas import is_url, lowercase_first_letter, Url


@pytest.mark.parametrize('url', [
    pytest.param('http://', id='http'),
    pytest.param('https://', id='https'),
    pytest.param('ftp://', id='ftp'),
    pytest.param('file:///C:/x', id='file'),
    pytest.param('HTTP://', id='uppercase'),
    pytest.param('HtTp://', id='mixed_case'),
    pytest.param('ab://', id='two_chars_scheme'),
    pytest.param('a+bc://', id='plus_sign'),
    pytest.param('a1bc://', id='digit'),
    pytest.param('a.bc://', id='period'),
    pytest.param('a-bc://', id='hyphen'),
    pytest.param('http:// shape only', id='http_shape'),
])
# pylint: disable-next=unused-variable
def test_is_url_accepts(url: Url) -> None:
    """Test accepted URLs."""
    assert is_url(url)

@pytest.mark.parametrize('url', [
    pytest.param('\u017ftp://', id='non_ASCII_F'),
    pytest.param('\u212attp://x', id='non_ASCII_K'),
    pytest.param('ht\u017fp://x', id='non_ASCII_mid'),
    pytest.param('h://foo', id='short_scheme'),
    pytest.param('H://foo', id='short_upper_scheme'),
    pytest.param('C:\\dir\\file.ext', id='drive_and_path'),
    pytest.param('http:/x', id='one_slash'),
    pytest.param('http//x', id='no_colon'),
    pytest.param('://x', id='no_scheme'),
    pytest.param('1http://x', id='leading_digit'),
    pytest.param('-http://x', id='leading_hyphen'),
    pytest.param(' http://', id='leading_whitespace'),
    pytest.param('see http://x', id='embedded_url'),
    pytest.param('', id='empty_url'),
])
# pylint: disable-next=unused-variable
def test_is_url_rejects(url: Url) -> None:
    """Test rejected URLs."""
    assert not is_url(url)


@pytest.mark.parametrize(('message', 'expected'), [
    pytest.param('ßOther', 'ßOther', id='first_has_no_lowercase'),
    pytest.param('Ñabc', 'ñabc', id='lower_non_ASCII'),
    pytest.param('aOther', 'aOther', id='first_already_lower'),
    pytest.param('42 Other', '42 other', id='letter_not_first'),
    pytest.param('X', 'x', id='single_letter'),
    pytest.param('1', '1', id='single_non_letter'),
    pytest.param('HTTP', 'hTTP', id='lower_acronyms_too'),
    pytest.param('\u0130Other', 'i\u0307Other', id='lower_may_expand_chars'),
    pytest.param('', '', id='empty_string'),
    pytest.param('42 ... 7', '42 ... 7', id='no_letters'),
])
# pylint: disable-next=unused-variable
def test_lowercase_first_letter(message: str, expected: str) -> None:
    """Test `lowercase_first_letter()`."""
    assert lowercase_first_letter(message) == expected
