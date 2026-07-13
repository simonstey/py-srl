"""
Regression tests for the 2026 SHACL 1.2 Rules spec-compliance remediation.

Each test pins a specific divergence identified in SPEC-COMPLIANCE-AUDIT.md so
that a future change cannot silently reintroduce it.
"""

import warnings

import pytest
from rdflib import Graph, Namespace, Literal as RDFLiteral, URIRef
from rdflib.namespace import RDF, XSD

from srl.parser import SRLParser, ParseError
from srl.engine import RuleEngine, stratify, StratificationError
from srl.engine.solutions import graphMatch, SolutionMapping
from srl.engine.expressions import (
    eval_expr,
    effective_boolean_value,
    builtin_year,
    builtin_month,
    builtin_hours,
    builtin_round,
    builtin_ucase,
    builtin_concat,
    builtin_langmatches,
    rdf_equal,
)
from srl.ast import (
    Assignment,
    TriplePattern,
    TripleTerm,
    Variable,
    IRI,
    PathSequence,
    WellFormednessError,
    validate_rule_well_formedness,
)

EX = Namespace("http://example.org/")
XSD_INT = URIRef(str(XSD) + "int")


def parse(text):
    return SRLParser().parse(text)


# --------------------------------------------------------------------------
# Grammar (C1, C2, H8, H9, H10, H11, M-prologue, M-dot, M-excluded-builtins)
# --------------------------------------------------------------------------


def test_a_shorthand_parses_in_all_positions():
    """C1: 'a' (rdf:type) must parse in body, head, and data positions."""
    parse("PREFIX : <http://example/>\nRULE { ?x :q :o } WHERE { ?x a :C }")
    parse("PREFIX : <http://example/>\nRULE { ?x a :C } WHERE { ?x :p :o }")
    parse("PREFIX : <http://example/>\nDATA { :s a :C }")


def test_set_assignment_parses_bind_rejected():
    """C2: SET(?v := expr) parses; BIND(expr AS ?v) is rejected."""
    rs = parse("PREFIX : <http://example/>\nRULE { ?x :q ?o } WHERE { ?x :p :o . SET (?o := 18) }")
    asg = [e for e in rs.rules[0].body.elements if isinstance(e, Assignment)]
    assert len(asg) == 1 and asg[0].variable == Variable("o")
    with pytest.raises(ParseError):
        parse("PREFIX : <http://example/>\nRULE { ?x :q ?o } WHERE { ?x :p :o . BIND(18 AS ?o) }")


def test_named_rule_iri():
    """H8: RULE iri? names the rule."""
    rs = parse("PREFIX : <http://example/>\nRULE :r1 { ?x :q :o } WHERE { ?x :p :o }")
    assert rs.rules[0].iri == IRI("http://example/r1")


def test_datalog_form_removed():
    """H9: the Datalog head :- body form no longer parses."""
    with pytest.raises(ParseError):
        parse("PREFIX : <http://example/>\n{ ?x :q :o } :- { ?x :p :o }")


def test_symmetric_postfix_only():
    """H10: postfix ( iri ) SYMMETRIC parses; prefix SYMMETRIC( iri ) rejected."""
    parse("PREFIX : <http://example/>\n(:knows) SYMMETRIC")
    with pytest.raises(ParseError):
        parse("PREFIX : <http://example/>\nSYMMETRIC(:knows)")


def test_reflexive_removed():
    """REFLEXIVE is not part of the grammar."""
    with pytest.raises(ParseError):
        parse("PREFIX : <http://example/>\nREFLEXIVE(:p)")


def test_data_block_rejects_variables():
    """H11: DATA blocks are ground; variables are rejected."""
    parse("PREFIX : <http://example/>\nDATA { :s :p :o }")
    with pytest.raises(ParseError):
        parse("PREFIX : <http://example/>\nDATA { ?x :p :o }")


def test_interspersed_prologue():
    """M-prologue: PREFIX may appear between rules."""
    rs = parse(
        "PREFIX : <http://example/>\n"
        "RULE { ?x :q :o } WHERE { ?x :p :o }\n"
        "PREFIX ex: <http://ex/>\n"
        "RULE { ?x ex:q :o } WHERE { ?x :p :o }"
    )
    assert len(rs.rules) == 2


def test_optional_dot_after_filter():
    """M-dot: an optional '.' may follow a FILTER element."""
    parse("PREFIX : <http://example/>\nRULE { ?x :q :o } WHERE { ?x :p ?o . FILTER (?o < 18) . ?x :r ?o }")


