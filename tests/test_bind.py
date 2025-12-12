"""Debug BIND/CONCAT evaluation"""
from rdflib import Graph, Namespace, Literal
from src.srl.parser import SRLParser
from src.srl.engine import RuleEngine

EX = Namespace("http://example.org/")

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

print("Parsing...")
parser = SRLParser()
rule_set = parser.parse(rule_text)
print(f"✓ Parsed {len(rule_set.rules)} rule(s)")

rule = rule_set.rules[0]
print(f"\nRule body elements: {len(rule.body.elements)}")
for i, elem in enumerate(rule.body.elements):
    print(f"  [{i}] {type(elem).__name__}: {elem}")

print("\nExecuting...")
engine = RuleEngine(rule_set)
result = engine.evaluate(g, inplace=False)

print(f"\n✓ Result: {len(result)} triples")
for s, p, o in result:
    print(f"  {s} {p} {o}")

# Check for expected triple
if (EX.Person1, EX.fullName, Literal("John Doe")) in result:
    print("\n✓ SUCCESS: fullName triple generated!")
else:
    print("\n✗ FAIL: fullName triple NOT found")
    print(f"Expected: {EX.Person1} {EX.fullName} 'John Doe'")
