"""Debug effective_boolean_value"""
from rdflib import Literal as RDFLiteral, Namespace

XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# Test boolean literal created from comparison
result = True
lit = RDFLiteral(result, datatype=XSD.boolean)

print(f"Literal: {lit}")
print(f"Datatype: {lit.datatype}")
print(f"Value: {lit.value}")
print(f"Value type: {type(lit.value)}")

# Try the EBV logic
if lit.datatype == XSD.boolean:
    print(f"Is boolean datatype: True")
    print(f"Value.lower() attempt:")
    try:
        result = lit.value.lower() in ('true', '1')
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  ERROR: {e}")
        print(f"  This is the bug - value is {type(lit.value)}, not string!")
