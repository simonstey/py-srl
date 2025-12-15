"""Tests for expression parsing into the AST.

These tests focus on ensuring that comparison operators are preserved when
parsing FILTER expressions (e.g. ?age >= 18) and are represented as BinaryOp
nodes in the AST.
"""

from src.srl.ast.nodes import (
    BinaryOp,
    BinaryOperator,
    ConditionExpression,
    IRI,
    Literal,
    Variable,
)
from src.srl.parser import SRLParser


def test_filter_relational_expressions_are_parsed_fully():
    srl_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?person ex:isAdult true .
    } WHERE {
        ?person ex:age ?age .
        FILTER (?age >= 18)
        FILTER (18 < ?age)
    }
    """

    rule_set = SRLParser().parse(srl_text)
    assert len(rule_set.rules) == 1

    rule = rule_set.rules[0]
    filters = [e for e in rule.body.elements if isinstance(e, ConditionExpression)]
    assert len(filters) == 2

    # FILTER (?age >= 18)
    expr1 = filters[0].expression
    assert isinstance(expr1, BinaryOp)
    assert expr1.operator == BinaryOperator.GE
    assert expr1.left == Variable(name="age")
    assert isinstance(expr1.right, Literal)
    assert expr1.right.value == "18"
    assert expr1.right.datatype == IRI("http://www.w3.org/2001/XMLSchema#integer")

    # FILTER (18 < ?age)
    expr2 = filters[1].expression
    assert isinstance(expr2, BinaryOp)
    assert expr2.operator == BinaryOperator.LT
    assert isinstance(expr2.left, Literal)
    assert expr2.left.value == "18"
    assert expr2.left.datatype == IRI("http://www.w3.org/2001/XMLSchema#integer")
    assert expr2.right == Variable(name="age")
