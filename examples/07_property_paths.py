"""
Example 7: Property Paths

Body triple patterns may use two path operators (the only two SRL supports):

    a/b   sequence  -- follow a, then b
    ^a    inverse   -- follow a backwards

Alternative (|), transitive (+/*), optional (?), and negated (!) paths are NOT
part of SRL and do not parse. Recursion (Example 3) covers transitivity.
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph: a parentOf chain Alice -> Bob -> Carol -> Dave.
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.parentOf, EX.Bob))
graph.add((EX.Bob, EX.parentOf, EX.Carol))
graph.add((EX.Carol, EX.parentOf, EX.Dave))

print("Input data (parentOf chain):")
for s, p, o in sorted(graph):
    print(
        f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}"
    )

# Sequence path finds grandparents; inverse path derives the childOf relation.
rule_text = """
PREFIX ex: <http://example.org/>

# Sequence: parentOf/parentOf spans two generations.
RULE {
    ?grandparent ex:grandparentOf ?grandchild .
} WHERE {
    ?grandparent ex:parentOf/ex:parentOf ?grandchild .
}

# Inverse: ^parentOf is "has parent", i.e. the childOf relation.
RULE {
    ?child ex:childOf ?parent .
} WHERE {
    ?child ^ex:parentOf ?parent .
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)
result_graph.bind("ex", EX)  # evaluate() drops custom prefixes; rebind for compact output

print("\nGrandparent relationships (via parentOf/parentOf):")
for s, p, o in sorted(result_graph.triples((None, EX.grandparentOf, None))):
    print(f"  {s.n3(result_graph.namespace_manager)} → {o.n3(result_graph.namespace_manager)}")

print("\nChildOf relationships (via ^parentOf):")
for s, p, o in sorted(result_graph.triples((None, EX.childOf, None))):
    print(f"  {s.n3(result_graph.namespace_manager)} → {o.n3(result_graph.namespace_manager)}")

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
