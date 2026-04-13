"""Test suite for the different handlers of sources and sinks."""
from collections import defaultdict
from collections.abc import Callable
from hashlib import algorithms_available, new as new_hash
from pathlib import Path
from random import choice, randrange
from uuid import uuid4

from openpyxl import load_workbook, Workbook
from openpyxl.utils.cell import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
import pytest

from sacamantecas import (
    bootstrap,
    get_url_from_row,
    Handler,
    single_url_handler,
    SourceError,
    spreadsheet_handler,
    textfile_handler,
    url_to_path,
)

HASHES = [hash_function for hash_function in algorithms_available if not hash_function.startswith('shake')]
SAMPLE_URLS = [f'{choice(('https', 'http', 'file'))}://subdomain{i}.domain.tld' for i in range(10)]  # noqa: S311
EXPECTED_METADATA = {u: {h: new_hash(h, u.encode('utf-8')).hexdigest() for h in HASHES} for u in SAMPLE_URLS}


MockSinkfileMaker = Callable[[str], Path]
@pytest.fixture
# pylint: disable-next=unused-variable
def mock_sinkfile_maker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> MockSinkfileMaker:
    """Fixture to mock the sink file path generation."""
    def _mock_sinkfile_maker(suffix: str) -> Path:
        def patched_generate_sinkfile_path(_: Path) -> Path:
            return mock_sinkfile_path
        mock_sinkfile_path = tmp_path / f'testsink_out.{suffix}'
        monkeypatch.setitem(single_url_handler.__globals__, 'generate_sinkfile_path', patched_generate_sinkfile_path)
        return mock_sinkfile_path
    return _mock_sinkfile_maker


# pylint: disable-next=unused-variable,redefined-outer-name
def test_handler_single_url(mock_sinkfile_maker: MockSinkfileMaker) -> None:
    """Test single URL handler."""
    single_url = url_to_path('url://subdomain.domain.toplevel/path?param1=value1&param2=value2')
    expected = Path('url___subdomain_domain_toplevel_path_param1_value1_param2_value2')

    assert single_url == expected

    mock_sinkfile_path = mock_sinkfile_maker('txt')

    handler = single_url_handler(SAMPLE_URLS[0])
    bootstrap(handler)

    urls: list[str] = []
    for url in handler:
        assert url is not None
        assert not isinstance(url, bool)

        handler.send(EXPECTED_METADATA[url])

        urls.append(url)

    assert mock_sinkfile_path.is_file()
    assert len(urls) == 1
    assert urls[0] == SAMPLE_URLS[0]

    result = mock_sinkfile_path.read_text().rstrip('\n').split('\n')

    assert result[0] == SAMPLE_URLS[0]

    result = dict(line.strip().split(': ') for line in result[1:])

    assert result == EXPECTED_METADATA[urls[0]]


# pylint: disable-next=unused-variable,redefined-outer-name
def test_handler_single_url_unsupported_url(mock_sinkfile_maker: MockSinkfileMaker) -> None:
    """Test single URL handler with unsupported URL scheme."""
    mock_sinkfile_path = mock_sinkfile_maker('txt')
    handler = single_url_handler('mock://')

    bootstrap(handler)
    with pytest.raises(StopIteration):
        next(handler)

    assert not mock_sinkfile_path.read_text(encoding='utf-8')


# pylint: disable-next=unused-variable,redefined-outer-name
def test_handler_single_url_no_metadata(mock_sinkfile_maker: MockSinkfileMaker) -> None:
    """Test single URL handler with no metadata."""
    mock_sinkfile_path = mock_sinkfile_maker('txt')
    handler = single_url_handler(SAMPLE_URLS[0])

    bootstrap(handler)
    url = next(handler)
    assert url == SAMPLE_URLS[0]
    handler.send({})
    with pytest.raises(StopIteration):
        next(handler)

    assert not mock_sinkfile_path.read_text(encoding='utf-8')


