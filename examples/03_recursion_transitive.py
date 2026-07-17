"""
Example 3: Recursion and Transitive Closure

A recursive rule feeds its own output back in. The engine stratifies the rule
set and iterates to a fixpoint, so parent chains of any depth collapse into the
full ancestor relation.
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph with a chain of parent relationships
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.parent, EX.Bob))
graph.add((EX.Bob, EX.parent, EX.Charlie))
graph.add((EX.Charlie, EX.parent, EX.Diana))

print("Input data (parent relationships):")
for s, p, o in sorted(graph):
    print(
        f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}"
    )

# Base case seeds ancestor from parent; the recursive case chains ancestors.
rule_text = """
PREFIX ex: <http://example.org/>

# Base case: a parent is an ancestor.
RULE {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}

# Recursive case: an ancestor of an ancestor is an ancestor.
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

# Show the complete ancestor relation (base + all transitively inferred pairs)
print("\nInferred ancestor relationships:")
for s, p, o in sorted(result_graph):
    if p == EX.ancestor:
        print(
            f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}"
        )

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