def test_excluded_builtins_rejected():
    """M-excluded-builtins / M-exists-builtin: removed builtins do not parse."""
    for fn in ["BOUND(?x)", "RAND()", "MD5(?x)", "SHA1(?x)", "SHA256(?x)", "COALESCE(?x,?y)"]:
        with pytest.raises(ParseError):
            parse(f"PREFIX : <http://example/>\nRULE {{ ?x :q :o }} WHERE {{ ?x :p ?y . FILTER({fn}) }}")
    with pytest.raises(ParseError):
        parse("PREFIX : <http://example/>\nRULE { ?x :q :o } WHERE { ?x :p ?y . FILTER(EXISTS { ?s :p ?o }) }")


def test_triple_term_parses():
    """M-tripleterm: triple terms parse in subject/object position."""
    rs = parse("PREFIX : <http://example/>\nRULE { <<( ?s :p ?o )>> :saidBy :x } WHERE { ?s :p ?o }")
    assert isinstance(rs.rules[0].head.templates[0].subject, TripleTerm)


# --------------------------------------------------------------------------
# Well-formedness (H12, M-wf-lax, M-wf-strict)
# --------------------------------------------------------------------------


def test_negation_body_wellformedness():
    """H12: a filter over an undefined variable inside NOT is rejected."""
    rs = parse("PREFIX : <http://example/>\nRULE { ?a :q :o } WHERE { ?a :p ?b . NOT { FILTER(?z > 1) } }")
    with pytest.raises(WellFormednessError):
        validate_rule_well_formedness(rs.rules[0])


def test_assignment_novelty_against_triple_var():
    """M-wf-lax: assigning a variable already bound by a triple pattern is ill-formed."""
    rs = parse("PREFIX : <http://example/>\nRULE { ?x :q ?y } WHERE { ?x :p ?y . SET(?x := 1) }")
    with pytest.raises(WellFormednessError):
        validate_rule_well_formedness(rs.rules[0])


def test_assignment_var_reused_later_is_wellformed():
    """M-wf-strict: an assignment var may appear in a LATER triple pattern."""
    rs = parse("PREFIX : <http://example/>\nRULE { ?x :q ?y } WHERE { ?a :p ?y . SET(?x := ?y) . ?x :r ?y }")
    validate_rule_well_formedness(rs.rules[0])  # must not raise


# --------------------------------------------------------------------------
# Stratification (C4, C7, H5)
# --------------------------------------------------------------------------


def test_blank_node_head_is_run_once():
    """C4: blank-node-head and assignment rules are run-once (no fixpoint loop)."""
    rs = parse("PREFIX : <http://example/>\nRULE { _:b :derivedFrom ?x } WHERE { ?x a :Thing }")
    layers = stratify(rs)
    assert layers[0].once == [0] and layers[0].general == []


def test_recursive_negation_raises():
    """C7: a recursive dependency through NOT raises StratificationError."""
    rs = parse(
        "PREFIX : <http://example/>\n"
        "RULE { ?x :a ?y } WHERE { ?x :seed ?y . NOT { ?x :b ?y } }\n"
        "RULE { ?x :b ?y } WHERE { ?x :a ?y }"
    )
    with pytest.raises(StratificationError):
        stratify(rs)


def test_negation_stratum_ordering():
    """H5: the rule defining a negated predicate is in a lower stratum."""
    rs = parse(
        "PREFIX : <http://example/>\n"
        "RULE { ?x :noP true } WHERE { ?x a :Thing . NOT { ?x :p ?y } }\n"
        "RULE { ?x :p :z } WHERE { ?x a :Special }"
    )
    stratify(rs)
    assert rs.rules[1].layer < rs.rules[0].layer


# --------------------------------------------------------------------------
# Evaluation (C3, H1, head blank-node freshness, GI)
# --------------------------------------------------------------------------


def test_data_block_seeded_into_evaluation():
    """C3: DATA-block triples are seeded and available for matching + in GI."""
    rs = parse(
        "PREFIX : <http://example.org/>\n"
        "DATA { :a a :Person }\n"
        "RULE { ?x :human true } WHERE { ?x a :Person }"
    )
    gi = RuleEngine(rs).evaluate(Graph(), inplace=False, results_only=True)
    assert (EX.a, RDF.type, EX.Person) in gi
    assert (EX.a, EX.human, RDFLiteral(True)) in gi


def test_graphmatch_repeated_variable_plain():
    """H1: ?x p ?x binds x once; no spurious match on distinct terms."""
    g = Graph()
    g.add((EX.a, EX.knows, EX.b))
    pat = TriplePattern(subject=Variable("x"), predicate=IRI("http://example.org/knows"), object=Variable("x"))
    assert graphMatch(g, pat) == []
    g.add((EX.c, EX.knows, EX.c))
    assert len(graphMatch(g, pat)) == 1


