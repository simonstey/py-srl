"""
Example 4: FILTER Conditions

FILTER keeps only the solution mappings whose expression is true. This example
shows a simple numeric comparison, a compound condition (&&), a range check,
and an IN membership test.
"""

from rdflib import Graph, Literal, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph with people, ages and departments
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.age, Literal(25)))
graph.add((EX.Alice, EX.dept, Literal("Engineering")))
graph.add((EX.Bob, EX.age, Literal(16)))
graph.add((EX.Bob, EX.dept, Literal("Sales")))
graph.add((EX.Charlie, EX.age, Literal(30)))
graph.add((EX.Charlie, EX.dept, Literal("Design")))
graph.add((EX.Diana, EX.age, Literal(70)))
graph.add((EX.Diana, EX.dept, Literal("Engineering")))

print("Input data:")
for s, p, o in sorted(graph):
    print(f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o}")

# Three rules, each guarded by a different FILTER shape:
#   - working-age adults:  a compound && range check
#   - product staff:       IN membership over a value list
rule_text = """
PREFIX ex: <http://example.org/>

# Compound condition: working-age adult (18..64 inclusive).
RULE {
    ?person ex:workingAgeAdult true .
} WHERE {
    ?person ex:age ?age .
    FILTER (?age >= 18 && ?age < 65)
}

# Membership test: anyone in a product-building department.
RULE {
    ?person ex:buildsProduct true .
} WHERE {
    ?person ex:dept ?dept .
    FILTER (?dept IN ("Engineering", "Design"))
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# Report each classification the rules produced
print("\nWorking-age adults (18 <= age < 65):")
for s in sorted(result_graph.subjects(EX.workingAgeAdult, Literal(True))):
    print(f"  {s.n3(result_graph.namespace_manager)} (age {graph.value(s, EX.age)})")

print("\nProduct builders (dept IN Engineering/Design):")
for s in sorted(result_graph.subjects(EX.buildsProduct, Literal(True))):
    print(f"  {s.n3(result_graph.namespace_manager)} (dept {graph.value(s, EX.dept)})")

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
