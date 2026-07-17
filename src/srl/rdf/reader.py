"""
Reader for the SRL/RDF concrete syntax (spec section #rdf-rules-syntax).

Parses an RDF graph encoding a ``srl:RuleSet`` into the AST defined in
srl.ast.nodes. The RDF encoding uses:

  * ``srl:RuleSet`` with ``srl:rules`` (list) and ``srl:data`` (list);
  * each rule has ``srl:body`` (list of rule elements) and ``srl:head`` (list
    of triple templates);
  * a triple pattern/template element has ``srl:subject``/``srl:predicate``/
    ``srl:object``, where a variable is a node ``[ srl:varName "x" ]``;
  * ``srl:filter`` holds a filter expression (a ``sparql:*`` function term);
  * ``srl:assign`` holds ``srl:assignVar`` and ``srl:assignValue``;
  * ``srl:not`` holds a list of negation-body rule elements.

The SPARQL function vocabulary (``sparql:less-than`` etc.) maps to the AST's
BinaryOp / BuiltInCall nodes.
"""

from typing import List, Optional

from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
from rdflib.collection import Collection

from ..ast.nodes import (
    RuleSet,
    Prologue,
    Rule,
    TargetedRule,
    RuleHead,
    RuleBody,
    DataBlock,
    Variable,
    IRI,
    Literal,
    BlankNode,
    TriplePattern,
    TripleTemplate,
    ConditionExpression,
    NegationElement,
    Assignment,
    BinaryOp,
    BinaryOperator,
    BuiltInCall,
    UnaryOp,
    UnaryOperator,
)
from . import vocab as V


class RDFSyntaxError(Exception):
    """Raised when an RDF graph is not a well-formed SRL/RDF rule set."""


# SPARQL function IRI -> BinaryOperator (for relational/arithmetic ops).
# The spec's RDF examples use sparql:equals, sparql:logical-or, sparql:logical-and,
# sparql:less-than, sparql:greater-than. Accept both those canonical names and
# common aliases.
_SPARQL_BINOP = {
    str(V.SPARQL["less-than"]): BinaryOperator.LT,
    str(V.SPARQL["greater-than"]): BinaryOperator.GT,
    str(V.SPARQL["less-than-or-equal"]): BinaryOperator.LE,
    str(V.SPARQL["greater-than-or-equal"]): BinaryOperator.GE,
    str(V.SPARQL["equals"]): BinaryOperator.EQ,
    str(V.SPARQL["equal"]): BinaryOperator.EQ,
    str(V.SPARQL["not-equals"]): BinaryOperator.NE,
    str(V.SPARQL["not-equal"]): BinaryOperator.NE,
    str(V.SPARQL["logical-and"]): BinaryOperator.AND,
    str(V.SPARQL["and"]): BinaryOperator.AND,
    str(V.SPARQL["logical-or"]): BinaryOperator.OR,
    str(V.SPARQL["or"]): BinaryOperator.OR,
    str(V.SPARQL["add"]): BinaryOperator.ADD,
    str(V.SPARQL["subtract"]): BinaryOperator.SUB,
    str(V.SPARQL["multiply"]): BinaryOperator.MUL,
    str(V.SPARQL["divide"]): BinaryOperator.DIV,
}


# SPARQL function IRI -> UnaryOperator (for unary logical/arithmetic ops).
_SPARQL_UNOP = {
    str(V.SPARQL["logical-not"]): UnaryOperator.NOT,
    str(V.SPARQL["unary-minus"]): UnaryOperator.MINUS,
    str(V.SPARQL["unary-plus"]): UnaryOperator.PLUS,
}


def _rdf_list(graph: Graph, node) -> List:
    """Return the members of an RDF list node (empty list if nil/None)."""
    if node is None:
        return []
    return list(Collection(graph, node))


