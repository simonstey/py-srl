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


from rdflib import Graph, Literal as RDFLit, URIRef
from srl.ast import IRI, Literal, Variable, BinaryOp, BinaryOperator
from srl.rdf import vocab as V


def test_write_term_variable_and_iri():
    from srl.rdf.writer import _write_term
    g = Graph()
    var_node = _write_term(g, Variable("x"))
    assert (var_node, V.varName, RDFLit("x")) in g
    iri_node = _write_term(g, IRI("http://example/p"))
    assert iri_node == URIRef("http://example/p")


def test_write_expr_binaryop():
    from srl.rdf.writer import _write_expr
    from rdflib.collection import Collection
    g = Graph()
    expr = BinaryOp(operator=BinaryOperator.LT, left=Variable("v"), right=Literal("18", datatype=IRI("http://www.w3.org/2001/XMLSchema#integer")))
    node = _write_expr(g, expr)
    # node has exactly one sparql:less-than edge to a 2-item list
    lt = URIRef(str(V.SPARQL) + "less-than")
    objs = list(g.objects(node, lt))
    assert len(objs) == 1
    members = list(Collection(g, objs[0]))
    assert len(members) == 2
