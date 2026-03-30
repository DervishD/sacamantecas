#! /usr/bin/env python3
"""Test suite for unused constants and messages."""
import ast
import inspect
from typing import cast

import pytest

import sacamantecas


class UsageTrackerAuditor(ast.NodeVisitor):
    """Simple auditor for checking if all class attributes are used."""

    def __init__(self, class_name: str) -> None:
        """Initialize visitor with class name."""
        self.class_name = class_name
        self.within_classdef = False
        self.within_attributedef = False
        self.unused_attributes: set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # pylint: disable=invalid-name
        """Mark class definition for further processing."""
        if node.name == self.class_name:
            self.within_classdef = True
        self.generic_visit(node)
        self.within_classdef = False

    def visit_Assign(self, node: ast.Assign) -> None:  # pylint: disable=invalid-name
        """Mark class attribute definitions for further processing."""
        if self.within_classdef:
            for target in node.targets:
                self.unused_attributes.add(cast('ast.Name', target).id)
            self.within_attributedef = True
            self.generic_visit(node.value)
            self.within_attributedef = False
        else:
            self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # pylint: disable=invalid-name
        """Find attribute usage within class definition itself."""
        if not self.within_classdef or not self.within_attributedef or \
            not node.id.isupper() or node.id.startswith('__'):
            self.generic_visit(node)
            return
        self.unused_attributes.discard(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # pylint: disable=invalid-name
        """Find attribute usage."""
        if not isinstance(node.value, ast.Name) or node.value.id != self.class_name:
            self.generic_visit(node)
            return
        self.unused_attributes.discard(node.attr)


@pytest.fixture(scope='module')
def codetree() -> ast.Module:
    """Fixture to get the parsed code tree of the module under test."""
    return ast.parse(inspect.getsource(sacamantecas))


@pytest.mark.parametrize('classname', [
    pytest.param(sacamantecas.Constants.__name__, id='test_no_unused_Constants_attributes'),
    pytest.param(sacamantecas.Messages.__name__, id='test_no_unused_Messages_attributes'),
    pytest.param(sacamantecas.ExitCodes.__name__, id='test_no_unused_ExitCodes_attributes'),
])
def test_no_unused_class_attributes(classname: str, codetree: ast.Module) -> None:
    """Test that all attributes in classname are used."""
    auditor = UsageTrackerAuditor(classname)
    auditor.visit(codetree)

    assert auditor.unused_attributes == set()
