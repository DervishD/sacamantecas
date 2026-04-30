"""Generate project metadata and dump it to `about.py`."""  # noqa: INP001
from pathlib import Path
import sys
from textwrap import dedent

from legion import ensure_utf8_output, excepthook, get_project_metadata


@ensure_utf8_output
def main() -> int | str:
    """."""
    sys.excepthook = excepthook

    if (project_metadata := get_project_metadata()) is None:
        return 'Error geting project metadata.'

    output_path = Path(project_metadata['local']['colophon']['path']).resolve()
    template = dedent(project_metadata['local']['colophon']['template'])

    output_path.write_text(template.format_map(project_metadata), encoding='utf-8', newline='\n')

    print(output_path, end='')  # noqa: T201
    return 0


if __name__ == '__main__':
    sys.exit(main())