def _term_to_ast(graph: Graph, node):
    """Convert an RDF node in a triple position to an AST term."""
    # Variable: a node carrying srl:varName.
    var_name = graph.value(node, V.varName)
    if var_name is not None:
        return Variable(name=str(var_name))
    if isinstance(node, URIRef):
        return IRI(str(node))
    if isinstance(node, RDFLiteral):
        dt = IRI(str(node.datatype)) if node.datatype else None
        return Literal(value=str(node), language=node.language, datatype=dt)
    if isinstance(node, BNode):
        return BlankNode(label=str(node))
    raise RDFSyntaxError(f"Unrecognized RDF term: {node!r}")


def _expr_to_ast(graph: Graph, node):
    """Convert an RDF expression node (sparql:* function or term) to an AST expression."""
    # A function application: exactly one sparql:* predicate whose object is a list.
    for pred, obj in graph.predicate_objects(node):
        pred_str = str(pred)
        if pred_str.startswith(str(V.SPARQL)):
            args_nodes = _rdf_list(graph, obj)
            args = [_expr_to_ast(graph, a) for a in args_nodes]
            if pred_str in _SPARQL_UNOP and len(args) == 1:
                return UnaryOp(operator=_SPARQL_UNOP[pred_str], operand=args[0])
            if pred_str in _SPARQL_BINOP and len(args) == 2:
                return BinaryOp(operator=_SPARQL_BINOP[pred_str], left=args[0], right=args[1])
            # Otherwise a named built-in: local name of the sparql: term.
            fname = pred_str[len(str(V.SPARQL)) :]
            return BuiltInCall(function_name=fname, arguments=args)
    # Not a function application: a plain term (variable/IRI/literal).
    return _term_to_ast(graph, node)


def _triple_element(graph, node) -> Optional[tuple]:
    """Return (s, p, o) AST terms if node encodes a triple pattern/template."""
    s = graph.value(node, V.subject)
    p = graph.value(node, V.predicate)
    o = graph.value(node, V.object_)
    if s is None and p is None and o is None:
        return None
    return (
        _term_to_ast(graph, s),
        _term_to_ast(graph, p),
        _term_to_ast(graph, o),
    )


def _body_element(graph, node):
    """Convert one RDF rule-element node to an AST rule body element."""
    # Filter element.
    filt = graph.value(node, V.filter_)
    if filt is not None:
        return ConditionExpression(expression=_expr_to_ast(graph, filt))

    # Assignment element.
    asg = graph.value(node, V.assign)
    if asg is not None:
        var_node = graph.value(asg, V.assignVar)
        val_node = graph.value(asg, V.assignValue)
        variable = _term_to_ast(graph, var_node)
        expression = _expr_to_ast(graph, val_node)
        return Assignment(variable=variable, expression=expression)

    # Negation element.
    neg = graph.value(node, V.not_)
    if neg is not None:
        members = _rdf_list(graph, neg)
        patterns = []
        for m in members:
            triple = _triple_element(graph, m)
            if triple is not None:
                patterns.append(TriplePattern(subject=triple[0], predicate=triple[1], object=triple[2]))
            else:
                filt2 = graph.value(m, V.filter_)
                if filt2 is not None:
                    patterns.append(ConditionExpression(expression=_expr_to_ast(graph, filt2)))
        return NegationElement(body_patterns=patterns)

    # Triple pattern element.
    triple = _triple_element(graph, node)
    if triple is not None:
        return TriplePattern(subject=triple[0], predicate=triple[1], object=triple[2])

    raise RDFSyntaxError(f"Unrecognized rule element: {node!r}")


def _head_template(graph, node) -> TripleTemplate:
    triple = _triple_element(graph, node)
    if triple is None:
        raise RDFSyntaxError(f"Head element is not a triple template: {node!r}")
    return TripleTemplate(subject=triple[0], predicate=triple[1], object=triple[2])


