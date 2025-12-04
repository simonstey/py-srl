"""
Simple test to verify basic rule evaluation.
"""

from rdflib import Graph, Namespace, Literal
from src.srl.parser import SRLParser
from src.srl.engine import RuleEngine

# Define namespace
EX = Namespace("http://example.org/")

# Simple SRL rule
srl_text = """
PREFIX ex: <http://example.org/>

RULE { ?x ex:derived ?y . } WHERE { ?x ex:source ?y . }
"""

print("Parsing SRL...")
parser = SRLParser()
rule_set = parser.parse(srl_text)
print(f"Parsed {len(rule_set.rules)} rule(s)")

# Create data
print("\nCreating data graph...")
data = Graph()
data.bind("ex", EX)
data.add((EX.A, EX.source, EX.B))
print(f"Data has {len(data)} triple(s)")

# Evaluate
print("\nEvaluating rules...")
engine = RuleEngine(rule_set)
result = engine.evaluate(data, inplace=False)

print(f"\nResult has {len(result)} triple(s)")
print("\nAll triples:")
for s, p, o in result:
    print(f"  {s.n3(result.namespace_manager)} {p.n3(result.namespace_manager)} {o.n3(result.namespace_manager)}")

print("\n✓ Test complete!")