def test_graphmatch_repeated_variable_path():
    """H1 residual: ?x p/p ?x over a->b->c yields no solution; over a<->b yields two."""
    p = IRI("http://example.org/p")
    seq = PathSequence(elements=[p, p])
    pat = TriplePattern(subject=Variable("x"), predicate=seq, object=Variable("x"))
    g1 = Graph()
    g1.add((EX.a, EX.p, EX.b))
    g1.add((EX.b, EX.p, EX.c))
    assert graphMatch(g1, pat) == []
    g2 = Graph()
    g2.add((EX.a, EX.p, EX.b))
    g2.add((EX.b, EX.p, EX.a))
    assert len(graphMatch(g2, pat)) == 2


def test_head_blank_nodes_fresh_per_solution():
    """Head blank nodes are fresh per generated triple (not collapsed to one)."""
    rs = parse("PREFIX : <http://example.org/>\nRULE { [] a :Person ; :name ?n } WHERE { ?x :fullName ?n }")
    g = Graph()
    for who in ("Alice", "Bob", "Carol"):
        g.add((getattr(EX, who), EX.fullName, RDFLiteral(who)))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = RuleEngine(rs).evaluate(g, inplace=False)
    persons = set(s for s, _, _ in out.triples((None, RDF.type, EX.Person)))
    assert len(persons) == 3
    for pn in persons:
        assert len(list(out.objects(pn, EX.name))) == 1


# --------------------------------------------------------------------------
# Expressions (H13, H14, M-ebv, M-3valued, datetime, equality, ROUND, string lang)
# --------------------------------------------------------------------------


def _mu():
    return SolutionMapping({})


def test_sameterm_reachable():
    """H14: sameTerm dispatches (not None)."""
    from srl.ast import BuiltInCall

    v = eval_expr(BuiltInCall("sameTerm", [IRI("http://e/a"), IRI("http://e/a")]), _mu())
    assert v is not None and str(v).lower() in ("true", "1")


def test_rdf_star_triple_builtins():
    """H13: TRIPLE/isTRIPLE/SUBJECT dispatch to real values."""
    from srl.ast import BuiltInCall

    triple = BuiltInCall("TRIPLE", [IRI("http://e/s"), IRI("http://e/p"), IRI("http://e/o")])
    assert eval_expr(BuiltInCall("isTRIPLE", [triple]), _mu()) is not None
    subj = eval_expr(BuiltInCall("SUBJECT", [triple]), _mu())
    assert str(subj) == "http://e/s"


def test_ebv_derived_numeric():
    """M-ebv: EBV of derived numeric XSD types is computed, not false."""
    assert effective_boolean_value(RDFLiteral("5", datatype=XSD_INT)) is True
    assert effective_boolean_value(RDFLiteral("0", datatype=XSD_INT)) is False


def test_three_valued_logic_error_propagation():
    """M-3valued: false || error is error (None), not false."""
    from srl.ast import BinaryOp, BinaryOperator, Literal as Lit

    false_lit = Lit(value="false", datatype=IRI(str(XSD) + "boolean"))
    err = BinaryOp(operator=BinaryOperator.GT, left=Variable("unbound"), right=Lit(value="5", datatype=IRI(str(XSD) + "integer")))
    expr = BinaryOp(operator=BinaryOperator.OR, left=false_lit, right=err)
    assert eval_expr(expr, _mu()) is None


def test_datetime_accessors():
    """Eight [121] datetime accessors compute values."""
    dt = RDFLiteral("2020-05-17T12:34:56", datatype=URIRef(str(XSD) + "dateTime"))
    assert str(builtin_year([dt])) == "2020"
    assert str(builtin_month([dt])) == "5"
    assert str(builtin_hours([dt])) == "12"


def test_value_equality_language_tags():
    """Value equality respects language tags."""
    assert rdf_equal(RDFLiteral("cat", lang="en"), RDFLiteral("cat", lang="fr")) is False
    assert rdf_equal(RDFLiteral("cat", lang="en"), RDFLiteral("cat")) is False
    assert rdf_equal(RDFLiteral("cat", lang="en"), RDFLiteral("cat", lang="en")) is True


def test_round_half_up():
    """ROUND rounds half toward positive infinity, preserving datatype."""
    dec = URIRef(str(XSD) + "decimal")
    assert str(builtin_round([RDFLiteral("2.5", datatype=dec)])) == "3.0"
    assert str(builtin_round([RDFLiteral("0.5", datatype=dec)])) == "1.0"


