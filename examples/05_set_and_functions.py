"""
Example 5: SET Assignments and Built-in Functions

SET(?v := expr) binds a fresh variable to a computed value. Assignments chain:
a later SET may use a variable an earlier SET introduced. This example strings
together CONCAT/UCASE/STRLEN and a numeric ABS + conditional IF.

(There is no BIND keyword in SRL; assignment is always SET(?v := expr).)
"""

from rdflib import Graph, Literal, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph: employees with names and a predicted-vs-actual score.
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Person1, EX.firstName, Literal("John")))
graph.add((EX.Person1, EX.lastName, Literal("Doe")))
graph.add((EX.Person1, EX.predicted, Literal(80)))
graph.add((EX.Person1, EX.actual, Literal(78)))

graph.add((EX.Person2, EX.firstName, Literal("Jane")))
graph.add((EX.Person2, EX.lastName, Literal("Smith")))
graph.add((EX.Person2, EX.predicted, Literal(60)))
graph.add((EX.Person2, EX.actual, Literal(72)))

print("Input data:")
for s, p, o in sorted(graph):
    print(f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o}")

# Rule 1 chains string built-ins; rule 2 chains arithmetic + a conditional IF.
rule_text = """
PREFIX ex: <http://example.org/>

# String pipeline: build a full name, then derive views of it.
RULE {
    ?p ex:fullName ?full .
    ?p ex:displayName ?disp .
    ?p ex:nameLength ?len .
} WHERE {
    ?p ex:firstName ?first .
    ?p ex:lastName ?last .
    SET(?full := CONCAT(?first, " ", ?last))
    SET(?disp := UCASE(?full))
    SET(?len := STRLEN(?full))
}

# Numeric pipeline: absolute prediction error, then a conditional rating.
RULE {
    ?p ex:absError ?err .
    ?p ex:rating ?rating .
} WHERE {
    ?p ex:predicted ?pred .
    ?p ex:actual ?act .
    SET(?err := ABS(?pred - ?act))
    SET(?rating := IF(?err <= 5, "good", "poor"))
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)
result_graph.bind("ex", EX)  # evaluate() drops custom prefixes; rebind for compact output

# Show every computed value grouped by person
print("\nComputed values per person:")
for person in sorted(set(result_graph.subjects(EX.fullName, None))):
    label = person.n3(result_graph.namespace_manager)
    full = result_graph.value(person, EX.fullName)
    disp = result_graph.value(person, EX.displayName)
    length = result_graph.value(person, EX.nameLength)
    err = result_graph.value(person, EX.absError)
    rating = result_graph.value(person, EX.rating)
    print(
        f'  {label}: fullName="{full}" display="{disp}" length={length} absError={err} rating="{rating}"'
    )

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
