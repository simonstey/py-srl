"""Debug transformer."""

import pathlib

from lark import Lark

from srl.parser.transformer import SRLTransformer

srl_text = """
PREFIX : <http://example.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

# Find people who have at least one child
RULE { ?person :isParent true } WHERE {
    ?person rdf:type :Person .
    FILTER(EXISTS { ?person :parentOf ?child })
}

# Find companies with employees
RULE { ?company :hasEmployees true } WHERE {
    ?company rdf:type :Company .
    FILTER(EXISTS { ?emp :worksFor ?company })
}
"""

# Get the parse tree
grammar_path = pathlib.Path("src/srl/parser/grammar.lark")
with open(grammar_path) as f:
    grammar = f.read()

lark_parser = Lark(grammar, start='rule_set', parser='lalr')
tree = lark_parser.parse(srl_text)

print("Parse tree:")
print(tree.pretty())

print("\n" + "="*70)
print("Transforming manually...")

transformer = SRLTransformer()

# Transform step by step
result = transformer.transform(tree)

print(f"Result: {result}")
print(f"Type: {type(result)}")
if hasattr(result, 'rules'):
    print(f"Rules: {result.rules}")
    for i, rule in enumerate(result.rules):
        print(f"  Rule {i}: {rule}")
