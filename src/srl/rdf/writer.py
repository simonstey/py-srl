"""Serializer for the SRL/RDF concrete syntax (AST -> RDF), inverse of reader.py."""

import io
from typing import Optional

from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF
from rdflib.plugins.serializers.turtle import TurtleSerializer

from ..ast.nodes import (
    RuleSet,
    Rule,
    TargetedRule,
    DataBlock,
    Variable,
    IRI,
    Literal,
    BlankNode,
    TripleTerm,
    TriplePattern,
    TripleTemplate,
    ConditionExpression,
    NegationElement,
    Assignment,
    BinaryOp,
    UnaryOp,
    FunctionCall,
    BuiltInCall,
    BinaryOperator,
    UnaryOperator,
)
from . import vocab as V

try:
    from rdflib.term import Triple as RDFTripleTerm  # type: ignore
except Exception:  # pragma: no cover
    RDFTripleTerm = None

_CANONICAL_BINOP = {
    BinaryOperator.EQ: "equals",
    BinaryOperator.NE: "not-equals",
    BinaryOperator.LT: "less-than",
    BinaryOperator.GT: "greater-than",
    BinaryOperator.LE: "less-than-or-equal",
    BinaryOperator.GE: "greater-than-or-equal",
    BinaryOperator.AND: "logical-and",
    BinaryOperator.OR: "logical-or",
    BinaryOperator.ADD: "add",
    BinaryOperator.SUB: "subtract",
    BinaryOperator.MUL: "multiply",
    BinaryOperator.DIV: "divide",
}
_CANONICAL_UNOP = {
    UnaryOperator.NOT: "logical-not",
    UnaryOperator.MINUS: "unary-minus",
    UnaryOperator.PLUS: "unary-plus",
}


def _write_list(g: Graph, nodes) -> object:
    head = BNode()
    Collection(g, head, list(nodes))
    return head


def _write_term(g: Graph, term):
    if isinstance(term, Variable):
        n = BNode()
        g.add((n, V.varName, RDFLiteral(term.name)))
        return n
    if isinstance(term, IRI):
        return URIRef(term.value)
    if isinstance(term, Literal):
        dt = URIRef(term.datatype.value) if term.datatype else None
        if term.language:
            return RDFLiteral(term.value, lang=term.language)
        return RDFLiteral(term.value, datatype=dt)
    if isinstance(term, BlankNode):
        return BNode(term.label) if term.label else BNode()
    if isinstance(term, TripleTerm):
        s = _write_term(g, term.subject)
        p = _write_term(g, term.predicate)
        o = _write_term(g, term.object)
        if RDFTripleTerm is not None:
            return RDFTripleTerm((s, p, o))
        n = BNode()
        g.add((n, V.subject, s))
        g.add((n, V.predicate, p))
        g.add((n, V.object_, o))
        return n
    raise TypeError(f"Cannot write term: {term!r}")


def _write_expr(g: Graph, expr):
    if isinstance(expr, (Variable, IRI, Literal, BlankNode, TripleTerm)):
        return _write_term(g, expr)
    if isinstance(expr, BinaryOp):
        n = BNode()
        pred = URIRef(str(V.SPARQL) + _CANONICAL_BINOP[expr.operator])
        g.add((n, pred, _write_list(g, [_write_expr(g, expr.left), _write_expr(g, expr.right)])))
        return n
    if isinstance(expr, UnaryOp):
        n = BNode()
        pred = URIRef(str(V.SPARQL) + _CANONICAL_UNOP[expr.operator])
        g.add((n, pred, _write_list(g, [_write_expr(g, expr.operand)])))
        return n
    if isinstance(expr, BuiltInCall):
        n = BNode()
        pred = URIRef(str(V.SPARQL) + expr.function_name)
        g.add((n, pred, _write_list(g, [_write_expr(g, a) for a in expr.arguments])))
        return n
    if isinstance(expr, FunctionCall):
        n = BNode()
        g.add(
            (n, URIRef(expr.function.value), _write_list(g, [_write_expr(g, a) for a in expr.arguments]))
        )
        return n
    raise TypeError(f"Cannot write expression: {expr!r}")


