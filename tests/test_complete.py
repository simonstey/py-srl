"""
Comprehensive test of SHACL 1.2 Rules implementation.

Tests the complete pipeline: parsing SRL → evaluating rules → generating inferences.
"""

import logging
from rdflib import Graph, Namespace, Literal

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespaces
EX = Namespace("http://example.org/")
logger = logging.getLogger(__name__)


def test_simple_inference():
    """Test 1: Simple inference rule: parent → ancestor"""
    logger.info("Starting Test 1: Simple inference rule")
    
    srl_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?x ex:ancestor ?y .
    } WHERE {
        ?x ex:parent ?y .
    }
    """
    
    # Parse the rule
    parser = SRLParser()
    rule_set = parser.parse(srl_text)
    logger.info(f"Parsed rule set: {len(rule_set.rules)} rule(s)")
    
    # Create test data
    data_graph = Graph()
    data_graph.bind("ex", EX)
    data_graph.add((EX.Alice, EX.parent, EX.Bob))
    data_graph.add((EX.Bob, EX.parent, EX.Charlie))
    
    logger.info(f"Data graph: {len(data_graph)} triple(s)")
    
    # Evaluate rules
    engine = RuleEngine(rule_set)
    result_graph = engine.evaluate(data_graph, inplace=False)
    
    logger.info(f"Result graph: {len(result_graph)} triple(s)")
    
    # Verify expected inferences
    assert (EX.Alice, EX.ancestor, EX.Bob) in result_graph
    assert (EX.Bob, EX.ancestor, EX.Charlie) in result_graph
    logger.info("All expected triples inferred!")


def test_transitive_closure():
    """Test 2: Transitive closure: ancestor → ancestor"""
    logger.info("Starting Test 2: Transitive closure")
    
    srl_text = """
    PREFIX ex: <http://example.org/>

    # Base case: parent is ancestor
    RULE {
        ?x ex:ancestor ?y .
    } WHERE {
        ?x ex:parent ?y .
    }

    # Transitive case: ancestor of ancestor is ancestor
    RULE {
        ?x ex:ancestor ?z .
    } WHERE {
        ?x ex:ancestor ?y .
        ?y ex:ancestor ?z .
    }
    """
    
    parser = SRLParser()
    rule_set = parser.parse(srl_text)
    logger.info(f"Parsed rule set: {len(rule_set.rules)} rule(s)")
    
    # Create test data with longer chain
    data_graph = Graph()
    data_graph.bind("ex", EX)
    data_graph.add((EX.Alice, EX.parent, EX.Bob))
    data_graph.add((EX.Bob, EX.parent, EX.Charlie))
    data_graph.add((EX.Charlie, EX.parent, EX.Diana))
    
    logger.info(f"Data graph: {len(data_graph)} triple(s)")
    
    # Evaluate rules
    engine = RuleEngine(rule_set)
    result_graph = engine.evaluate(data_graph, inplace=False)
    
    logger.info(f"Result graph: {len(result_graph)} triple(s)")
    
    # Verify transitive closure
    assert (EX.Alice, EX.ancestor, EX.Bob) in result_graph
    assert (EX.Alice, EX.ancestor, EX.Charlie) in result_graph
    assert (EX.Alice, EX.ancestor, EX.Diana) in result_graph
    assert (EX.Bob, EX.ancestor, EX.Charlie) in result_graph
    assert (EX.Bob, EX.ancestor, EX.Diana) in result_graph
    assert (EX.Charlie, EX.ancestor, EX.Diana) in result_graph
    logger.info("Transitive closure computed correctly!")


def test_filter_condition():
    """Test 3: Rule with FILTER condition"""
    logger.info("Starting Test 3: Rule with FILTER condition")
    
    srl_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?person ex:isAdult true .
    } WHERE {
        ?person ex:age ?age .
        FILTER (?age >= 18)
    }
    """
    
    parser = SRLParser()
    rule_set = parser.parse(srl_text)
    logger.info(f"Parsed rule set: {len(rule_set.rules)} rule(s)")
    
    # Create test data
    data_graph = Graph()
    data_graph.bind("ex", EX)
    data_graph.add((EX.Alice, EX.age, Literal(25)))
    data_graph.add((EX.Bob, EX.age, Literal(16)))
    data_graph.add((EX.Charlie, EX.age, Literal(30)))
    
    logger.info(f"Data graph: {len(data_graph)} triple(s)")
    
    # Evaluate rules
    engine = RuleEngine(rule_set)
    result_graph = engine.evaluate(data_graph, inplace=False)
    
    logger.info(f"Result graph: {len(result_graph)} triple(s)")
    
    # Verify filter worked
    assert (EX.Alice, EX.isAdult, Literal(True)) in result_graph
    assert (EX.Charlie, EX.isAdult, Literal(True)) in result_graph
    assert (EX.Bob, EX.isAdult, Literal(True)) not in result_graph  # Bob is 16
    logger.info("FILTER condition applied correctly!")


def test_bind_assignment():
    """Test 4: Rule with BIND (assignment)"""
    logger.info("Starting Test 4: Rule with BIND (assignment)")
    
    srl_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?person ex:fullName ?fullName .
    } WHERE {
        ?person ex:firstName ?first .
        ?person ex:lastName ?last .
        BIND(CONCAT(?first, " ", ?last) AS ?fullName)
    }
    """
    
    parser = SRLParser()
    rule_set = parser.parse(srl_text)
    logger.info(f"Parsed rule set: {len(rule_set.rules)} rule(s)")
    
    # Create test data
    data_graph = Graph()
    data_graph.bind("ex", EX)
    data_graph.add((EX.Person1, EX.firstName, Literal("John")))
    data_graph.add((EX.Person1, EX.lastName, Literal("Doe")))
    data_graph.add((EX.Person2, EX.firstName, Literal("Jane")))
    data_graph.add((EX.Person2, EX.lastName, Literal("Smith")))
    
    logger.info(f"Data graph: {len(data_graph)} triple(s)")
    
    # Evaluate rules
    engine = RuleEngine(rule_set)
    result_graph = engine.evaluate(data_graph, inplace=False)
    
    logger.info(f"Result graph: {len(result_graph)} triple(s)")
    
    # Verify BIND worked
    assert (EX.Person1, EX.fullName, Literal("John Doe")) in result_graph
    assert (EX.Person2, EX.fullName, Literal("Jane Smith")) in result_graph
    logger.info("BIND expression evaluated correctly!")
