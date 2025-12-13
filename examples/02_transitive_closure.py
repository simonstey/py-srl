"""
Example 2: Transitive Closure

This example shows how to compute transitive closure using
recursive rules and stratification.
"""

from rdflib import Graph, Namespace
from src.srl.engine import RuleEngine
from src.srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph with parent relationships
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.parent, EX.Bob))
graph.add((EX.Bob, EX.parent, EX.Charlie))
graph.add((EX.Charlie, EX.parent, EX.Diana))

print("Input data (parent relationships):")
for s, p, o in graph:
    print(f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}")

# Define recursive rules for transitive closure
rule_text = """
PREFIX ex: <http://example.org/>

# Base case: parent is ancestor
RULE {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}

# Recursive case: ancestor of ancestor
RULE {
    ?x ex:ancestor ?z .
} WHERE {
    ?x ex:ancestor ?y .
    ?y ex:ancestor ?z .
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# Show all ancestor relationships
print("\nInferred ancestor relationships:")
for s, p, o in sorted(result_graph):
    if p == EX.ancestor:
        print(f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}")

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
print("Transitive closure computed successfully!")
