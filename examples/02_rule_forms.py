"""
Example 2: Rule Forms

SRL offers two interchangeable surface syntaxes that parse to the same AST:

    RULE { head } WHERE { body }      -- optionally named: RULE ex:name { .. }
    IF   { body } THEN { head }

This example mixes all three (named RULE, anonymous RULE, IF/THEN) in one
rule set and shows they cooperate.
"""

from rdflib import Graph, Literal, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph: a couple of people with data to classify.
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.age, Literal(40)))
graph.add((EX.Alice, EX.name, Literal("Alice")))
graph.add((EX.Bob, EX.age, Literal(9)))
graph.add((EX.Bob, EX.name, Literal("Bob")))

print("Input data:")
for s, p, o in sorted(graph):
    print(f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o}")

# One rule set, three forms:
#   1. named RULE   -> tags anyone with age + name as a Person
#   2. IF/THEN      -> tags Persons at/over 18 as an Adult
#   3. anonymous RULE (built on the output of the first two)
rule_text = """
PREFIX ex: <http://example.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

# Named RULE/WHERE form: the IRI after RULE names the rule.
RULE ex:PersonRule {
    ?p rdf:type ex:Person .
} WHERE {
    ?p ex:age ?age .
    ?p ex:name ?name .
}

# IF/THEN form: body first, head second -- same meaning as RULE/WHERE.
IF {
    ?p rdf:type ex:Person .
    ?p ex:age ?age .
    FILTER (?age >= 18)
} THEN {
    ?p rdf:type ex:Adult .
}

# Anonymous RULE/WHERE form, consuming the Adult type inferred above.
RULE {
    ?p ex:canVote true .
} WHERE {
    ?p rdf:type ex:Adult .
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

# The parsed rule set exposes each rule; named rules carry their IRI.
print("\nParsed rules:")
for i, rule in enumerate(rule_set.rules):
    name = str(rule.iri) if rule.iri is not None else "(anonymous)"
    print(f"  rule {i}: {name}")

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# Show the classifications produced across all three forms.
print("\nInferred triples:")
for s, p, o in sorted(result_graph):
    if (s, p, o) not in graph:
        print(
            f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}"
        )

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
