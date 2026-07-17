"""
Example 11: Python API -- Provenance, Strata, and Results-Only Output

Beyond a plain evaluate(), the engine exposes:

    evaluate_with_provenance(graph)  -> (graph, [(triple, rule_index, stratum)])
    get_stratum_info()               -> rule indices grouped by evaluation layer
    evaluate(inplace=False, results_only=True) -> only the NEW triples

This example uses all three to explain *why* each triple exists.
"""

from rdflib import Graph, Namespace

from srl.engine import RuleEngine
from srl.parser import SRLParser

# Define namespace
EX = Namespace("http://example.org/")

# Create graph with a parent chain (drives multi-stratum inference).
graph = Graph()
graph.bind("ex", EX)

graph.add((EX.Alice, EX.parent, EX.Bob))
graph.add((EX.Bob, EX.parent, EX.Carol))

print("Input data:")
for s, p, o in sorted(graph):
    print(
        f"  {s.n3(graph.namespace_manager)} {p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)}"
    )

rule_text = """
PREFIX ex: <http://example.org/>

# Base ancestor from parent.
RULE ex:BaseRule {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}

# Transitive ancestor.
RULE ex:RecursiveRule {
    ?x ex:ancestor ?z .
} WHERE {
    ?x ex:ancestor ?y .
    ?y ex:ancestor ?z .
}
"""

parser = SRLParser()
rule_set = parser.parse(rule_text)
engine = RuleEngine(rule_set)

# --- Stratification layers: which rules run together, and in what order. ---
print("\nStratification layers (rule indices per stratum):")
for layer_num, rule_indices in enumerate(engine.get_stratum_info()):
    names = [str(rule_set.rules[i].iri or f"rule{i}") for i in rule_indices]
    print(f"  stratum {layer_num}: {names}")

# --- results_only: just the inferred/new triples (requires inplace=False). ---
only_new = engine.evaluate(graph, inplace=False, results_only=True)
print(f"\nresults_only=True yields {len(only_new)} newly inferred triple(s):")
for s, p, o in sorted(only_new):
    print(
        f"  {s.n3(only_new.namespace_manager)} {p.n3(only_new.namespace_manager)} {o.n3(only_new.namespace_manager)}"
    )

# --- Provenance: attribute every triple to the rule (and stratum) that made it. ---
full_graph, provenance = engine.evaluate_with_provenance(graph, inplace=False)
print("\nProvenance (triple -> rule that inferred it):")
for triple, rule_idx, stratum in provenance:
    s, p, o = triple
    if rule_idx == -1:
        source = "DATA block"
    else:
        rule = rule_set.rules[rule_idx]
        source = str(rule.iri) if rule.iri is not None else f"rule {rule_idx}"
    triple_str = f"{s.n3(full_graph.namespace_manager)} {p.n3(full_graph.namespace_manager)} {o.n3(full_graph.namespace_manager)}"
    print(f"  [{source}, stratum {stratum}] {triple_str}")

print(f"\nTotal: {len(graph)} input triples → {len(full_graph)} output triples")
