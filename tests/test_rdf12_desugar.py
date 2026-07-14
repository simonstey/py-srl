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


# ----------------------------------------------------------------------------
# Reified triples << ... >>  (base NOT asserted)
# ----------------------------------------------------------------------------


def test_reified_triple_term_base_not_asserted():
    ts = _body_triples("PREFIX : <http://example/>\nRULE {} WHERE { ?s :p << :a :b :c >> }")
    reifies = _preds(ts, RDF_REIFIES)
    assert len(reifies) == 1 and isinstance(reifies[0].object, TripleTerm)
    assert not any(t.subject == IRI("http://example/a") for t in ts)  # base NOT asserted


def test_reified_triple_explicit_reifier():
    ts = _body_triples("PREFIX : <http://example/>\nRULE {} WHERE { ?s :p << :a :b :c ~:r >> }")
    reifies = _preds(ts, RDF_REIFIES)
    assert reifies and reifies[0].subject == IRI("http://example/r")


def test_reified_triple_block_subject():
    ts = _body_triples("PREFIX : <http://example/>\nRULE {} WHERE { << :s :p :o >> :q :z }")
    reifies = _preds(ts, RDF_REIFIES)
    q = [t for t in ts if t.predicate == IRI("http://example/q")]
    assert reifies and q and reifies[0].subject == q[0].subject  # same reifier
    assert not any(t.subject == IRI("http://example/s") for t in ts)  # base NOT asserted


# ----------------------------------------------------------------------------
# Reifier annotation ~ and annotation blocks {| ... |}  (base IS asserted)
# ----------------------------------------------------------------------------


def test_reifier_annotation_asserts_base():
    ts = _data_triples("PREFIX : <http://example/>\nDATA { :a :b :c ~:r . }")
    assert any(
        t.subject == IRI("http://example/a") and t.predicate == IRI("http://example/b") for t in ts
    )  # base asserted
    reifies = _preds(ts, RDF_REIFIES)
    assert reifies and reifies[0].subject == IRI("http://example/r")


def test_annotation_block_standalone_fresh_reifier():
    ts = _body_triples("PREFIX : <http://example/>\nRULE {} WHERE { :s :p :o {| :q :r |} }")
    assert any(t.subject == IRI("http://example/s") for t in ts)  # base asserted
    reifies = _preds(ts, RDF_REIFIES)
    q = [t for t in ts if t.predicate == IRI("http://example/q")]
    assert len(reifies) == 1 and q and q[0].subject == reifies[0].subject  # block list on reifier


def test_reifier_then_block_reuses_reifier():
    ts = _data_triples(
        "PREFIX : <http://example/>\n" "DATA { :s :p :o ~:r1 {| :q1 :z1 |} ~_:B {| :q1 :z1 |} . }"
    )
    subs = {t.subject for t in ts if t.predicate == IRI("http://example/q1")}
    assert IRI("http://example/r1") in subs  # ~:r1 reused by its following block