# pylint: disable-next=unused-variable,redefined-outer-name
def test_handler_textfile(tmp_path: Path, mock_sinkfile_maker: MockSinkfileMaker) -> None:
    """Test textfile handler."""
    sourcefile_path = tmp_path / 'urls.txt'
    sourcefile_path.write_text('\n'.join(SAMPLE_URLS), encoding='utf-8')
    mock_sinkfile_path = mock_sinkfile_maker('txt')

    handler = textfile_handler(sourcefile_path)
    bootstrap(handler)

    urls: list[str] = []
    for url in handler:
        assert url is not None
        assert not isinstance(url, bool)

        handler.send(EXPECTED_METADATA[url])

        urls.append(url)

    assert mock_sinkfile_path.is_file()
    assert len(urls) == len(SAMPLE_URLS)
    assert urls == SAMPLE_URLS

    result: dict[str, dict[str, str]] = {}
    current_k = None
    for line in mock_sinkfile_path.read_text().rstrip('\n').split('\n'):
        if not line.rstrip():
            continue
        if line.startswith('  ') and current_k is not None:
            result[current_k].update(dict([line.strip().split(': ')]))
            continue
        current_k = line.strip()
        result[current_k] = {}

    assert result == EXPECTED_METADATA


# pylint: disable-next=unused-variable,redefined-outer-name
def test_handler_textfile_unsupported_url(tmp_path: Path, mock_sinkfile_maker: MockSinkfileMaker) -> None:
    """Test textfile handler with unsupported URL scheme."""
    sourcefile_path = tmp_path / 'urls.txt'
    sourcefile_path.write_text('mock://', encoding='utf-8')
    mock_sinkfile_path = mock_sinkfile_maker('txt')

    handler = textfile_handler(sourcefile_path)
    bootstrap(handler)

    with pytest.raises(StopIteration):
        next(handler)

    assert not mock_sinkfile_path.read_text(encoding='utf-8')


# pylint: disable-next=unused-variable,redefined-outer-name
def test_handler_textfile_no_metadata(tmp_path: Path, mock_sinkfile_maker: MockSinkfileMaker) -> None:
    """Test textfile handler with no metadata."""
    sourcefile_path = tmp_path / 'urls.txt'
    sourcefile_path.write_text(SAMPLE_URLS[0], encoding='utf-8')
    mock_sinkfile_path = mock_sinkfile_maker('txt')

    handler = textfile_handler(sourcefile_path)
    bootstrap(handler)
    url = next(handler)
    handler.send({})

    with pytest.raises(StopIteration):
        next(handler)

    assert url == SAMPLE_URLS[0]
    assert not mock_sinkfile_path.read_text(encoding='utf-8')


@pytest.mark.parametrize(('metadata', 'expected'), [
    pytest.param(
        EXPECTED_METADATA,
        EXPECTED_METADATA,
        id='test_handler_spreadsheet_with_metadata',
    ),
    pytest.param(
        defaultdict[str, dict[str, str]](dict),
        {url: dict[str, str]() for url in SAMPLE_URLS},
        id='test_handler_spreadsheet_without_metadata',
    ),
])
# pylint: disable-next=unused-variable,too-many-locals
def test_handler_spreadsheet(
    tmp_path: Path,
    mock_sinkfile_maker: MockSinkfileMaker,  # pylint: disable=redefined-outer-name
    metadata: dict[str, dict[str, str]],
    expected: dict[str, dict[str, str]],
) -> None:
    """Test spreadsheet handler."""
    sourcefile_path = tmp_path / 'urls.xlsx'
    mock_sinkfile_path = mock_sinkfile_maker('xlsx')

    fake_metadata_columns = 10
    headings = [f'Heading_{i}' for i in range(fake_metadata_columns)]

    workbook = Workbook()
    sheet = workbook.active

    assert sheet is not None
    sheet.append(headings)

    for column in range(fake_metadata_columns):
        sheet.column_dimensions[get_column_letter(column + 1)].width = 33

    for url in SAMPLE_URLS:
        row = [uuid4().hex[:randrange(5, 20)] for _ in range(fake_metadata_columns)]  # noqa: S311
        row.insert(randrange(len(row)), url)  # noqa: S311
        sheet.append(row)
    workbook.save(sourcefile_path)
    workbook.close()

    handler = spreadsheet_handler(sourcefile_path)
    bootstrap(handler)

    urls: list[str] = []
    for url in handler:
        assert isinstance(url, str)

        handler.send(metadata[url])

        urls.append(url)

    assert mock_sinkfile_path.is_file()
    assert len(urls) == len(SAMPLE_URLS)
    assert urls == SAMPLE_URLS

    result = {}
    workbook = load_workbook(mock_sinkfile_path)
    sheet = workbook.worksheets[0]

    assert isinstance(sheet, Worksheet)

    headers: dict[int ,str] = {}
    for cell in next(sheet.rows):
        value = str(cell.value)
        if not value or not value.startswith('[sm] '):
            continue
        value = value.removeprefix('[sm] ')
        assert cell.column is not None
        headers[cell.column] = value

    for row in sheet.rows:
        if (url := get_url_from_row(row)) is None:
            continue
        assert row[0].row is not None
        result[url] = {k: sheet.cell(row[0].row, column).value for column, k in headers.items()}
    workbook.close()

    assert result == expected


