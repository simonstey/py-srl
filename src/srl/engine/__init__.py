"""
SHACL 1.2 Rules - Engine module.

This module provides rule evaluation functionality including solution mappings,
expression evaluation, and fixpoint iteration.
"""

from .engine import RuleEngine, evaluate_rules, ExtensionError
from .expressions import eval_expr, effective_boolean_value, EvaluationError
from .rules import eval_rule
from .solutions import SolutionMapping, compatible, merge, graphMatch
from .stratification import (
    stratify,
    stratify_rules,
    StratificationLayer,
    StratificationError,
    build_dependency_graph,
    possibly_matches,
)

__all__ = [
    # Solution mappings
    "SolutionMapping",
    "compatible",
    "merge",
    "graphMatch",
    # Expression evaluation
    "eval_expr",
    "effective_boolean_value",
    "EvaluationError",
    # Rule evaluation
    "eval_rule",
    # Stratification
    "stratify",
    "stratify_rules",
    "StratificationLayer",
    "StratificationError",
    "build_dependency_graph",
    "possibly_matches",
    # Main engine
    "RuleEngine",
    "evaluate_rules",
    "ExtensionError",
]
