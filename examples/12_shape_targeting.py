"""
Example 12: Rule-to-Shape Targeting (opt-in extension)

This is NOT part of the SRL spec -- it is an opt-in extension that scopes a rule
to the focus nodes of a SHACL shape:

    RULE ex:r FOR ?this IN ex:Shape { head } WHERE { body }

Firing a targeted rule is a two-stage filter over the data graph:
  1. the shape's targets (sh:targetClass, sh:targetNode, ...) select candidates;
  2. only candidates that CONFORM to the shape survive.
The wrapped rule then runs once per surviving node, with the focus variable
(?this here) pre-bound to that node.

Enabling it requires the opt-in switches:
  - SRLParser(extensions=True)                     to parse FOR ?v IN <shape>
  - RuleEngine(..., extensions=True, shapes_graph=g)  to evaluate against shapes

On the CLI this is the `srl shacl` subcommand (see README.md).
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespaces
EX = Namespace("http://example.org/")
SH = Namespace("http://www.w3.org/ns/shacl#")

# Data graph: two Persons, only one of whom is an adult.
data_graph = Graph()
data_graph.bind("ex", EX)
data_graph.parse(
    data="""
    @prefix ex: <http://example.org/> .
    ex:Alice a ex:Person ; ex:age 30 .
    ex:Bob   a ex:Person ; ex:age 10 .
    """,
    format="turtle",
)

# Shapes graph: AdultShape targets every Person but only conforms at age >= 18.
shapes_graph = Graph()
shapes_graph.parse(
    data="""
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix ex: <http://example.org/> .
    ex:AdultShape a sh:NodeShape ;
        sh:targetClass ex:Person ;
        sh:property [ sh:path ex:age ; sh:minCount 1 ; sh:minInclusive 18 ] .
    """,
    format="turtle",
)

print("Data:")
for s, p, o in sorted(data_graph):
    print(f"  {s.n3(data_graph.namespace_manager)} {p.n3(data_graph.namespace_manager)} {o}")

# The targeted rule marks conforming focus nodes as adults.
rule_text = """
PREFIX ex: <http://example.org/>

RULE ex:AdultRule FOR ?this IN ex:AdultShape {
    ?this ex:status ex:adult .
} WHERE {
    ?this ex:age ?a .
}
"""

# extensions=True is required both to PARSE and to EVALUATE the FOR ... IN clause.
parser = SRLParser(extensions=True)
rule_set = parser.parse(rule_text)

# Targeted rules live on a separate list from plain rules.
print(
    f"\nParsed {len(rule_set.rules)} plain rule(s), "
    f"{len(rule_set.targeted_rules)} targeted rule(s):"
)
for tr in rule_set.targeted_rules:
    print(f"  {tr.rule.iri}: FOR ?{tr.focus_var.name} IN {tr.shape}")

engine = RuleEngine(rule_set, extensions=True, shapes_graph=shapes_graph)
result_graph = engine.evaluate(data_graph, inplace=False)

# Alice (30) conforms to AdultShape; Bob (10) does not, so only Alice is tagged.
print("\nInferred triples (only shape-conforming focus nodes fire):")
for s, p, o in sorted(result_graph):
    if (s, p, o) not in data_graph:
        print(
            f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}"
        )

print(f"\nTotal: {len(data_graph)} input triples → {len(result_graph)} output triples")
