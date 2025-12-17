"""
RDF infrastructure for SHACL Rules Language.

This module provides wrappers and utilities for working with RDF graphs
using rdflib as the underlying implementation.
"""

from .namespace import NamespaceManager
from .nodes import IRINode, LiteralNode, BlankNode, RDFNode

__all__ = [
    "NamespaceManager",
    "IRINode",
    "LiteralNode",
    "BlankNode",
    "RDFNode",
]