def _write_triple(g: Graph, triple) -> object:
    n = BNode()
    g.add((n, V.subject, _write_term(g, triple.subject)))
    g.add((n, V.predicate, _write_term(g, triple.predicate)))
    g.add((n, V.object_, _write_term(g, triple.object)))
    return n


def _write_body_element(g: Graph, elt) -> object:
    if isinstance(elt, TriplePattern):
        return _write_triple(g, elt)
    if isinstance(elt, ConditionExpression):
        n = BNode()
        g.add((n, V.filter_, _write_expr(g, elt.expression)))
        return n
    if isinstance(elt, Assignment):
        n = BNode()
        asg = BNode()
        g.add((asg, V.assignVar, _write_term(g, elt.variable)))
        g.add((asg, V.assignValue, _write_expr(g, elt.expression)))
        g.add((n, V.assign, asg))
        return n
    if isinstance(elt, NegationElement):
        n = BNode()
        members = [_write_body_element(g, e) for e in elt.body_patterns]
        g.add((n, V.not_, _write_list(g, members)))
        return n
    raise TypeError(f"Cannot write body element: {elt!r}")


def _write_rule(g: Graph, rule: Rule) -> object:
    rn = URIRef(rule.iri.value) if rule.iri else BNode()
    g.add((rn, RDF.type, V.Rule))
    g.add((rn, V.body, _write_list(g, [_write_body_element(g, e) for e in rule.body.elements])))
    g.add((rn, V.head, _write_list(g, [_write_triple(g, t) for t in rule.head.templates])))
    return rn


def to_rdf_graph(rule_set: RuleSet) -> Graph:
    g = Graph()
    rs_node = BNode()
    g.add((rs_node, RDF.type, V.RuleSet))

    rule_nodes = [_write_rule(g, rule) for rule in rule_set.rules]

    for tr in rule_set.targeted_rules:
        rn = _write_rule(g, tr.rule)
        g.add((rn, V.targetShape, URIRef(tr.shape.value)))
        g.add((rn, V.focusVar, RDFLiteral(tr.focus_var.name)))
        rule_nodes.append(rn)

    g.add((rs_node, V.rules, _write_list(g, rule_nodes)))

    data_triples = [t for block in rule_set.data_blocks for t in block.triples]
    if data_triples:
        g.add((rs_node, V.data, _write_list(g, [_write_triple(g, t) for t in data_triples])))
    return g


class _FullIRITurtleSerializer(TurtleSerializer):
    """Turtle serializer that never coins generated ``ns1:`` prefixes.

    rdflib's default Turtle serializer invents opaque prefixes (``ns1:`` …) for
    any namespace it meets in a predicate position, which then also abbreviates
    class IRIs (``srl:RuleSet``). Writing the SRL vocabulary IRIs in full keeps
    the output unambiguous and self-describing without depending on a prefix map.

    The relevant hook is ``getQName`` on rdflib < 7.6 and ``get_pname`` on
    rdflib >= 7.6 (renamed there); override both so prefix generation stays off
    regardless of the installed rdflib version.
    """

    def get_pname(self, uri: object, gen_prefix: bool = True) -> Optional[str]:
        return super().get_pname(uri, gen_prefix=False)

    def getQName(self, uri: object, gen_prefix: bool = True) -> Optional[str]:
        return super().getQName(uri, gen_prefix=False)


def serialize(rule_set: RuleSet, fmt: str = "turtle") -> str:
    g = to_rdf_graph(rule_set)
    if fmt == "turtle":
        buf = io.BytesIO()
        _FullIRITurtleSerializer(g).serialize(buf)
        return buf.getvalue().decode("utf-8")
    return g.serialize(format=fmt)
