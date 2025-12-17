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
    Annotation,
    RuleBodyElement,
    RuleHead,
    RuleBody,
    Rule,
    RuleSet,
    DataBlock,
    Prologue,
    # Property Paths
    InversePath,
    PathSequence,
    PropertyPath,
    # Declarations
    TransitiveDeclaration,
    SymmetricDeclaration,
    InverseDeclaration,
    Declaration,
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
    BinaryOperator,
    UnaryOperator,
    # Validation
    WellFormednessError,
    validate_rule_well_formedness,
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
    "Annotation",
    "RuleBodyElement",
    "RuleHead",
    "RuleBody",
    "Rule",
    "RuleSet",
    "DataBlock",
    "Prologue",
    "InversePath",
    "PathSequence",
    "PropertyPath",
    "TransitiveDeclaration",
    "SymmetricDeclaration",
    "InverseDeclaration",
    "Declaration",
    "RDFTerm",
    "IRI",
    "Literal",
    "BlankNode",
    "BinaryOp",
    "UnaryOp",
    "FunctionCall",
    "BuiltInCall",
    "BinaryOperator",
    "UnaryOperator",
    "WellFormednessError",
    "validate_rule_well_formedness",
]
