"""Debug rule AST to see what body elements are created"""
from srl.parser import SRLParser
from srl.ast.nodes import *

rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:isAdult true .
} WHERE {
    ?person ex:age ?age .
    FILTER (?age >= 18)
}
"""

# Parse
parser = SRLParser()
result = parser.parse(rule_text)
print(f"Parsed {len(result.rules)} rule(s)")

rule = result.rules[0]
print(f"\nRule: {rule}")
print(f"Rule type: {type(rule)}")
print(f"Body: {rule.body}")
print(f"Body type: {type(rule.body)}")
print(f"Body elements: {len(rule.body.elements)}")

for i, elem in enumerate(rule.body.elements):
    print(f"\nElement {i}:")
    print(f"  Type: {type(elem)}")
    print(f"  Value: {elem}")
    
    if isinstance(elem, ConditionExpression):
        print(f"  Is ConditionExpression: YES")
        print(f"  Expression: {elem.expression}")
        print(f"  Expression type: {type(elem.expression)}")
    else:
        print(f"  Is ConditionExpression: NO")
