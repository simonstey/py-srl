"""
python-srl: Python SHACL 1.2 Rules (SRL) Parser and Evaluation Engine

A comprehensive implementation of the SHACL 1.2 Rules specification,
providing parsing, validation, and evaluation capabilities for RDF
rule-based reasoning.
"""

# Parser
from .parser import SRLParser, ParseError

# Engine
from .engine import (
    RuleEngine,
    evaluate_rules,
    StratificationError,
    EvaluationError,
)

# Core AST
from .ast import (
    Rule,
    RuleSet,
    Variable,
    IRI,
    Literal,
    BlankNode,
    RuleHead,
    RuleBody,
    Prologue,
    DataBlock,
    TriplePattern,
    TripleTemplate,
    WellFormednessError,
    ConditionExpression,
    Assignment,
    validate_rule_well_formedness,
)

# Version handling with fallback
try:
    from srl._version import __version__
except ImportError:
    # Fallback for development installations without build
    try:
        from importlib.metadata import version
        __version__ = version("python-srl")
    except Exception:
        __version__ = "0.0.0+unknown"

__author__ = "Simon Steyskal"

__all__ = [
    # Metadata
    "__version__",
    "__author__",
    # Parsing
    "SRLParser",
    # Engine
    "RuleEngine",
    "evaluate_rules",
    # AST - Core structures
    "RuleSet",
    "Rule",
    "RuleHead",
    "RuleBody",
    "Prologue",
    "DataBlock",
    # AST - RDF Terms
    "Variable",
    "IRI",
    "Literal",
    "BlankNode",
    # AST - Patterns
    "TriplePattern",
    "TripleTemplate",
    "ConditionExpression",
    "Assignment",
    # Validation
    "validate_rule_well_formedness",
    # Exceptions
    "ParseError",
    "WellFormednessError",
    "StratificationError",
    "EvaluationError",
]
