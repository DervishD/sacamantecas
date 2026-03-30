#! /usr/bin/env python3
"""Test suite for non-refactored code strings."""
import ast
from contextlib import suppress
from inspect import getsource
from typing import NamedTuple

import sacamantecas

ALLOWED_UNREFACTORED_STRINGS = (
    # Early platform check.
    'win32', '\nThis program is compatible only with the Win32 platform.\n',
    # Python well-known strings.
    'frozen', '__main__', 'w', '%s',
    # For typing hints.
    'TextIOWrapper',
    # Allowed empty or whitespace strings.
    ' ', '', b'',
    # Miscellaneous strings.
    'Project-URL', ', ', 'source', 'reconfigure', '.post', '==', ' v',
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




def test_unrefactored_strings() -> None:
    """Test for non-refactored strings."""
    report = audit(getsource(sacamantecas))

    assert not report.stale_allowed_strings
    assert not report.unrefactored_strings
    assert not report.ignored_strings