@pytest.mark.parametrize(('contents'), [
    pytest.param(b'mock contents' , id='test_handler_spreadsheet_invalid_input_bad_zip'),
    pytest.param(b'PK\x05\x06' + b'\x00' * 18 , id='test_handler_spreadsheet_invalid_input_bad_xlxs'),
])
# pylint: disable-next=unused-variable
def test_handler_spreadsheet_invalid_input(
    tmp_path: Path,
    mock_sinkfile_maker: MockSinkfileMaker,  # pylint: disable=redefined-outer-name
    contents: bytes,
) -> None:
    """Test spreadsheet handler with an invalid XLSX input file."""
    sourcefile_path = tmp_path / 'invalid.xlsx'
    sourcefile_path.write_bytes(contents)
    mock_sinkfile_path = mock_sinkfile_maker('xlsx')

    handler = spreadsheet_handler(sourcefile_path)
    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)

    assert excinfo.type == SourceError
    assert str(excinfo.value).startswith('La hoja de entrada es inválida')
    assert mock_sinkfile_path.read_bytes() == contents


@pytest.mark.parametrize(('unreadable_path', 'handler_factory'), [
    pytest.param('unreadable_textfile.txt', textfile_handler, id='test_unreadable_txt_input'),
    pytest.param('unreadable_spreadsheet.xlsx', spreadsheet_handler, id='test_unreadable_xlsx_input'),
], indirect=['unreadable_path'])
# pylint: disable-next=unused-variable
def test_unreadable_input_file(unreadable_path: Path, handler_factory: Callable[[Path], Handler]) -> None:
    """Test handling of unreadable files."""
    handler = handler_factory(unreadable_path)

    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)

    assert str(excinfo.value).startswith('No hay permisos suficientes para leer el fichero de entrada.')


@pytest.mark.parametrize(('source_stem', 'unwritable_path', 'handler_factory'), [
    pytest.param(
        'http://s.url',
        'unwritable_single_url_out.txt',
        single_url_handler,
        id='test_unwritable_output_file_single_url',
    ),
    pytest.param(
        's.txt',
        'unwritable_textfile_out.txt',
        textfile_handler,
        id='test_unwritable_output_file_txt_file',
    ),
    pytest.param(
        's.xlsx',
        'unwritable_spreadsheet_out.xlsx',
        spreadsheet_handler,
        id='test_unwritable_output_file_xlsx_file',
    ),
], indirect=['unwritable_path'])
# pylint: disable-next=unused-variable
def test_unwritable_output_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_stem: str,
    unwritable_path: Path,
    handler_factory: Callable[[str | Path], Handler],
) -> None:
    """Test handling of non-writable files."""
    def patched_generate_sinkfile_path(_: Path) -> Path:
        return unwritable_path

    monkeypatch.setitem(handler_factory.__globals__, 'generate_sinkfile_path', patched_generate_sinkfile_path)

    if not source_stem.startswith('http://'):
        source = tmp_path / source_stem
        source.write_text('')
    else:
        source = source_stem

    handler = handler_factory(source)

    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)

    assert str(excinfo.value).startswith('No hay permisos suficientes para crear el fichero de salida.')
