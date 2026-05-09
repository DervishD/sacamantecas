"""Dump contents of provided URL to text file. Crudely."""
import sys

from legion import ensure_utf8_output, excepthook, get_logger

from sacamantecas import retrieve_url, url_to_path


@ensure_utf8_output
def main(*args: str) -> int:
    """."""
    logger = get_logger(__name__)
    logger.config()
    for url in args:
        logger.info('Retrieving %s', url)
        contents, encoding = retrieve_url(url)

        logger.info('Detected encoding: %s', encoding)
        contents = contents.decode(encoding)

        output_path = url_to_path(url).with_suffix('.html')
        logger.info('Dumping web page to %s', output_path)
        output_path.write_text(contents, encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.excepthook = excepthook
    sys.exit(main(*sys.argv[1:]))
