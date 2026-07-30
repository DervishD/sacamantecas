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
    # Timestamp stem.
    '_%Y%m%d_%H%M%S',
    # Empty strings.
    ' ', '',
    # Punctuation.
    '.', ', ', '"',
    # Miscellaneous strings.
    'file://', 'utf-8', 'ascii', '==', ' v', r'\W', '_', ':/', '/',
)


class UnrefactoredStringsAuditor(ast.NodeVisitor):
    """Simple auditor to find non-refactored literal strings."""

    def __init__(self) -> None:
        """Initialize."""
        self.stale_allowed_strings: list[str] = list(ALLOWED_UNREFACTORED_STRINGS)
        self.unrefactored_strings: list[tuple[int, str]] = []

    def visit_ignoring_docstring(
        self,
        node:  ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        """Visit *node* but ignoring its docstring, if any."""
        if ast.get_docstring(node, clean=False) is not None:
            del node.body[0]
        self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> None:  # pylint: disable=invalid-name
        """Visit `ast.Module` *node*."""
        self.visit_ignoring_docstring(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # pylint: disable=invalid-name
        """Visit `ast.ClassDef` *node*."""
        self.visit_ignoring_docstring(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:   # pylint: disable=invalid-name
        """Visit `ast.FunctionDef` *node*."""
        self.visit_ignoring_docstring(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:   # pylint: disable=invalid-name
        """Visit `ast.AsyncFunctionDef` *node*."""
        self.visit_ignoring_docstring(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:  # pylint: disable=invalid-name
        """Visit `ast.JoinedStr` node."""
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                self.visit(value)

    def visit_magic_strings(self, node: ast.AST) -> None:
        """Walk *node*, recursively, visiting magic strings.

        Walk *node*, recursively, unwrapping `ast.Tuple`, `ast.List` and
        `ast.Set` containers to reach every leaf, and avoid visiting the
        `ast.Constant` nodes found if they have `str` type.

        That is, strings that are assigned to a name are not considered
        magic strings, however deeply nested inside containers they are.

        Everything else is dispatched through `self.visit`, so any magic
        string nested inside (e.g.) a call argument still gets found via
        the normal `visit_Constant()` path.
        """
        if isinstance(node, ast.Constant):
            return

        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            for elt in node.elts:
                self.visit_magic_strings(elt)
            return

        self.visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # pylint: disable=invalid-name
        """Visit `ast.Assign` *node*."""
        for target in node.targets:
            self.visit(target)
        self.visit_magic_strings(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # pylint: disable=invalid-name
        """Visit `ast.AnnAssign` *node*."""
        self.visit(node.target)
        self.visit(node.annotation)
        if node.value is not None:
            self.visit_magic_strings(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # pylint: disable=invalid-name
        """Visit `ast.AugAssign` *node*."""
        self.visit(node.target)
        self.visit_magic_strings(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:  # pylint: disable=invalid-name
        """Visit `ast.NamedExpr` *node*."""
        self.visit(node.target)
        self.visit_magic_strings(node.value)

    def visit_Dict(self, node: ast.Dict) -> None:  # pylint: disable=invalid-name
        """Visit `ast.Dict` *node*."""
        for key, value in zip(node.keys, node.values, strict=True):
            if key is not None:  # None means a `**expr` unpacking entry.
                self.visit_magic_strings(key)
            self.visit(value)

    def visit_Constant(self, node: ast.Constant) -> None:  # pylint: disable=invalid-name
        """Visit `ast.Constant` *node*."""
        if node.value in ALLOWED_UNREFACTORED_STRINGS:
            with suppress(ValueError):
                self.stale_allowed_strings.remove(node.value)
            return
        if isinstance(node.value, str):
            self.unrefactored_strings.append((node.lineno, repr(node.value)))


class AuditReport(NamedTuple):
    """Encapsulate a non-refactored strings auditing report."""

    stale_allowed_strings: list[str]
    unrefactored_strings: list[tuple[int, str]]


def audit(source: str) -> AuditReport:
    """Audit *source*, returning the auditor."""
    auditor = UnrefactoredStringsAuditor()
    auditor.visit(ast.parse(source))
    return AuditReport(
        unrefactored_strings=sorted(auditor.unrefactored_strings),
        stale_allowed_strings=auditor.stale_allowed_strings,
    )


# pylint: disable-next=unused-variable
def test_unrefactored_strings() -> None:
    """Test for non-refactored strings."""
    report = audit(getsource(sacamantecas))

    assert not report.stale_allowed_strings
    assert not report.unrefactored_strings


########################################################################
#
# The following tests exercise the Auditor itself.
#
########################################################################


@pytest.mark.parametrize(('allowed', 'stale', 'source', 'expected'), [
    pytest.param(
        ['allowed_string_x'], ['allowed_string_z'],
        'x == "allowed_string_x"\ny == "magic"\nz == "allowed_string_z"',
        AuditReport(
            unrefactored_strings=[(2, "'magic'")],
            stale_allowed_strings=[],
        ),
        id='test_allowed_refactored_strings_are_ignored',
    ),
    pytest.param(
        ['allowed_string'], ['stale_allowed_string'],
        'x == "allowed_string"',
        AuditReport(
            unrefactored_strings=[],
            stale_allowed_strings=['stale_allowed_string'],
        ),
        id='test_allowed_refactored_strings_stale_detected',
    ),
])
# pylint: disable-next=unused-variable
def test_allowed_refactored_strings(
    monkeypatch: pytest.MonkeyPatch,
    allowed: list[str],
    stale: list[str],
    source: str,
    expected: AuditReport) -> None:
    """Test the `ALLOWED_UNREFACTORED_STRINGS` mechanism."""
    monkeypatch.setitem(globals(), 'ALLOWED_UNREFACTORED_STRINGS', (allowed + stale))

    report = audit(source)

    assert report == expected


@pytest.mark.parametrize(('source', 'unrefactored'), [
    pytest.param(
        '"""Module docstring."""',
        [],
        id='test_docstrings_ignore_module_docstring',
    ),
    pytest.param(
        'class Example:\n """Class docstring."""',
        [],
        id='test_docstrings_ignore_class_docstring',
    ),
    pytest.param(
        'def example():\n """Function docstring."""',
        [],
        id='test_docstrings_ignore_function_docstring',
    ),
    pytest.param(
        'async def example():\n """Async function docstring."""',
        [],
        id='test_docstrings_ignore_async_function_docstring',
    ),
    pytest.param(
        'def example():\n """Docstring."""\n "This is not a docstring, but a magic string."',
        [(3, "'This is not a docstring, but a magic string.'")],
        id = 'test_docstrings_docstring_is_first_child',
    ),
])
# pylint: disable-next=unused-variable
def test_docstrings(source: str, unrefactored: list[tuple[int, str]]) -> None:
    """Test that docstrings are ignored."""
    report = audit(source)

    assert report.unrefactored_strings == unrefactored


@pytest.mark.parametrize(('source', 'unrefactored'), [
    pytest.param("EXAMPLES = ('x', 'y')", [], id='test_containers_tuple_container'),
    pytest.param("EXAMPLES = ['x', 'y']", [], id='test_containers_list_container'),
    pytest.param("EXAMPLES = {'x', 'y'}", [], id='test_containers_set_container'),
    pytest.param("EXAMPLES = ('x', ('y', 'z'))", [], id='test_containers_nested_tuple'),
    pytest.param("PAIR = 'x', foo('magic')", [(1, "'magic'")], id='test_containers_mixed_tuple'),
    pytest.param('EXAMPLES = ()', [], id='test_containers_empty_tuple'),
])
# pylint: disable-next=unused-variable
def test_containers(source: str, unrefactored: list[tuple[int, str]]) -> None:
    """Test `Auditor` supported containers handling."""
    report = audit(source)

    assert report.unrefactored_strings == unrefactored


@pytest.mark.parametrize(('source', 'unrefactored'), [
    pytest.param("MAPPING = {'a': 'b'}", [(1, "'b'")], id='test_dicts_bare_value_is_magic'),
    pytest.param("MAPPING = {'a': {'nested': 'magic'}}", [(1, "'magic'")], id='test_dicts_nested_key_is_not_magic'),
    pytest.param('MAPPING = {**foo}', [], id='test_dicts_unpacked_expr_as_key_is_none'),
    pytest.param("MAPPING = {**foo('magic')}", [(1, "'magic'")], id='test_dicts_unpacked_expr_with_bare_string'),
])
# pylint: disable-next=unused-variable
def test_dicts(source: str, unrefactored: list[tuple[int, str]]) -> None:
    """Test `ast.Dict` nodes handling."""
    report = audit(source)

    assert report.unrefactored_strings == unrefactored


@pytest.mark.parametrize(('source', 'unrefactored'), [
    pytest.param('x = f"prefix_{i}_suffix"', [], id='test_fstrings_literal_fragments_ignored'),
    pytest.param('x = f"{foo(\'magic\')}"', [(1, "'magic'")], id='test_fstrings_bare_string_in_expression_is_magic'),
])
# pylint: disable-next=unused-variable
def test_fstrings(source: str, unrefactored: list[tuple[int, str]]) -> None:
    """Test f-string literals are ignored but expressions are not."""
    report = audit(source)

    assert report.unrefactored_strings == unrefactored


# pylint: disable-next=unused-variable
def test_fields_outside_body() -> None:
    """Test that every node field is checked, not just body.

    This covers the case where node fields are visited by hand instead
    of using `generic_visit()`. The sample chosen is a magic string used
    as a function argument default value but any other field outside the
    node's `body` element (decorator arguments, base classes, a literal
    return annotation, etc.) would be an equally valid choice, so one is
    is representative of all.
    """
    report = audit('def foo(x="magic"):\n pass\n')

    assert report.unrefactored_strings == [(1, "'magic'")]
