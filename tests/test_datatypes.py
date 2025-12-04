"""Debug literal datatypes."""

from rdflib import Literal, Namespace

XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

lit1 = Literal(16)
lit2 = Literal(25)
lit3 = Literal("16")

print(f"Literal(16): value={lit1.value}, datatype={lit1.datatype}, type={type(lit1.value)}")
print(f"Literal(25): value={lit2.value}, datatype={lit2.datatype}, type={type(lit2.value)}")
print(f'Literal("16"): value={lit3.value}, datatype={lit3.datatype}, type={type(lit3.value)}')

print(f"\nXSD.integer = {XSD.integer}")
print(f"lit1.datatype == XSD.integer: {lit1.datatype == XSD.integer}")
print(f"lit1.datatype in (...): {lit1.datatype in (XSD.integer, XSD.decimal, XSD.double)}")
