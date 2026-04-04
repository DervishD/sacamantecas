"""Test suite for non-refactored code strings."""
import ast
from contextlib import suppress
from inspect import getsource
from typing import NamedTuple

import pytest

import sacamantecas

ALLOWED_UNREFACTORED_STRINGS = (
    # Early platform check.
    'win32', '\nThis program is compatible only with the Win32 platform.\n',
    # Python well-known strings.
    'frozen', 'w', '%s',
    # For typing hints.
    'TextIOWrapper',
    # Allowed empty or whitespace strings.
    ' ', '', b'',
    # Miscellaneous strings.
    'reconfigure', '.post', '==', ' v',
)


class UnrefactoredStringsAuditor(ast.NodeVisitor):
    """Simple auditor to find non-refactored literal strings."""

    def __init__(self) -> None:
        """Initialize."""
        self.stale_allowed_strings: list[str | bytes] = list(ALLOWED_UNREFACTORED_STRINGS)
        self.unrefactored_strings: list[tuple[int, str | bytes]] = []
        self.ignored_strings: list[str | bytes] = []

    def ignore_docstring(self, node: ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module) -> None:
        """Ignore docstring string constants for node."""
        if docstring := ast.get_docstring(node, clean=False):
            self.ignored_strings.append(docstring)

    def visit_Module(self, node: ast.Module) -> None:  # pylint: disable=invalid-name
        """Visit Module node."""
        self.ignore_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # pylint: disable=invalid-name
        """Visit ClassDef node."""
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
        """Visit FunctionDef node."""
        self.ignore_docstring(node)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:  # pylint: disable=invalid-name  # noqa: ARG002
        """Visit JoinedStr node."""
        # pylint: disable=unused-argument
        return

    def visit_Constant(self, node: ast.Constant) -> None:   # pylint: disable=invalid-name
        """Visit Constant node."""
        if node.value in self.ignored_strings:
            self.ignored_strings.remove(node.value)
            return
        if node.value in ALLOWED_UNREFACTORED_STRINGS:
            with suppress(ValueError):
                self.stale_allowed_strings.remove(node.value)
            return
        if isinstance(node.value, str | bytes):
            self.unrefactored_strings.append((node.lineno, repr(node.value)))


class AuditReport(NamedTuple):
    """Encapsulate a non-refactored strings auditing report."""

    stale_allowed_strings: list[str | bytes]
    unrefactored_strings: list[tuple[int, str | bytes]]
    ignored_strings: list[str | bytes]


def audit(source: str) -> AuditReport:
    """Audit *source*, returning the auditor."""
    auditor = UnrefactoredStringsAuditor()
    auditor.visit(ast.parse(source))
    return AuditReport(
        unrefactored_strings=auditor.unrefactored_strings,
        stale_allowed_strings=auditor.stale_allowed_strings,
        ignored_strings=auditor.ignored_strings,
    )


@pytest.mark.parametrize(('allowed_strings', 'dangling_strings', 'sourcelines', 'expected_report'), [
    pytest.param(
        [], [],
        ['x = "first_string"', 'y = "second_string"'],
        AuditReport(
            unrefactored_strings = [(1, repr('first_string')), (2, repr('second_string'))],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_unrefactored_strings_detected',
    ),
    pytest.param(
        [], [],
        ['x = b"byte_string"'],
        AuditReport(
            unrefactored_strings = [(1, repr(b'byte_string'))],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_unrefactored_bytes_detected',
    ),
    pytest.param(
        [], [],
        [f'x = "{' ' * 42}"'],
        AuditReport(
            unrefactored_strings = [(1, repr(' ' * 42))],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_unrefactored_whitespace_detected',
    ),
    pytest.param(
        [], [],
        ['x = f"prefix_{i}_suffix"'],
        AuditReport(
            unrefactored_strings = [],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_unrefactored_f_strings_ignored',
    ),
    pytest.param(
        [], [],
        ['"""Module docstring."""'],
        AuditReport(
            unrefactored_strings = [],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_module_docstring_ignored',
    ),
    pytest.param(
        [], [],
        ['class Mock:\n    """Class *Mock* docstring."""'],
        AuditReport(
            unrefactored_strings = [],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_class_docstring_ignored',
    ),
    pytest.param(
        [], [],
        ['def mock():\n    """Function *mock()* docstring."""'],
        AuditReport(
            unrefactored_strings = [],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_function_docstring_ignored',
    ),
    pytest.param(
        [], [],
        ['class Mock:\n    MOCK = "mock_string"\n    MOCKS = ("mock_string_x", "mock_string_y")'],
        AuditReport(
            unrefactored_strings = [],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_class_level_constant_ignored',
    ),
    pytest.param(
        ['allowed_string_x'], ['allowed_string_y'],
        ['x = "allowed_string_x"', 'y = "allowed_string_y"'],
        AuditReport(
            unrefactored_strings = [],
            stale_allowed_strings = [],
            ignored_strings = [],
        ),
        id='test_auditor_allowed_strings_ignored',
    ),
    pytest.param(
        ['allowed_string'], ['dangling_string'],
        ['x = "allowed_string"'],
        AuditReport(
            unrefactored_strings = [],
            stale_allowed_strings = ['dangling_string'],
            ignored_strings = [],
        ),
        id='test_auditor_dangling_strings_detected',
    ),
])
def test_auditor_itself(
    monkeypatch: pytest.MonkeyPatch,
    allowed_strings: list[str | bytes],
    dangling_strings: list[str | bytes],
    sourcelines: list[str],
    expected_report: list[tuple[int, str | bytes]]) -> None:
    """Self-test auditor."""
    monkeypatch.setitem(globals(), 'ALLOWED_UNREFACTORED_STRINGS', (allowed_strings + dangling_strings))

    report = audit('\n'.join(sourcelines))

    assert report == expected_report


def test_unrefactored_strings() -> None:
    """Test for non-refactored strings."""
    report = audit(getsource(sacamantecas))

    assert not report.stale_allowed_strings
    assert not report.unrefactored_strings
    assert not report.ignored_strings
