#! /usr/bin/env python
"""Dump contents of provided URL to text file. Crudely."""
import logging
import sys

from sacamantecas import retrieve_url, url_to_filename


def main(*args: str) -> int:
    """."""
    logging.getLogger().setLevel(logging.INFO)
    for url in args:
        logging.info('Retrieving %s', url)
        contents, encoding = retrieve_url(url)

        logging.info('Detected encoding: %s', encoding)
        contents = contents.decode(encoding)

        output_filename = url_to_filename(url).with_suffix('.html')
        with output_filename.open('wt', encoding=encoding) as output_file:
            logging.info('Dumping web page to %s', output_filename)
            output_file.write(contents)
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
