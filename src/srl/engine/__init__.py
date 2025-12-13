"""
SHACL 1.2 Rules - Engine module.

This module provides rule evaluation functionality including solution mappings,
expression evaluation, and fixpoint iteration.
"""

from .engine import RuleEngine, evaluate_rules
from .expressions import eval_expr, effective_boolean_value
from .rules import eval_rule
from .solutions import SolutionMapping, compatible, merge, graphMatch
from .stratification import stratify_rules, StratificationError

__all__ = [
    # Solution mappings
    "SolutionMapping",
    "compatible",
    "merge",
    "graphMatch",
    
    # Expression evaluation
    "eval_expr",
    "effective_boolean_value",
    
    # Rule evaluation
    "eval_rule",
    
    # Stratification
    "stratify_rules",
    "StratificationError",
    
    # Main engine
    "RuleEngine",
    "evaluate_rules",
]
