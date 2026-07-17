"""
Example 9: DATA Blocks

A DATA { ... } block holds ground triples (no variables, no paths) that are
seeded into the graph before evaluation. This lets a rule set be
self-contained: the facts and the rules that reason over them travel together,
so you can evaluate against an empty input graph.
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Start from an EMPTY graph -- all facts come from the DATA block below.
graph = Graph()
graph.bind("ex", EX)

print(f"Input graph starts with {len(graph)} triples (empty).")

# DATA supplies the ground facts; the RULE reasons over them.
rule_text = """
PREFIX ex: <http://example.org/>

DATA {
    ex:Alice ex:parent ex:Bob .
    ex:Bob ex:parent ex:Carol .
}

RULE {
    ?x ex:grandparent ?z .
} WHERE {
    ?x ex:parent ?y .
    ?y ex:parent ?z .
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

# The parsed rule set carries the DATA facts separately from the rules.
seeded = sum(len(block.triples) for block in rule_set.data_blocks)
print(f"Rule set carries {seeded} DATA triple(s) across {len(rule_set.data_blocks)} block(s).")

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# The result contains the seeded DATA facts plus whatever the rule inferred.
print("\nResult graph (seeded DATA + inferred triples):")
for s, p, o in sorted(result_graph):
    print(
        f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}"
    )

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
