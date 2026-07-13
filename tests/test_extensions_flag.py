# tests/test_extensions_flag.py
import pytest
from srl.parser import SRLParser, ParseError


FOR_RULE = ("PREFIX : <http://example/>\n"
            "RULE :r FOR ?this IN :PersonShape { ?this :adult true } "
            "WHERE { ?this :age ?a . FILTER(?a >= 18) }")


def test_for_clause_rejected_without_flag():
    with pytest.raises(ParseError):
        SRLParser().parse(FOR_RULE)


def test_for_clause_parsed_with_flag():
    rs = SRLParser(extensions=True).parse(FOR_RULE)
    assert len(rs.targeted_rules) == 1
    tr = rs.targeted_rules[0]
    assert tr.focus_var.name == "this"
    assert tr.shape.value == "http://example/PersonShape"
    assert tr.rule.iri.value == "http://example/r"
    # a plain rule with no FOR still lands in rules, not targeted_rules
    rs2 = SRLParser(extensions=True).parse("PREFIX : <http://example/>\nRULE { ?x :q :o } WHERE { ?x :p :o }")
    assert len(rs2.rules) == 1 and len(rs2.targeted_rules) == 0
