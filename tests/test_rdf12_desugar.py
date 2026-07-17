"""Exact-triple assertions for RDF 1.2 desugaring in the SRL transformer.

Parse-success is necessary but not sufficient — these tests assert the
*desugared triples* per RDF 1.2 Turtle §7 constructor semantics.
"""

import os
import tempfile

from srl.ast.nodes import IRI, TripleTerm, Variable
from srl.engine.imports import resolve_imports
from srl.parser.parser import ParseError, SRLParser

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


# ----------------------------------------------------------------------------
# Blank-node label uniqueness (desugared nodes must be globally fresh)
# ----------------------------------------------------------------------------


def _first_cells(graph):
    """Subjects carrying an rdf:first in an evaluated rdflib graph (list cells)."""
    return {s for (s, pred, o) in graph if str(pred) == RDF_FIRST}


def test_desugared_bnodes_unique_across_imports():
    # Two separately-parsed files, each with a 2-element collection, must yield
    # two DISTINCT list chains (4 distinct cells), not fuse into one.
    from rdflib import Graph

    from srl.engine.engine import RuleEngine

    d = tempfile.mkdtemp()
    a = os.path.join(d, "imp_a.srl")
    with open(a, "w", encoding="utf-8") as f:
        f.write("PREFIX ex: <http://example.org/>\nDATA { ex:s1 ex:p ( ex:a ex:b ) . }\n")
    main = (
        "PREFIX ex: <http://example.org/>\n"
        f"IMPORTS <file:///{a.replace(os.sep, '/')}>\n"
        "DATA { ex:s2 ex:q ( ex:c ex:d ) . }\n"
    )
    rs = resolve_imports(SRLParser().parse(main), base_location=os.path.join(d, "imp_main.srl"))
    out = RuleEngine(rs).evaluate(Graph(), inplace=False)
    # Four distinct collection cells (2 per list); nothing fused.
    assert len(_first_cells(out)) == 4, list(out)


def test_desugared_bnodes_dont_collide_with_user_labels():
    from rdflib import Graph, URIRef

    from srl.engine.engine import RuleEngine

    # A user blank node whose label mimics the internal scheme must stay a
    # distinct node from any desugared collection cell.
    rs = SRLParser().parse(
        "PREFIX : <http://example/>\nDATA { :s :p ( :a :b ) . _:_sx_c_1 :tag :USER . }"
    )
    out = RuleEngine(rs).evaluate(Graph(), inplace=False)
    tag = URIRef("http://example/tag")
    user = URIRef("http://example/USER")
    tagged = {s for (s, pred, o) in out if pred == tag and o == user}
    # The tagged user node must not be one of the collection's list cells.
    assert tagged.isdisjoint(_first_cells(out)), list(out)


# ----------------------------------------------------------------------------
# Path predicates must not leak into a reified triple term
# ----------------------------------------------------------------------------


def test_annotating_path_predicate_object_is_rejected():
    # A property path predicate cannot be reified (TripleTerm predicate must be
    # an IRI or Variable). The sibling << :s :p1/:p2 :o >> forms already reject
    # paths; the annotation form must too.
    for src in (
        "PREFIX : <http://example/>\nRULE {} WHERE { :s :p1/:p2 :o {| :q :z |} }",
        "PREFIX : <http://example/>\nRULE {} WHERE { :s :p1/:p2 :o ~:r }",
        "PREFIX : <http://example/>\nRULE {} WHERE { :s ^:p :o {| :q :z |} }",
    ):
        try:
            SRLParser().parse(src)
            raise AssertionError(f"expected rejection for: {src!r}")
        except ParseError:
            pass
