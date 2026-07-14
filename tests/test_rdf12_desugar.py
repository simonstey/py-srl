"""Exact-triple assertions for RDF 1.2 desugaring in the SRL transformer.

Parse-success is necessary but not sufficient — these tests assert the
*desugared triples* per RDF 1.2 Turtle §7 constructor semantics.
"""

from srl.ast.nodes import IRI, TripleTerm, Variable
from srl.parser.parser import SRLParser

RDF_FIRST = "http://www.w3.org/1999/02/22-rdf-syntax-ns#first"
RDF_REST = "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"
RDF_NIL = "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"
RDF_REIFIES = "http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies"


def _head_triples(srl):
    return SRLParser().parse(srl).rules[0].head.templates


def _body_triples(srl):
    return list(SRLParser().parse(srl).rules[0].body.elements)


def _data_triples(srl):
    return SRLParser().parse(srl).data_blocks[0].triples


def _preds(triples, iri):
    return [t for t in triples if isinstance(t.predicate, IRI) and t.predicate.value == iri]


# ----------------------------------------------------------------------------
# Collections ( ... )
# ----------------------------------------------------------------------------


def test_collection_desugars_to_first_rest_nil():
    ts = _head_triples("PREFIX : <http://example/>\nRULE { :a :p (1 2 3) } WHERE { ?a ?b ?c }")
    firsts = _preds(ts, RDF_FIRST)
    assert {f.object.value for f in firsts} == {"1", "2", "3"}
    rests = _preds(ts, RDF_REST)
    assert any(isinstance(r.object, IRI) and r.object.value == RDF_NIL for r in rests)
    assert any(t.predicate == IRI("http://example/p") for t in ts)


def test_empty_collection_is_nil():
    ts = _head_triples("PREFIX : <http://example/>\nRULE { :a :p () } WHERE { ?a ?b ?c }")
    assert any(isinstance(t.object, IRI) and t.object.value == RDF_NIL for t in ts)


# ----------------------------------------------------------------------------
# Blank-node property lists [ ... ]
# ----------------------------------------------------------------------------


def test_bnode_property_list_desugars():
    ts = _body_triples("PREFIX : <http://example/>\nRULE {} WHERE { [ ?b ?c ; :p :z ] }")
    subjects = {t.subject for t in ts}
    assert len(subjects) == 1  # one fresh blank-node subject for both pairs
    preds = {t.predicate for t in ts}
    assert Variable("b") in preds and IRI("http://example/p") in preds
