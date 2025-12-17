"""
Tests for the SRL Parser.
"""
import logging
from srl.parser import SRLParser

logger = logging.getLogger(__name__)

def test_basic_parser_structure():
    """Test parsing a simple rule structure."""
    srl_text = """
    PREFIX ex: <http://example.org/>

    RULE {
        ?s ex:predicate ?o .
    } WHERE {
        ?s ex:source ?o .
    }
    """
    
    logger.info("Testing basic parser structure...")
    parser = SRLParser()
    result = parser.parse(srl_text)
    
    logger.info(f"Parse result type: {type(result)}")
    assert result is not None
    assert len(result.rules) == 1
    
    rule = result.rules[0]
    assert len(rule.head.templates) == 1
    assert len(rule.body.elements) == 1
    
    logger.info("Basic parser structure test passed.")
