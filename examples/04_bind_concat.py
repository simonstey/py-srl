"""
Example 4: BIND and String Operations

This example shows using BIND to create new variables
with computed values, including string concatenation.
"""

from rdflib import Graph, Namespace, Literal
from src.srl.engine import RuleEngine
from src.srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph with name information
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Person1, EX.firstName, Literal("John")))
graph.add((EX.Person1, EX.lastName, Literal("Doe")))
graph.add((EX.Person2, EX.firstName, Literal("Jane")))
graph.add((EX.Person2, EX.lastName, Literal("Smith")))

print("Input data:")
for s, p, o in sorted(graph):
    print(f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o}")

# Define rule with BIND and CONCAT
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

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# Show generated full names
print("\nGenerated full names:")
for s, p, o in sorted(result_graph):
    if p == EX.fullName:
        print(f"  {s.n3(result_graph.namespace_manager)} -> {o}")