"""
Example 8: Property Declarations (TRANSITIVE / SYMMETRIC / INVERSE)

SRL can declare well-known property characteristics:

    TRANSITIVE(:p)          -- p is transitive
    (:p) SYMMETRIC          -- p is symmetric (note the postfix keyword)
    INVERSE(:a, :b)         -- a and b are inverses

IMPORTANT: in this engine these declarations are parsed *metadata* -- they are
recorded on rule_set.declarations (and merged across IMPORTS) but do NOT by
themselves drive inference. To actually derive the closure you pair each
declaration with an explicit rule, exactly as the test suite does. This example
shows both halves: the inspectable declarations and the rules that realise them.
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph: a small social/organisational network.
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.ancestorOf, EX.Bob))
graph.add((EX.Bob, EX.ancestorOf, EX.Carol))
graph.add((EX.Alice, EX.friendOf, EX.Dave))
graph.add((EX.Acme, EX.employs, EX.Alice))

print("Input data:")
for s, p, o in sorted(graph):
    print(
        f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}"
    )

# Declarations document intent; the paired rules perform the derivation.
rule_text = """
PREFIX ex: <http://example.org/>

# --- Declarations (metadata: inspectable, but inert on their own) ---
TRANSITIVE(ex:ancestorOf)
(ex:friendOf) SYMMETRIC
INVERSE(ex:employs, ex:worksFor)

# --- Rules that actually realise those characteristics ---

# Transitive closure of ancestorOf.
RULE {
    ?x ex:ancestorOf ?z .
} WHERE {
    ?x ex:ancestorOf ?y .
    ?y ex:ancestorOf ?z .
}

# Symmetry of friendOf.
RULE {
    ?y ex:friendOf ?x .
} WHERE {
    ?x ex:friendOf ?y .
}

# Inverse: worksFor is the inverse of employs.
RULE {
    ?e ex:worksFor ?org .
} WHERE {
    ?org ex:employs ?e .
}
"""

# Parse and evaluate
parser = SRLParser()
rule_set = parser.parse(rule_text)

# Declarations are structured AST nodes you can inspect programmatically.
print("\nParsed declarations (metadata on rule_set.declarations):")
for decl in rule_set.declarations:
    preds = [
        getattr(decl, f) for f in ("predicate", "predicate1", "predicate2") if hasattr(decl, f)
    ]
    compact = ", ".join(p.value.replace(str(EX), "ex:") for p in preds)
    print(f"  {type(decl).__name__}: {compact}")

engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)
result_graph.bind("ex", EX)  # evaluate() drops custom prefixes; rebind for compact output

# The newly derived triples come from the rules, guided by the declarations.
print("\nInferred triples:")
for s, p, o in sorted(result_graph):
    if (s, p, o) not in graph:
        print(
            f"  {s.n3(result_graph.namespace_manager)} {p.n3(result_graph.namespace_manager)} {o.n3(result_graph.namespace_manager)}"
        )

print(f"\nTotal: {len(graph)} input triples → {len(result_graph)} output triples")
