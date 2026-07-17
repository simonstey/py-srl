"""
Example 6: Negation as Failure

NOT { ... } succeeds when the enclosed pattern has no match, giving closed-world
reasoning. Safety rule: every variable used inside NOT must already be bound by
a positive pattern earlier in the body, and the negated predicate must differ
from the rule's head predicate (negating your own output is a closed
self-dependency, which the stratifier rejects).
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph: some people have children recorded, some do not.
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.type, EX.Person))
graph.add((EX.Alice, EX.hasChild, EX.Bob))
graph.add((EX.Carol, EX.type, EX.Person))  # no children recorded
graph.add((EX.Dave, EX.type, EX.Person))  # no children recorded

print("Input data:")
for s, p, o in sorted(graph):
    print(
        f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}"
    )

# ?person is bound by the positive Person pattern before NOT references it.
rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:childless true .
} WHERE {
    ?person ex:type ex:Person .
    NOT {
        ?person ex:hasChild ?child .
    }
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)
result_graph.bind("ex", EX)  # evaluate() drops custom prefixes; rebind for compact output

# Only the people with no hasChild triple should be flagged.
print("\nPeople with no recorded children:")
for s in sorted(result_graph.subjects(EX.childless, None)):
    print(f"  {s.n3(result_graph.namespace_manager)}")

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
