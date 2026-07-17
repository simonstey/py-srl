# tests/test_shapes_targets.py
from rdflib import Graph, URIRef
from srl.shapes.model import load_shape
from srl.shapes.targets import focus_nodes

SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
ex:PersonShape a sh:NodeShape ; sh:targetClass ex:Person .
ex:SubjShape a sh:NodeShape ; sh:targetSubjectsOf ex:knows .
ex:NodeShapeT a sh:NodeShape ; sh:targetNode ex:Alice .
ex:ObjShape a sh:NodeShape ; sh:targetObjectsOf ex:knows .
ex:WhereShape a sh:NodeShape ;
  sh:targetWhere [ sh:property [ sh:path ex:age ; sh:minCount 1 ] ] .
ex:ManualShape a sh:NodeShape ;
  sh:property [ sh:path ex:name ; sh:minCount 0 ] .
"""
DATA = """
@prefix ex: <http://example.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
ex:Alice a ex:Person ; ex:age 30 . ex:Bob a ex:Person .
ex:Carol ex:knows ex:Dan .
ex:Erin sh:shape ex:ManualShape .
"""


def _sg():
    g = Graph()
    g.parse(data=SHAPES, format="turtle")
    return g


def _dg():
    g = Graph()
    g.parse(data=DATA, format="turtle")
    return g


def test_target_class_and_subjects_of():
    sg = _sg()
    dg = _dg()
    ps = load_shape(sg, URIRef("http://example.org/PersonShape"))
    assert focus_nodes(ps, dg, sg) == {
        URIRef("http://example.org/Alice"),
        URIRef("http://example.org/Bob"),
    }
    ss = load_shape(sg, URIRef("http://example.org/SubjShape"))
    assert focus_nodes(ss, dg, sg) == {URIRef("http://example.org/Carol")}


def test_target_node():
    sg = _sg()
    dg = _dg()
    ns = load_shape(sg, URIRef("http://example.org/NodeShapeT"))
    assert focus_nodes(ns, dg, sg) == {URIRef("http://example.org/Alice")}


def test_target_objects_of():
    sg = _sg()
    dg = _dg()
    os_ = load_shape(sg, URIRef("http://example.org/ObjShape"))
    assert focus_nodes(os_, dg, sg) == {URIRef("http://example.org/Dan")}


def test_target_where():
    sg = _sg()
    dg = _dg()
    ws = load_shape(sg, URIRef("http://example.org/WhereShape"))
    # Only Alice has an ex:age (minCount 1 in the inline sh:targetWhere shape).
    assert focus_nodes(ws, dg, sg) == {URIRef("http://example.org/Alice")}


def test_target_shape():
    sg = _sg()
    dg = _dg()
    ms = load_shape(sg, URIRef("http://example.org/ManualShape"))
    # ex:Erin sh:shape ex:ManualShape in the data graph.
    assert focus_nodes(ms, dg, sg) == {URIRef("http://example.org/Erin")}