def test_string_functions_preserve_language():
    """UCASE / CONCAT keep the language tag."""
    assert builtin_ucase([RDFLiteral("hi", lang="en")]).language == "en"
    assert builtin_concat([RDFLiteral("a", lang="en"), RDFLiteral("b", lang="en")]).language == "en"


def test_langmatches_rfc4647():
    """LANGMATCHES matches on subtag boundaries."""
    assert str(builtin_langmatches([RDFLiteral("english"), RDFLiteral("en")])) == "false"
    assert str(builtin_langmatches([RDFLiteral("en-US"), RDFLiteral("en")])) == "true"


# --------------------------------------------------------------------------
# SRL/RDF concrete syntax (H15, M-namespace)
# --------------------------------------------------------------------------


def test_srl_rdf_reader_all_features():
    """H15: the SRL/RDF encoding parses into the AST."""
    from srl.rdf import parse_rdf_rule_set

    ttl = """
    PREFIX :       <http://example/>
    PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX sparql: <http://www.w3.org/ns/sparql#>
    PREFIX srl:    <http://www.w3.org/ns/shacl-rules#>
    :rs rdf:type srl:RuleSet ;
      srl:data ( [ srl:subject :s ; srl:predicate :p ; srl:object :o ] ) ;
      srl:rules (
        [ rdf:type srl:Rule ;
          srl:body (
            [ srl:subject [ srl:varName "x" ] ; srl:predicate :p ; srl:object [ srl:varName "v" ] ]
            [ srl:filter [ sparql:less-than ( [ srl:varName "v" ] 18 ) ] ]
          ) ;
          srl:head ( [ srl:subject [ srl:varName "x" ] ; srl:predicate :q ; srl:object :o ] )
        ]
      ) .
    """
    g = Graph()
    g.parse(data=ttl, format="turtle")
    rs = parse_rdf_rule_set(g)
    assert len(rs.rules) == 1
    assert len(rs.data_blocks) == 1


def test_srl_rdf_equals_operator():
    """Reader maps sparql:equals to value equality and the filter fires."""
    from srl.rdf import parse_rdf_rule_set

    ttl = """
    PREFIX :       <http://example/>
    PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX sparql: <http://www.w3.org/ns/sparql#>
    PREFIX srl:    <http://www.w3.org/ns/shacl-rules#>
    :rs rdf:type srl:RuleSet ;
      srl:rules (
        [ rdf:type srl:Rule ;
          srl:body (
            [ srl:subject [ srl:varName "x" ] ; srl:predicate :p ; srl:object [ srl:varName "v" ] ]
            [ srl:filter [ sparql:equals ( [ srl:varName "v" ] 0 ) ] ]
          ) ;
          srl:head ( [ srl:subject [ srl:varName "x" ] ; srl:predicate :oneIsZero ; srl:object true ] )
        ]
      ) .
    """
    g = Graph()
    g.parse(data=ttl, format="turtle")
    rs = parse_rdf_rule_set(g)
    data = Graph()
    data.parse(data="PREFIX : <http://example/>\n:x :p 0 .", format="turtle")
    gi = RuleEngine(rs).evaluate(data, inplace=False, results_only=True)
    assert (EX.x if False else URIRef("http://example/x"), URIRef("http://example/oneIsZero"), RDFLiteral(True)) in gi


def test_namespaces_registered():
    """M-namespace: srl and sparql prefixes are registered."""
    from srl.rdf import NamespaceManager

    nm = NamespaceManager()
    assert nm.expand("srl:RuleSet") == "http://www.w3.org/ns/shacl-rules#RuleSet"
    assert nm.expand("sparql:less-than") == "http://www.w3.org/ns/sparql#less-than"


# --------------------------------------------------------------------------
# Imports (H7)
# --------------------------------------------------------------------------


def test_imports_resolved(tmp_path):
    """H7: IMPORTS are resolved and merged before evaluation."""
    lib = tmp_path / "lib.srl"
    lib.write_text(
        "PREFIX : <http://example/>\nRULE { ?x :ancestor ?y } WHERE { ?x :parent ?y }",
        encoding="utf-8",
    )
    main = (
        f"PREFIX : <http://example/>\n"
        f"IMPORTS <{lib.as_uri()}>\n"
        f"RULE { '{' } ?x :grandparent ?z { '}' } WHERE { '{' } ?x :parent/:parent ?z { '}' }"
    )
    rs = parse(main)
    engine = RuleEngine(rs)  # resolves imports in __init__
    assert len(engine.rule_set.rules) == 2
