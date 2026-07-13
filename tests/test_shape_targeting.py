# tests/test_shape_targeting.py
from srl.ast import TargetedRule, Rule, RuleHead, RuleBody, Variable, IRI, RuleSet, Prologue


def test_targeted_rule_wraps_rule():
    r = Rule(head=RuleHead(templates=[]), body=RuleBody(elements=[]))
    tr = TargetedRule(rule=r, focus_var=Variable("this"), shape=IRI("http://example/S"), direction="rule-to-shape")
    assert tr.rule is r
    assert tr.focus_var == Variable("this")
    assert tr.shape == IRI("http://example/S")


def test_ruleset_has_targeted_rules_field():
    rs = RuleSet(prologue=Prologue(), rules=[], data_blocks=[])
    assert rs.targeted_rules == []


from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF
from srl.parser import SRLParser
from srl.engine import RuleEngine, ExtensionError
import pytest

EX = Namespace("http://example.org/")
SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
ex:AdultShape a sh:NodeShape ; sh:targetClass ex:Person ;
  sh:property [ sh:path ex:age ; sh:minCount 1 ; sh:minInclusive 18 ] .
"""
RULE = ("PREFIX ex: <http://example.org/>\n"
        "RULE ex:r FOR ?this IN ex:AdultShape { ?this ex:status ex:adult } "
        "WHERE { ?this ex:age ?a }")


def _data():
    g = Graph()
    g.add((EX.Alice, RDF.type, EX.Person)); g.add((EX.Alice, EX.age, Literal(30)))
    g.add((EX.Bob, RDF.type, EX.Person)); g.add((EX.Bob, EX.age, Literal(10)))
    return g


def _shapes():
    g = Graph(); g.parse(data=SHAPES, format="turtle"); return g


def test_targeted_rule_fires_only_for_conforming_focus_nodes():
    rs = SRLParser(extensions=True).parse(RULE)
    out = RuleEngine(rs, extensions=True, shapes_graph=_shapes()).evaluate(_data(), inplace=False)
    assert (EX.Alice, EX.status, EX.adult) in out   # age 30 conforms
    assert (EX.Bob, EX.status, EX.adult) not in out  # age 10 fails minInclusive


def test_targeted_rule_rejected_without_extensions():
    rs = SRLParser(extensions=True).parse(RULE)
    with pytest.raises(ExtensionError):
        RuleEngine(rs).evaluate(_data(), inplace=False)  # extensions defaults to False


def test_targeted_rule_sees_inferred_target_membership():
    # A plain rule infers ex:age; the targeted rule (gated on ex:age >= 18)
    # must fire AFTER that inference, i.e. be in a higher stratum.
    src = ("PREFIX ex: <http://example.org/>\n"
           "RULE { ?x ex:age 40 } WHERE { ?x ex:bornYear ?y }\n"
           "RULE ex:r FOR ?this IN ex:AdultShape { ?this ex:status ex:adult } WHERE { ?this ex:age ?a }")
    rs = SRLParser(extensions=True).parse(src)
    g = Graph()
    g.add((EX.Dana, RDF.type, EX.Person)); g.add((EX.Dana, EX.bornYear, Literal(1980)))
    out = RuleEngine(rs, extensions=True, shapes_graph=_shapes()).evaluate(g, inplace=False)
    assert (EX.Dana, EX.age, Literal(40)) in out
    assert (EX.Dana, EX.status, EX.adult) in out  # gate saw the inferred age


def test_targeted_rule_head_feeds_another_targeted_gate():
    # Two targeted rules: the first infers ex:age (feeding AdultShape's gate);
    # the second is gated on AdultShape. Proper stratification must place the
    # second rule in a higher stratum than the first so it sees the inferred age.
    shapes = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
ex:PersonShape a sh:NodeShape ; sh:targetClass ex:Person .
ex:AdultShape a sh:NodeShape ; sh:targetClass ex:Person ;
  sh:property [ sh:path ex:age ; sh:minCount 1 ; sh:minInclusive 18 ] .
"""
    src = ("PREFIX ex: <http://example.org/>\n"
           "RULE ex:r2 FOR ?this IN ex:AdultShape { ?this ex:status ex:adult } WHERE { ?this ex:age ?a }\n"
           "RULE ex:r1 FOR ?this IN ex:PersonShape { ?this ex:age 40 } WHERE { ?this ex:bornYear ?y }")
    rs = SRLParser(extensions=True).parse(src)
    sg = Graph(); sg.parse(data=shapes, format="turtle")
    g = Graph()
    g.add((EX.Erin, RDF.type, EX.Person)); g.add((EX.Erin, EX.bornYear, Literal(1980)))
    out = RuleEngine(rs, extensions=True, shapes_graph=sg).evaluate(g, inplace=False)
    assert (EX.Erin, EX.age, Literal(40)) in out
    assert (EX.Erin, EX.status, EX.adult) in out  # r2's gate saw r1's inferred age
