"""Test literal datatypes assumptions."""

import logging
from rdflib import Literal, Namespace

logger = logging.getLogger(__name__)
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

def test_literal_datatypes():
    """Verify RDFLib literal datatype behavior."""
    lit1 = Literal(16)
    lit2 = Literal(25)
    lit3 = Literal("16")

    logger.info(f"Literal(16): value={lit1.value}, datatype={lit1.datatype}, type={type(lit1.value)}")
    logger.info(f"Literal(25): value={lit2.value}, datatype={lit2.datatype}, type={type(lit2.value)}")
    logger.info(f'Literal("16"): value={lit3.value}, datatype={lit3.datatype}, type={type(lit3.value)}')

    assert lit1.datatype == XSD.integer
    assert lit2.datatype == XSD.integer
    # Default string literal has no datatype (or xsd:string implied)
    assert lit3.datatype is None or lit3.datatype == XSD.string
    
    assert lit1.datatype in (XSD.integer, XSD.decimal, XSD.double)
    logger.info("Datatype assumptions verified.")
