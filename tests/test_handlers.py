#! /usr/bin/env python3
"""Test suite for the different handlers of URL sources / metadata sinks."""
from hashlib import algorithms_available, new as new_hash
from pathlib import Path
from random import choice, randrange
from uuid import uuid4

from openpyxl import load_workbook, Workbook
from openpyxl.utils.cell import get_column_letter

import pytest

from sacamantecas import (
    bootstrap,
    Constants,
    get_url_from_row,
    Messages,
    single_url_handler,
    SourceError,
    spreadsheet_handler,
    textfile_handler,
    url_to_filename,
)


HASHES = [hash_function for hash_function in algorithms_available if not hash_function.startswith('shake')]
SAMPLE_URLS = [f'{choice(Constants.ACCEPTED_URL_SCHEMES)}://subdomain{i}.domain.tld' for i in range(10)]
EXPECTED_METADATA = {u: {h: new_hash(h, u.encode(Constants.UTF8)).hexdigest() for h in HASHES} for u in SAMPLE_URLS}


def test_single_url_handler(monkeypatch, tmp_path):  # pylint: disable=unused-variable
    """Test single URLs."""
    urls = url_to_filename('url://subdomain.domain.toplevel/path?param1=value1&param2=value2')
    expected = Path('url___subdomain_domain_toplevel_path_param1_value1_param2_value2')
    assert urls == expected

    sink_filename = tmp_path / f'testsink{Constants.SINKFILE_STEM}.txt'
    monkeypatch.setattr('sacamantecas.generate_sink_filename', lambda _: sink_filename)

    handler = single_url_handler(SAMPLE_URLS[0])
    bootstrap(handler)

    urls = []
    for url in handler:
        urls.append(url)
        handler.send(EXPECTED_METADATA[url])

    assert sink_filename.is_file()
    assert len(urls) == 1
    assert urls[0] == SAMPLE_URLS[0]

    result = sink_filename.read_text().rstrip(Constants.TEXTSINK_METADATA_FOOTER).splitlines()
    assert result[0] == SAMPLE_URLS[0]
    result = dict(line.strip().split(Constants.TEXTSINK_METADATA_SEPARATOR) for line in result[1:])
    assert result == EXPECTED_METADATA[urls[0]]


def test_textfile_handler(monkeypatch, tmp_path):  # pylint: disable=unused-variable
    """Test textfile handler."""
    source_filename = tmp_path / 'urls.txt'
    source_filename.write_text('\n'.join(SAMPLE_URLS), encoding='utf-8')
    sink_filename = tmp_path / f'testsink{Constants.SINKFILE_STEM}.txt'
    monkeypatch.setattr('sacamantecas.generate_sink_filename', lambda _: sink_filename)

    handler = textfile_handler(source_filename)
    bootstrap(handler)

    urls = []
    for url in handler:
        urls.append(url)
        handler.send(EXPECTED_METADATA[url])

    assert sink_filename.is_file()
    assert len(urls) == len(SAMPLE_URLS)
    assert urls == SAMPLE_URLS

    result = {}
    current_k = None
    for line in sink_filename.read_text().rstrip(Constants.TEXTSINK_METADATA_FOOTER).splitlines():
        if not line.rstrip():
            continue
        if line.startswith(Constants.TEXTSINK_METADATA_INDENT):
            result[current_k].update(dict([line.strip().split(Constants.TEXTSINK_METADATA_SEPARATOR)]))
            continue
        current_k = line.strip()
        result[current_k] = {}
    assert result == EXPECTED_METADATA


FAKE_METADATA_COLUMNS = 10
def test_spreadsheet_handler(monkeypatch, tmp_path):  # pylint: disable=unused-variable
    """Test spreadsheet handler."""
    source_filename = tmp_path / 'urls.xlsx'
    headings = [f'Heading_{i}' for i in range(FAKE_METADATA_COLUMNS)]

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headings)
    for column in range(FAKE_METADATA_COLUMNS):
        sheet.column_dimensions[get_column_letter(column + 1)].width = 33

    for url in SAMPLE_URLS:
        row = [uuid4().hex[:randrange(5, 20)] for _ in range(FAKE_METADATA_COLUMNS)]
        row.insert(randrange(len(row)), url)
        sheet.append(row)

    workbook.save(source_filename)
    workbook.close()

    sink_filename = tmp_path / f'testsink{Constants.SINKFILE_STEM}.xlsx'
    monkeypatch.setattr('sacamantecas.generate_sink_filename', lambda _: sink_filename)

    handler = spreadsheet_handler(source_filename)
    bootstrap(handler)

    urls = []
    for url in handler:
        urls.append(url)
        handler.send(EXPECTED_METADATA[url])

    assert sink_filename.is_file()
    assert len(urls) == len(SAMPLE_URLS)
    assert urls == SAMPLE_URLS

    result = {}
    workbook = load_workbook(sink_filename)
    sheet = workbook.worksheets[0]
    headers = {}
    for cell in next(sheet.rows):
        if not cell.value or not cell.value.startswith(Constants.SPREADSHEET_METADATA_COLUMN_MARKER):
            continue
        cell.value = cell.value.removeprefix(Constants.SPREADSHEET_METADATA_COLUMN_MARKER)
        headers[cell.column] = cell.value

    for row in sheet.rows:
        if (url := get_url_from_row(row)) is None:
            continue
        result[url] = {k: sheet.cell(row[0].row, column).value for column, k in headers.items()}
    workbook.close()

    assert result == EXPECTED_METADATA


@pytest.mark.parametrize('suffix, handler', [
    ('.txt', textfile_handler),
    ('.xlsx', spreadsheet_handler)
])
def test_missing_source(tmp_path, suffix, handler):  # pylint: disable=unused-variable
    """Test for missing source handling."""
    handler = handler(tmp_path / f'non_existent{suffix}')
    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)
    assert str(excinfo.value).startswith(Messages.INPUT_FILE_NOT_FOUND)


@pytest.mark.parametrize('unreadable_file, handler', [
    ('unreadable_textfile.txt', textfile_handler),
    ('unreadable_spreadsheet.xlsx', spreadsheet_handler)
], indirect=['unreadable_file'])
def test_input_no_permission(unreadable_file, handler):  # pylint: disable=unused-variable
    """."""
    handler = handler(unreadable_file)
    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)
    assert str(excinfo.value).startswith(Messages.INPUT_FILE_NO_PERMISSION)


@pytest.mark.parametrize('source, unwritable_file, handler', [
    ('http://s.url', f'unwritable_single_url{Constants.SINKFILE_STEM}.txt', single_url_handler),
    ('s.txt', f'unwritable_textfile{Constants.SINKFILE_STEM}.txt', textfile_handler),
    ('s.xlsx', f'unwritable_spreadsheet{Constants.SINKFILE_STEM}.xlsx', spreadsheet_handler)
], indirect=['unwritable_file'])
def test_output_no_permission(tmp_path, monkeypatch, source, unwritable_file, handler):  # pylint: disable=unused-variable
    """."""
    monkeypatch.setattr('sacamantecas.generate_sink_filename', lambda _: unwritable_file)
    if not source.startswith('http://'):
        source = tmp_path / source
        source.write_text('')
    handler = handler(source)
    with pytest.raises(SourceError) as excinfo:
        bootstrap(handler)
    assert str(excinfo.value).startswith(Messages.OUTPUT_FILE_NO_PERMISSION)
