"""Debug filter evaluation in detail"""
from rdflib import Graph, Namespace, Literal as RDFLiteral

from src.srl.engine import RuleEngine

EX = Namespace("http://example.org/")

# Create test data
g = Graph()
g.bind("ex", EX)
g.add((EX.Alice, EX.age, RDFLiteral(25)))
g.add((EX.Bob, EX.age, RDFLiteral(16)))
g.add((EX.Charlie, EX.age, RDFLiteral(30)))

# Rule with filter
rule_text = """
@prefix ex: <http://example.org/> .

RULE {
    FORALL ?person ?age {
        ?person ex:age ?age .
        FILTER (?age >= 18)
    } => {
        ?person ex:isAdult true .
    }
}
"""

# Patch eval_filter to add debugging
from src.srl.engine import expressions
original_eval_filter = expressions.eval_filter

def debug_eval_filter(condition, mu, active_graph=None):
    """Debug wrapper for eval_filter"""
    print(f"\n=== FILTER EVALUATION ===")
    print(f"Condition: {condition}")
    print(f"Solution mapping: {mu}")
    
    # Evaluate the expression first
    result_term = expressions.eval_expr(condition, mu, active_graph)
    print(f"Expression result term: {result_term}")
    print(f"Result type: {type(result_term)}")
    if isinstance(result_term, RDFLiteral):
        print(f"Result datatype: {result_term.datatype}")
        print(f"Result value: {result_term.value}")
        print(f"Result value type: {type(result_term.value)}")
    
    # Compute EBV
    ebv = expressions.effective_boolean_value(result_term)
    print(f"Effective boolean value: {ebv}")
    print(f"=========================\n")
    
    return ebv

expressions.eval_filter = debug_eval_filter

# Execute
engine = RuleEngine(g)
engine.add_rules(rule_text)
result = engine.apply_rules()

print(f"\nFinal result ({len(result)} triples):")
for s, p, o in result:
    print(f"  {s} {p} {o}")
