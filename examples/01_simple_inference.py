"""
Example 1: Simple Inference Rule

This example demonstrates a basic SHACL 1.2 rule that infers
ancestor relationships from parent relationships.
"""

from rdflib import Graph, Namespace
from src.srl.engine import RuleEngine
from src.srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create an RDF graph with some data
graph = Graph()
graph.bind("ex", EX)

# Add parent relationships
graph.add((EX.Alice, EX.parent, EX.Bob))
graph.add((EX.Bob, EX.parent, EX.Charlie))

print("Input data:")
for s, p, o in graph:
    print(f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}")

# Define a SHACL rule
rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}
"""

# Parse the rule
parser = SRLParser()
rule_set = parser.parse(rule_text)

# Create engine and evaluate rules
engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# Show inferred triples
print("\nInferred triples:")
for s, p, o in result_graph:
    if (s, p, o) not in graph:
        print(f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}")

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
