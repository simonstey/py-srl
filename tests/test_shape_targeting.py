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
