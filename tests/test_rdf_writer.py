from rdflib import Graph
from srl.rdf import parse_rdf_rule_set
from srl.ast import ConditionExpression, UnaryOp, UnaryOperator, BinaryOp


def _first_filter(rs):
    for e in rs.rules[0].body.elements:
        if isinstance(e, ConditionExpression):
            return e.expression
    raise AssertionError("no filter")


def test_reader_reconstructs_unary_not():
    ttl = """
    PREFIX :       <http://example/>
    PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX sparql: <http://www.w3.org/ns/sparql#>
    PREFIX srl:    <http://www.w3.org/ns/shacl-rules#>
    :rs rdf:type srl:RuleSet ; srl:rules (
      [ rdf:type srl:Rule ;
        srl:body (
          [ srl:subject [ srl:varName "x" ] ; srl:predicate :p ; srl:object [ srl:varName "v" ] ]
          [ srl:filter [ sparql:logical-not (
              [ sparql:greater-than ( [ srl:varName "v" ] 5 ) ] ) ] ]
        ) ;
        srl:head ( [ srl:subject [ srl:varName "x" ] ; srl:predicate :q ; srl:object :o ] ) ]
    ) .
    """
    g = Graph()
    g.parse(data=ttl, format="turtle")
    rs = parse_rdf_rule_set(g)
    expr = _first_filter(rs)
    assert isinstance(expr, UnaryOp)
    assert expr.operator == UnaryOperator.NOT
    assert isinstance(expr.operand, BinaryOp)
