"""Generate project metadata and dump it to `about.py`."""  # noqa: INP001
import sys
from textwrap import dedent
from typing import TYPE_CHECKING

from legion import ensure_utf8_output, excepthook, generate_metadata_file, timestamp

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


TEMPLATE = dedent(f'''
    """Auto generated, do not edit."""
    # {timestamp('%Y-%m-%d %H:%M:%S')}

    # pylint: disable=unused-variable
    PROGRAM_NAME = {{project[name]!r}}
    VERSION = {{project[version]!r}}
    REPOSITORY = {{project[urls][source]!r}}
    DEPENDENCIES = {{project[dependencies]!r}}
''').lstrip()


@ensure_utf8_output
def main() -> int | str:
    """."""
    # ruff: disable[T201]
    sys.excepthook = excepthook

    def output_path_factory(m: dict[str, Any]) -> Path:
        return m['project_root'] / 'src' / m['project']['name'] / 'about.py'

    if (about_py_file := generate_metadata_file(output_path_factory, TEMPLATE)) is None:
        return f"Error generating metadata file at '{about_py_file}'."

    print(f"Generated metadata file at '{about_py_file}'")
    return 0
    # ruff: enable[T201]


if __name__ == '__main__':
    sys.exit(main())
