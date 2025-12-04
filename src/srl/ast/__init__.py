"""
SHACL 1.2 Rules - Abstract Syntax Tree (AST) module.

This module defines the AST node classes for the Shape Rule Language (SRL)
as specified in Section 3 of the SHACL 1.2 Rules specification.
"""

from .nodes import (
    # Core AST components
    Variable,
    Expression,
    TriplePattern,
    TripleTemplate,
    ConditionExpression,
    NegationElement,
    Assignment,
    AggregationElement,
    RuleBodyElement,
    RuleHead,
    RuleBody,
    Rule,
    RuleSet,
    DataBlock,
    
    # Supporting types
    RDFTerm,
    IRI,
    Literal,
    BlankNode,
    
    # Operators and built-ins
    BinaryOp,
    UnaryOp,
    FunctionCall,
    BuiltInCall,
)

__all__ = [
    "Variable",
    "Expression",
    "TriplePattern",
    "TripleTemplate",
    "ConditionExpression",
    "NegationElement",
    "Assignment",
    "AggregationElement",
    "RuleBodyElement",
    "RuleHead",
    "RuleBody",
    "Rule",
    "RuleSet",
    "DataBlock",
    "RDFTerm",
    "IRI",
    "Literal",
    "BlankNode",
    "BinaryOp",
    "UnaryOp",
    "FunctionCall",
    "BuiltInCall",
]
