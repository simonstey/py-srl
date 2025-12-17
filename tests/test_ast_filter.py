"""Test rule AST structure for filters."""

import logging
from srl.ast.nodes import ConditionExpression, BinaryOp, BinaryOperator, Variable, Literal
from srl.parser import SRLParser

logger = logging.getLogger(__name__)

def test_ast_filter_structure():
    """Verify AST structure for FILTER expressions."""
    rule_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?person ex:isAdult true .
    } WHERE {
        ?person ex:age ?age .
        FILTER (?age >= 18)
        FILTER (17 < ?age )
    }
    """

    logger.info("Parsing rule text...")
    parser = SRLParser()
    result = parser.parse(rule_text)
    
    assert len(result.rules) == 1
    rule = result.rules[0]
    
    logger.info(f"Body elements: {len(rule.body.elements)}")
    
    # We expect 3 elements: TriplePattern, Filter, Filter
    assert len(rule.body.elements) == 3
    
    # Check first filter
    filter1 = rule.body.elements[1]
    assert isinstance(filter1, ConditionExpression)
    assert isinstance(filter1.expression, BinaryOp)
    assert filter1.expression.operator == BinaryOperator.GE
    assert isinstance(filter1.expression.left, Variable)
    assert filter1.expression.left.name == "age"
    assert isinstance(filter1.expression.right, Literal)
    assert filter1.expression.right.value == "18"
    logger.info(f"First filter verified: {filter1.expression.left.name} {filter1.expression.operator} {filter1.expression.right.value}")
    
    # Check second filter
    filter2 = rule.body.elements[2]
    assert isinstance(filter2, ConditionExpression)
    assert isinstance(filter2.expression, BinaryOp)
    assert filter2.expression.operator == BinaryOperator.LT
    assert isinstance(filter2.expression.left, Literal)
    assert filter2.expression.left.value == "17"
    assert isinstance(filter2.expression.right, Variable)
    assert filter2.expression.right.name == "age"    
    logger.info(f"Second filter verified: {filter2.expression.left.value} {filter2.expression.operator} {filter2.expression.right.name}")
    logger.info("AST filter structure verified.")

