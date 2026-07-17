"""
Example 1: Simple Inference

The smallest useful rule: derive an ancestor relationship directly from a
parent relationship. Start here to see the parse -> evaluate -> read cycle.
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create an RDF graph with some data
graph = Graph()
graph.bind("ex", EX)

# Add parent relationships
graph.add((EX.Alice, EX.parent, EX.Bob))
graph.add((EX.Bob, EX.parent, EX.Charlie))

print("Input data:")
for s, p, o in sorted(graph):
    print(
        f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}"
    )

# Define a SHACL rule (RULE { head } WHERE { body } form)
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

# Create engine and evaluate rules (inplace=False leaves the input graph intact)
engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)
result_graph.bind("ex", EX)  # evaluate() drops custom prefixes; rebind for compact output

# Show inferred triples (everything in the result that was not in the input)
print("\nInferred triples:")
for s, p, o in sorted(result_graph):
    if (s, p, o) not in graph:
        print(
            f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}"
        )

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
