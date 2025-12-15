"""Test effective boolean value logic."""

import logging
from rdflib import Literal as RDFLiteral, Namespace
from srl.engine.expressions import effective_boolean_value

logger = logging.getLogger(__name__)
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

def test_effective_boolean_value():
    """Test EBV calculation for various literals."""
    
    # Boolean True
    lit_true = RDFLiteral(True, datatype=XSD.boolean)
    assert effective_boolean_value(lit_true) is True
    
    # Boolean False
    lit_false = RDFLiteral(False, datatype=XSD.boolean)
    assert effective_boolean_value(lit_false) is False
    
    # String "true" (boolean)
    lit_str_true = RDFLiteral("true", datatype=XSD.boolean)
    assert effective_boolean_value(lit_str_true) is True
    
    # String "false" (boolean)
    lit_str_false = RDFLiteral("false", datatype=XSD.boolean)
    assert effective_boolean_value(lit_str_false) is False
    
    # Non-empty string
    lit_str = RDFLiteral("hello")
    assert effective_boolean_value(lit_str) is True
    
    # Empty string
    lit_empty = RDFLiteral("")
    assert effective_boolean_value(lit_empty) is False
    
    # Numeric non-zero
    lit_num = RDFLiteral(1)
    assert effective_boolean_value(lit_num) is True
    
    # Numeric zero
    lit_zero = RDFLiteral(0)
    assert effective_boolean_value(lit_zero) is False
    
    logger.info("EBV tests passed.")
