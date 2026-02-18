#! /usr/bin/env python3
"""Test suite for unused constants and messages."""
import ast
import inspect

import pytest

import sacamantecas


class UsageTrackerVisitor(ast.NodeVisitor):
    """Simple visitor for checking if all class attributes are used."""

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
                if not isinstance(target, ast.Name):
                    continue
                self.unused_attributes.add(target.id)
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


CODETREE = ast.parse(inspect.getsource(sacamantecas))


@pytest.mark.parametrize('classname', [
    sacamantecas.Constants.__name__,
    sacamantecas.Messages.__name__,
    sacamantecas.ExitCodes.__name__,
], ids=[
    'test_no_unused_Constants',
    'test_no_unused_Messages',
    'test_no_unused_Exitcodes',
])
def test_no_unused_attributes(classname: str) -> None:   # pylint: disable=unused-variable
    """Test that all attributes in classname are used."""
    visitor = UsageTrackerVisitor(classname)
    visitor.visit(CODETREE)

    assert visitor.unused_attributes == set()
