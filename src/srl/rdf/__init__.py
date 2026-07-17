"""
RDF infrastructure for SHACL Rules Language.

This module provides wrappers and utilities for working with RDF graphs
using rdflib as the underlying implementation.
"""

from .namespace import NamespaceManager
from .nodes import IRINode, LiteralNode, BlankNode, RDFNode
from . import vocab
from .reader import parse_rdf_rule_set, parse_rdf_file, RDFSyntaxError
from .writer import to_rdf_graph, serialize

__all__ = [
    "NamespaceManager",
    "IRINode",
    "LiteralNode",
    "BlankNode",
    "RDFNode",
    "vocab",
    "parse_rdf_rule_set",
    "parse_rdf_file",
    "RDFSyntaxError",
    "to_rdf_graph",
    "serialize",
]
