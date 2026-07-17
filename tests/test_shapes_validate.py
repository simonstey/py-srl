# tests/test_shapes_validate.py
from rdflib import Graph, URIRef

from srl.shapes.model import load_shape
from srl.shapes.validate import conforms

SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:AdultShape a sh:NodeShape ;
  sh:targetClass ex:Person ;
  sh:property [ sh:path ex:age ; sh:minCount 1 ; sh:minInclusive 18 ] .
"""
DATA = """
@prefix ex: <http://example.org/> .
ex:Alice a ex:Person ; ex:age 30 .
ex:Bob a ex:Person ; ex:age 10 .
ex:Carol a ex:Person .
"""


def _shapes():
    g = Graph()
    g.parse(data=SHAPES, format="turtle")
    return g


def _data():
    g = Graph()
    g.parse(data=DATA, format="turtle")
    return g


def test_conforms_true_and_false():
    sg = _shapes()
    dg = _data()
    shape = load_shape(sg, URIRef("http://example.org/AdultShape"))
    assert conforms(URIRef("http://example.org/Alice"), shape, dg, sg) is True
    assert conforms(URIRef("http://example.org/Bob"), shape, dg, sg) is False  # age < 18
    assert conforms(URIRef("http://example.org/Carol"), shape, dg, sg) is False  # no age (minCount)


# --- 1.2 additions coverage -------------------------------------------------

SHAPES_12 = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .

ex:DogShape a sh:NodeShape ;
  sh:property [ sh:path ex:species ; sh:hasValue "dog" ] .

ex:PetOwnerShape a sh:NodeShape ;
  sh:targetClass ex:Person ;
  sh:property [ sh:path ex:hasPet ; sh:someValue ex:DogShape ] .

ex:PersonAddrShape a sh:NodeShape ;
  sh:targetClass ex:Person ;
  sh:property [ sh:path ex:address ; sh:node ex:AddressShape ] .

ex:AddressShape a sh:NodeShape ;
  sh:property [ sh:path ex:zip ; sh:minCount 1 ] .

ex:PetTypeShape a sh:NodeShape ;
  sh:property [ sh:path ex:petType ; sh:rootClass ex:Animal ] .

ex:KennelShape a sh:NodeShape ;
  sh:property [ sh:path ex:members ; sh:memberShape ex:DogShape ; sh:uniqueMembers true ] .
"""

DATA_12 = """
@prefix ex: <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Dog rdfs:subClassOf ex:Mammal .
ex:Mammal rdfs:subClassOf ex:Animal .

ex:Rex ex:species "dog" .
ex:Fido ex:species "dog" .
ex:Whiskers ex:species "cat" .

ex:Alice a ex:Person ; ex:hasPet ex:Rex, ex:Whiskers ;
  ex:address ex:Addr1 ; ex:petType ex:Dog .
ex:Bob a ex:Person ; ex:hasPet ex:Whiskers ;
  ex:address ex:Addr2 ; ex:petType ex:Rock .

ex:Addr1 ex:zip "12345" .
ex:Addr2 ex:foo "bar" .

ex:GoodKennel ex:members ( ex:Rex ex:Fido ) .
ex:DupKennel ex:members ( ex:Rex ex:Rex ) .
ex:CatKennel ex:members ( ex:Rex ex:Whiskers ) .
"""


def _sg12():
    g = Graph()
    g.parse(data=SHAPES_12, format="turtle")
    return g


def _dg12():
    g = Graph()
    g.parse(data=DATA_12, format="turtle")
    return g


def _u(local):
    return URIRef("http://example.org/" + local)


def test_some_value():
    sg = _sg12()
    dg = _dg12()
    shape = load_shape(sg, _u("PetOwnerShape"))
    assert conforms(_u("Alice"), shape, dg, sg) is True  # Rex is a dog
    assert conforms(_u("Bob"), shape, dg, sg) is False  # only a cat


def test_node_nesting():
    sg = _sg12()
    dg = _dg12()
    shape = load_shape(sg, _u("PersonAddrShape"))
    assert conforms(_u("Alice"), shape, dg, sg) is True  # Addr1 has a zip
    assert conforms(_u("Bob"), shape, dg, sg) is False  # Addr2 has no zip


def test_root_class_transitive_subclass():
    sg = _sg12()
    dg = _dg12()
    shape = load_shape(sg, _u("PetTypeShape"))
    assert conforms(_u("Alice"), shape, dg, sg) is True  # Dog -> Mammal -> Animal
    assert conforms(_u("Bob"), shape, dg, sg) is False  # Rock is not an Animal


def test_member_shape_and_unique_members():
    sg = _sg12()
    dg = _dg12()
    shape = load_shape(sg, _u("KennelShape"))
    assert conforms(_u("GoodKennel"), shape, dg, sg) is True  # dogs, unique
    assert conforms(_u("DupKennel"), shape, dg, sg) is False  # not unique
    assert conforms(_u("CatKennel"), shape, dg, sg) is False  # Whiskers is a cat
