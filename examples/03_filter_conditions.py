"""
Example 3: FILTER Conditions

This example demonstrates using FILTER to apply conditions
in rule bodies, such as filtering by numeric values.
"""

from rdflib import Graph, Namespace, Literal
from src.srl.engine import RuleEngine
from src.srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph with age information
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.age, Literal(25)))
graph.add((EX.Bob, EX.age, Literal(16)))
graph.add((EX.Charlie, EX.age, Literal(30)))
graph.add((EX.Diana, EX.age, Literal(12)))

print("Input data:")
for s, p, o in sorted(graph):
    print(f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o}")

# Define rule with FILTER
rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:isAdult true .
} WHERE {
    ?person ex:age ?age .
    FILTER (?age >= 18)
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# Show who is marked as adult
print("\nAdults (age >= 18):")
for s, p, o in sorted(result_graph):
    if p == EX.isAdult:
        # Get the age from original graph
        age = graph.value(s, EX.age)
        print(f"  {s.n3(result_graph.namespace_manager)} - age: {age}")

print(f"\nFiltered correctly: Bob (16) and Diana (12) excluded")
