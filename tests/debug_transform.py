"""Debug transformer."""

from src.srl.parser.parser import SRLParser
from src.srl.parser.transformer import SRLTransformer
from lark import Lark
import pathlib

srl_text = """
PREFIX ex: <http://example.org/>

RULE { ?x ex:derived ?y . } WHERE { ?x ex:source ?y . }
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
