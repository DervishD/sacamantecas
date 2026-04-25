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

    project_root = Path(project_metadata['project_root']).resolve()
    config = project_metadata['tool'][Path(__file__).stem]
    output_path = project_root / config['path'].format_map(project_metadata)
    template = dedent(config['template'])

    output_path.resolve().write_text(template.format_map(project_metadata), newline='\n')

    print(output_path, end='')  # noqa: T201
    return 0


if __name__ == '__main__':
    sys.exit(main())
