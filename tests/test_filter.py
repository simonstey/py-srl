"""Test FILTER evaluation."""

import logging
from rdflib import Graph, Namespace, Literal

from srl.engine import RuleEngine
from srl.parser import SRLParser

logger = logging.getLogger(__name__)
EX = Namespace("http://example.org/")

def test_filter_evaluation():
    """Test that FILTER correctly filters solution mappings."""
    srl_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?person ex:isAdult true .
    } WHERE {
        ?person ex:age ?age .
        FILTER (?age >= 18)
    }
    """

    logger.info("Parsing rule set...")
    parser = SRLParser()
    rule_set = parser.parse(srl_text)

    data = Graph()
    data.bind("ex", EX)
    data.add((EX.Alice, EX.age, Literal(25)))
    data.add((EX.Bob, EX.age, Literal(16)))
    data.add((EX.Charlie, EX.age, Literal(30)))

    logger.info(f"Input data graph size: {len(data)}")

    engine = RuleEngine(rule_set)
    result = engine.evaluate(data, inplace=False)

    logger.info(f"Result graph size: {len(result)}")

    # Check expected results
    assert (EX.Alice, EX.isAdult, Literal(True)) in result
    assert (EX.Charlie, EX.isAdult, Literal(True)) in result
    
    # Check negative result (Bob is 16)
    assert (EX.Bob, EX.isAdult, Literal(True)) not in result
    
    logger.info("Filter evaluation test passed.")
