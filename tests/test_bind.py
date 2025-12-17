"""Test BIND/CONCAT evaluation."""

import logging
from rdflib import Graph, Namespace, Literal

from srl.engine import RuleEngine
from srl.parser import SRLParser


logger = logging.getLogger(__name__)
EX = Namespace("http://example.org/")

def test_bind_concat():
    """Test BIND with CONCAT function."""
    # Test data
    g = Graph()
    g.bind("ex", EX)
    g.add((EX.Person1, EX.firstName, Literal("John")))
    g.add((EX.Person1, EX.lastName, Literal("Doe")))

    # Rule with BIND
    rule_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?person ex:fullName ?fullName .
    } WHERE {
        ?person ex:firstName ?first .
        ?person ex:lastName ?last .
        BIND(CONCAT(?first, " ", ?last) AS ?fullName)
    }
    """

    logger.info("Parsing rule set...")
    parser = SRLParser()
    rule_set = parser.parse(rule_text)
    
    assert len(rule_set.rules) == 1
    rule = rule_set.rules[0]
    logger.info(f"Rule body elements: {len(rule.body.elements)}")

    logger.info("Executing rule engine...")
    engine = RuleEngine(rule_set)
    result = engine.evaluate(g, inplace=False)

    logger.info(f"Result graph size: {len(result)}")
    
    # Check for expected triple
    assert (EX.Person1, EX.fullName, Literal("John Doe")) in result
    logger.info("BIND/CONCAT test passed.")
