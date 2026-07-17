"""
Example 10: RDF 1.2 Concrete Syntax

SRL accepts RDF 1.2 surface syntax in rule heads/bodies and desugars it to
plain triples during parsing (there are no dedicated RDF 1.2 AST nodes):

    ( a b c )          RDF collection  -> rdf:first / rdf:rest / rdf:nil chain
    [ p1 v1 ; p2 v2 ]  blank-node list -> a fresh blank node with those triples
    << s p o >>        reified triple ) all desugar to an rdf:reifies
    s p o ~r           reifier        ) triple *term* <<( s p o )>>
    s p o {| k v |}    annotation     )

Collections and blank-node property lists desugar to ordinary triples and
evaluate normally. The reification family desugars to RDF 1.2 *triple terms*
(rdf:reifies <<( s p o )>>); those parse, but this rdflib build has no
triple-term type, so evaluating them raises UnrepresentableTripleTermError.
This example demonstrates both outcomes honestly.
"""

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from srl.engine import RuleEngine
from srl.engine.solutions import UnrepresentableTripleTermError
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# --- Part 1: collections + blank-node property lists (evaluate cleanly) ---

graph = Graph()
graph.bind("ex", EX)
graph.bind("rdf", RDF)
graph.add((EX.Cart1, EX.checkout, EX.Now))

print("Input data:")
for s, p, o in sorted(graph):
    print(
        f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}"
    )

# The head builds an ordered list and a nested blank node in one rule.
rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?c ex:items ( "milk" "eggs" "bread" ) .
    ?c ex:contact [ ex:email "cart@example.org" ; ex:priority 1 ] .
} WHERE {
    ?c ex:checkout ?when .
}
"""

parser = SRLParser()
rule_set = parser.parse(rule_text)

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)
result_graph.bind("rdf", RDF)

# The rdf:first/rdf:rest chain and the blank-node triples are all plain triples.
print("\nResult graph (collection + blank-node list desugared to plain triples):")
for s, p, o in sorted(result_graph, key=str):
    print(
        f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}"
    )

# --- Part 2: reification/annotation (parses, but not evaluable here) ---

reify_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?s ex:validReading ?r {| ex:derivedBy ex:ValidationRule |} .
} WHERE {
    ?s ex:rawReading ?r .
}
"""

print("\nReification/annotation rule parses fine:")
reify_rules = parser.parse(reify_text)
print(f"  parsed {len(reify_rules.rules)} rule; head desugared to an rdf:reifies triple term.")

data = Graph()
data.add((EX.Sensor1, EX.rawReading, EX.R1))
try:
    RuleEngine(reify_rules).evaluate(data, inplace=False)
except UnrepresentableTripleTermError as exc:
    print("  ...but evaluating it raises (as documented):")
    print(f"    {type(exc).__name__}: {str(exc).splitlines()[0]}")

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
