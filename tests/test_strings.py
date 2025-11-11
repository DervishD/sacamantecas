#! /usr/bin/env python3
"""Test suite for non-refactored code strings."""
import ast

from sacamantecas import Constants

ALLOWED_STRINGS = (
    # Early platform check.
    'win32', '\nThis application is compatible only with the Win32 platform.\n',
    # Python well-known strings.
    'frozen', '__main__', 'w', '%s',
    # For typing hints.
    'TextIOWrapper', 'CustomLogger',
    # Strings used for logging.dictConfig configuration dictionary.
    'version', 'disable_existing_loggers', 'level', 'propagate',
    '()', 'style', 'format', 'datefmt', 'formatter', 'class',
    'filename', 'mode', 'encoding', 'stream',
    'debugfile_formatter', 'logfile_formatter', 'console_formatter',
    'debugfile_handler', 'logfile_handler', 'stdout_handler', 'stderr_handler',
    'loggers', 'handlers', 'formatters', 'filters',
    # Miscellaneous strings.
    'reconfigure',
)

class UnrefactoredStringsFinderVisitor(ast.NodeVisitor):
    """Simple visitor to find non-refactored literal strings."""

    def __init__(self) -> None:
        """Initialize."""
        self.ignored_strings: list[str | bytes] = []
        self.unrefactored_strings: list[tuple[int, str]] = []

    def ignore_docstring(self, node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module) -> None:
        """Ignore docstring string constants for node."""
        if docstring := ast.get_docstring(node, clean=False):
            self.ignored_strings.append(docstring)

    def visit_Module(self, node: ast.Module) -> None:  # pylint: disable=invalid-name
        """."""
        self.ignore_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # pylint: disable=invalid-name
        """."""
        self.ignore_docstring(node)

        subnodes: list[ast.AST] = []
        for child in node.body:
            if not isinstance(child, ast.Assign):
                continue
            if isinstance(child.value, ast.Tuple):
                subnodes.extend(child.value.elts)
            else:
                subnodes.append(child.value)

        for subnode in subnodes:
            if isinstance(subnode, ast.Constant) and isinstance(subnode.value, str | bytes):
                self.ignored_strings.append(subnode.value)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:   # pylint: disable=invalid-name
        """."""
        self.ignore_docstring(node)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:  # pylint: disable=invalid-name  # noqa: ARG002
        """."""
        # pylint: disable=unused-argument
        return

    def visit_Constant(self, node: ast.Constant) -> None:   # pylint: disable=invalid-name
        """."""
        if node.value in self.ignored_strings:
            self.ignored_strings.remove(node.value)
            return
        if node.value in ALLOWED_STRINGS:
            return
        if isinstance(node.value, str | bytes) and node.value.strip():
            self.unrefactored_strings.append((node.lineno, repr(node.value)))


def test_strings() -> None:  # pylint: disable=unused-variable
    """Test for non-refactored strings."""
    visitor = UnrefactoredStringsFinderVisitor()
    visitor.visit(ast.parse(Constants.APP_PATH.read_text(encoding=Constants.UTF8)))

    assert not visitor.ignored_strings
    assert not visitor.unrefactored_strings
