"""
Simple test to verify basic rule evaluation.
"""

import logging
from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

logger = logging.getLogger(__name__)
EX = Namespace("http://example.org/")

def test_simple_rule_evaluation():
    """Test a very basic rule evaluation."""
    srl_text = """
    PREFIX ex: <http://example.org/>

    RULE { ?x ex:derived ?y . } WHERE { ?x ex:source ?y . }
    """

    logger.info("Parsing SRL...")
    parser = SRLParser()
    rule_set = parser.parse(srl_text)
    assert len(rule_set.rules) == 1

    logger.info("Creating data graph...")
    data = Graph()
    data.bind("ex", EX)
    data.add((EX.A, EX.source, EX.B))
    
    logger.info("Evaluating rules...")
    engine = RuleEngine(rule_set)
    result = engine.evaluate(data, inplace=False)

    logger.info(f"Result has {len(result)} triple(s)")
    
    assert (EX.A, EX.derived, EX.B) in result
    logger.info("Simple rule evaluation passed.")
