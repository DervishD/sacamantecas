"""Get the requested value from the project metadata tables."""  # noqa: INP001
import sys

from legion import ensure_utf8_output, excepthook, get_project_metadata


@ensure_utf8_output
def main(args: list[str]) -> int | str:
    """."""
    if not args:
        return 'No arguments'

    if (metadata := get_project_metadata()) is None:
        return 'Error getting project metadata.'

    value = metadata
    try:
        for key in args[0].split('.'):
            value = value[key]
        print(value, end='')
    except KeyError as exc:
        return f'Metadata key not found: {exc.args[0]!r}'
    return 0


if __name__ == '__main__':
    sys.excepthook = excepthook
    sys.exit(main(sys.argv[1:]))
