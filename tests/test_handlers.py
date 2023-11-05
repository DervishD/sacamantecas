#! /usr/bin/env python3
"""Test suite for the different handlers of URL sources / metadata sinks."""
from pathlib import Path
from random import choice, randrange
from uuid import uuid4

from openpyxl import Workbook
from openpyxl.utils.cell import get_column_letter

import pytest

import sacamantecas as sm


SAMPLE_URLS = [f'{choice(sm.ACCEPTED_URL_SCHEMES)}://subdomain{i}.domain.tld' for i in range(10)]
EXPECTED = [True] + [item for url in SAMPLE_URLS for item in (url, None)]


def test_single_url_handler(monkeypatch, tmp_path):  # pylint: disable=unused-variable
    """Test single URLs."""
    result = sm.url_to_filename('url://subdomain.domain.toplevel/path?param1=value1&param2=value2')
    expected = Path('url___subdomain_domain_toplevel_path_param1_value1_param2_value2')
    assert result == expected

    sink_filename = tmp_path / f'testsink{sm.SINK_FILENAME_STEM_MARKER}.txt'
    monkeypatch.setattr(sm, 'generate_sink_filename', lambda _: sink_filename)
    result = list(sm.single_url_handler(SAMPLE_URLS[0]))
    assert sink_filename.is_file()
    assert result == EXPECTED[0:3]


def test_textfile_handler(monkeypatch, tmp_path):  # pylint: disable=unused-variable
    """Test textfile handler."""
    source_filename = tmp_path / 'urls.txt'
    source_filename.write_text('\n'.join(SAMPLE_URLS), encoding='utf-8')
    sink_filename = tmp_path / f'testsink{sm.SINK_FILENAME_STEM_MARKER}.txt'
    monkeypatch.setattr(sm, 'generate_sink_filename', lambda _: sink_filename)
    result = list(sm.textfile_handler(source_filename))
    assert sink_filename.is_file()
    assert result == EXPECTED


def test_spreadsheet_handler(monkeypatch, tmp_path):  # pylint: disable=unused-variable
    """Test spreadsheet handler."""
    columns = 10
    source_filename = tmp_path / 'urls.xlsx'
    headings = [f'Heading_{i}' for i in range(columns)]

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headings)
    for column in range(columns):
        sheet.column_dimensions[get_column_letter(column + 1)].width = 33

    for url in SAMPLE_URLS:
        row = [uuid4().hex[:randrange(5, 20)] for _ in range(columns)]
        row.insert(randrange(len(row)), url)
        sheet.append(row)

    workbook.save(source_filename)
    workbook.close()

    sink_filename = tmp_path / f'testsink{sm.SINK_FILENAME_STEM_MARKER}.xlsx'
    monkeypatch.setattr(sm, 'generate_sink_filename', lambda _: sink_filename)
    result = list(sm.spreadsheet_handler(source_filename))
    assert sink_filename.is_file()
    assert result == EXPECTED


@pytest.mark.parametrize('suffix, handler', [
    ('.txt', sm.textfile_handler),
    ('.xlsx', sm.spreadsheet_handler)
])
def test_missing_source(tmp_path, suffix, handler):  # pylint: disable=unused-variable
    """Test for missing source handling."""
    handler = handler(tmp_path / f'non_existent{suffix}')
    with pytest.raises(sm.SourceError) as excinfo:
        sm.bootstrap(handler)
    assert excinfo.value.details.startswith(sm.Messages.INPUT_FILE_NOT_FOUND)


@pytest.mark.parametrize('unreadable_file, handler', [
    ('unreadable_textfile.txt', sm.textfile_handler),
    ('unreadable_spreadsheet.xlsx', sm.spreadsheet_handler)
], indirect=['unreadable_file'])
def test_input_no_permission(unreadable_file, handler):  # pylint: disable=unused-variable
    """."""
    handler = handler(unreadable_file)
    with pytest.raises(sm.SourceError) as excinfo:
        sm.bootstrap(handler)
    assert excinfo.value.details.startswith(sm.Messages.INPUT_FILE_NO_PERMISSION)


@pytest.mark.parametrize('source, unwritable_file, handler', [
    ('http://s.url', f'unwritable_single_url{sm.SINK_FILENAME_STEM_MARKER}.txt', sm.single_url_handler),
    ('s.txt', f'unwritable_textfile{sm.SINK_FILENAME_STEM_MARKER}.txt', sm.textfile_handler),
    ('s.xlsx', f'unwritable_spreadsheet{sm.SINK_FILENAME_STEM_MARKER}.xlsx', sm.spreadsheet_handler)
], indirect=['unwritable_file'])
def test_output_no_permission(tmp_path, monkeypatch, source, unwritable_file, handler):  # pylint: disable=unused-variable
    """."""
    monkeypatch.setattr(sm, 'generate_sink_filename', lambda _: unwritable_file)
    if not source.startswith('http://'):
        source = tmp_path / source
        source.write_text('')
    handler = handler(source)
    with pytest.raises(sm.SourceError) as excinfo:
        sm.bootstrap(handler)
    assert excinfo.value.details.startswith(sm.Messages.OUTPUT_FILE_NO_PERMISSION)
