# tests/test_shapes_model.py
from rdflib import Graph
from srl.shapes.model import load_shape, NodeShape, UnsupportedShapeFeatureError
import pytest

SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:PersonShape a sh:NodeShape ;
  sh:targetClass ex:Person ;
  sh:property [ sh:path ex:age ; sh:minCount 1 ; sh:datatype xsd:integer ] .
"""


def _g():
    g = Graph(); g.parse(data=SHAPES, format="turtle"); return g


def test_load_shape_targets_and_property():
    from rdflib import URIRef
    s = load_shape(_g(), URIRef("http://example.org/PersonShape"))
    assert isinstance(s, NodeShape)
    assert any(t[0] == "targetClass" for t in s.targets)
    assert len(s.property_shapes) == 1
    kinds = {c.kind for c in s.property_shapes[0].constraints}
    assert "minCount" in kinds and "datatype" in kinds


def test_unsupported_feature_raises():
    g = Graph()
    g.parse(data=SHAPES + """
ex:BadShape a sh:NodeShape ; sh:targetNode ex:x ; sh:closed true .
""", format="turtle")
    from rdflib import URIRef
    with pytest.raises(UnsupportedShapeFeatureError):
        load_shape(g, URIRef("http://example.org/BadShape"))
