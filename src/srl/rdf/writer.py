"""Serializer for the SRL/RDF concrete syntax (AST -> RDF), inverse of reader.py."""

from typing import Optional

from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF

from ..ast.nodes import (
    RuleSet,
    Rule,
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
