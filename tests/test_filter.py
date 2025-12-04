"""Test FILTER evaluation."""

from rdflib import Graph, Namespace, Literal
from src.srl.parser import SRLParser
from src.srl.engine import RuleEngine

EX = Namespace("http://example.org/")

srl_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:isAdult true .
} WHERE {
    ?person ex:age ?age .
    FILTER (?age >= 18)
}
"""

parser = SRLParser()
rule_set = parser.parse(srl_text)

data = Graph()
data.bind("ex", EX)
data.add((EX.Alice, EX.age, Literal(25)))
data.add((EX.Bob, EX.age, Literal(16)))
data.add((EX.Charlie, EX.age, Literal(30)))

print("Data:")
for s, p, o in data:
    print(f"  {s.n3(data.namespace_manager)} {p.n3(data.namespace_manager)} {o}")

engine = RuleEngine(rule_set)
result = engine.evaluate(data, inplace=False)

print("\nResult:")
for s, p, o in result:
    if EX.isAdult in (p,):
        print(f"  {s.n3(result.namespace_manager)} {p.n3(result.namespace_manager)} {o}")

print("\nExpected: Alice and Charlie should be adults, Bob should NOT be.")
