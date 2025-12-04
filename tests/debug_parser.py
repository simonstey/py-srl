"""Debug parser output."""

from src.srl.parser.parser import SRLParser
from lark import Lark

srl_text = """
PREFIX ex: <http://example.org/>

RULE { ?x ex:derived ?y . } WHERE { ?x ex:source ?y . }
"""

parser = SRLParser()

# Get the parse tree
import pathlib
grammar_path = pathlib.Path("src/srl/parser/grammar.lark")
with open(grammar_path) as f:
    grammar = f.read()

lark_parser = Lark(grammar, start='rule_set', parser='lalr')
tree = lark_parser.parse(srl_text)

print("Parse tree:")
print(tree.pretty())

print("\n" + "="*70)
print("Now transforming...")
result = parser.parse(srl_text)
print(f"Result type: {type(result)}")
print(f"Result: {result}")
print(f"Rules: {result.rules}")
print(f"Number of rules: {len(result.rules)}")