def _data_triple(graph, node) -> TripleTemplate:
    triple = _triple_element(graph, node)
    if triple is None:
        raise RDFSyntaxError(f"Data element is not a triple: {node!r}")
    # Data blocks hold ground triples only: variables are not allowed.
    if any(isinstance(t, Variable) for t in triple):
        raise RDFSyntaxError(
            f"Data-block triple must not contain variables (ground triples only): {node!r}"
        )
    return TripleTemplate(subject=triple[0], predicate=triple[1], object=triple[2])


def _build_rule(graph: Graph, rule_node) -> Rule:
    body_nodes = _rdf_list(graph, graph.value(rule_node, V.body))
    head_nodes = _rdf_list(graph, graph.value(rule_node, V.head))
    body = RuleBody(elements=[_body_element(graph, n) for n in body_nodes])
    head = RuleHead(templates=[_head_template(graph, n) for n in head_nodes])
    rule_iri = IRI(str(rule_node)) if isinstance(rule_node, URIRef) else None
    return Rule(head=head, body=body, iri=rule_iri)


def parse_rdf_rule_set(graph: Graph, extensions: bool = False) -> RuleSet:
    """
    Parse an RDF graph containing exactly one ``srl:RuleSet`` into an AST RuleSet.

    When ``extensions`` is true, the opt-in rule-to-shape targeting attachment is
    recognised: a rule node carrying ``srl:targetShape`` (with an optional
    ``srl:focusVar``) becomes a ``TargetedRule`` (direction ``rule-to-shape``),
    and a shape node carrying ``sh:rule``/``srl:rule`` pointing at a rule node
    becomes a ``TargetedRule`` (direction ``shape-to-rule``). Without the flag,
    these attachments are ignored (the wrapped rule is treated as a plain rule).
    """
    from rdflib.namespace import RDF as _RDF

    rs_nodes = list(graph.subjects(_RDF.type, V.RuleSet))
    if not rs_nodes:
        raise RDFSyntaxError("No srl:RuleSet found in graph")
    rs_node = rs_nodes[0]

    # Rules.
    rules: List[Rule] = []
    targeted_rules: List[TargetedRule] = []
    for rule_node in _rdf_list(graph, graph.value(rs_node, V.rules)):
        rule = _build_rule(graph, rule_node)
        target_shape = graph.value(rule_node, V.targetShape) if extensions else None
        if target_shape is not None:
            focus_lit = graph.value(rule_node, V.focusVar)
            focus_name = str(focus_lit) if focus_lit is not None else "this"
            targeted_rules.append(
                TargetedRule(
                    rule=rule,
                    focus_var=Variable(name=focus_name),
                    shape=IRI(str(target_shape)),
                    direction="rule-to-shape",
                )
            )
        else:
            rules.append(rule)

    # Shape-to-rule attachment: a shape node with sh:rule/srl:rule -> rule node.
    if extensions:
        sh_rule = V.SH.rule
        for pred in (sh_rule, V.rule):
            for shape_node, rule_node in graph.subject_objects(pred):
                rule = _build_rule(graph, rule_node)
                focus_lit = graph.value(rule_node, V.focusVar)
                focus_name = str(focus_lit) if focus_lit is not None else "this"
                targeted_rules.append(
                    TargetedRule(
                        rule=rule,
                        focus_var=Variable(name=focus_name),
                        shape=IRI(str(shape_node)),
                        direction="shape-to-rule",
                    )
                )

    # Data blocks.
    data_triples = [
        _data_triple(graph, n) for n in _rdf_list(graph, graph.value(rs_node, V.data))
    ]
    data_blocks = [DataBlock(triples=data_triples)] if data_triples else []

    return RuleSet(
        prologue=Prologue(),
        rules=rules,
        data_blocks=data_blocks,
        targeted_rules=targeted_rules,
    )


def parse_rdf_file(path: str, fmt: Optional[str] = None, extensions: bool = False) -> RuleSet:
    """Parse an SRL/RDF file (Turtle by default) into an AST RuleSet."""
    graph = Graph()
    graph.parse(path, format=fmt or "turtle")
    return parse_rdf_rule_set(graph, extensions=extensions)
