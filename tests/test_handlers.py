#! /usr/bin/env python3
"""Test suite for the different handlers of URL sources / metadata sinks."""
import os
from pathlib import Path
from random import choice, randrange
from uuid import uuid4

from openpyxl import Workbook
from openpyxl.utils.cell import get_column_letter

import pytest

import sacamantecas as sm


SAMPLE_URLS = [f'{choice(sm.ACCEPTED_URL_SCHEMES)}://subdomain{i}.domain.tld' for i in range(10)]
EXPECTED = [True] + [item for url in SAMPLE_URLS for item in (url, None)]


def test_single_url_handler():  # pylint: disable=unused-variable
    """Test single URLs."""
    result = sm.url_to_filename('url://subdomain.domain.toplevel/path?param1=value1&param2=value2')
    expected = Path('url___subdomain_domain_toplevel_path_param1_value1_param2_value2')
    assert result == expected

    result = list(sm.single_url_handler(SAMPLE_URLS[0]))
    assert result == EXPECTED[0:3]


def test_textfile_handler(tmp_path):  # pylint: disable=unused-variable
    """Test textfile handler."""
    filename = tmp_path / 'urls.txt'
    filename.write_text('\n'.join(SAMPLE_URLS), encoding='utf-8')
    result = list(sm.textfile_handler(filename))
    assert result == EXPECTED


def test_spreadsheet_handler(tmp_path):  # pylint: disable=unused-variable
    """Test spreadsheet handler."""
    columns = 10
    filename = tmp_path / 'urls.xlsx'
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

    workbook.save(filename)
    workbook.close()

    result = list(sm.spreadsheet_handler(filename))
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


@pytest.mark.parametrize('filename, handler', [
    ('unreadable.txt', sm.textfile_handler),
    ('unreadable.xlsx', sm.spreadsheet_handler)
])
def test_input_no_permission(unreadable_file, handler):  # pylint: disable=unused-variable
    """."""
    handler = handler(unreadable_file)
    with pytest.raises(sm.SourceError) as excinfo:
        sm.bootstrap(handler)
    assert excinfo.value.details.startswith(sm.Messages.INPUT_FILE_NO_PERMISSION)


@pytest.mark.parametrize('source, filename, handler', [
    (
        'http://s.url',
        Path(str(sm.url_to_filename('http://s.url')) + sm.OUTPUT_FILE_STEM_MARKER).with_suffix('.txt'),
        sm.single_url_handler
    ),
    (
        Path('s.txt'),
        Path('s.txt').with_stem(Path('s.txt').stem + sm.OUTPUT_FILE_STEM_MARKER),
        sm.textfile_handler
    ),
    (
        Path('s.xlsx'),
        Path('s.xlsx').with_stem(Path('s.xlsx').stem + sm.OUTPUT_FILE_STEM_MARKER),
        sm.spreadsheet_handler
    )
])
def test_output_no_permission(source, unreadable_file, handler):  # pylint: disable=unused-variable
    """."""
    os.chdir(unreadable_file.parent)
    if isinstance(source, Path):
        source.write_text('')
    handler = handler(source)
    with pytest.raises(sm.SourceError) as excinfo:
        sm.bootstrap(handler)
    if isinstance(source, Path):
        source.unlink()
    assert excinfo.value.details.startswith(sm.Messages.OUTPUT_FILE_NO_PERMISSION)
