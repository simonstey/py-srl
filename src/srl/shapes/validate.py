"""SHACL Core conformance checking for the opt-in rule-to-shape targeting extension.

This is NOT part of the SRL spec. It evaluates the subset of SHACL 1.2 Core
parsed by :mod:`srl.shapes.model` (see the support matrix). ``conforms`` returns
``True`` iff a node satisfies every node-level constraint and every property
shape of the given shape.

Property paths reuse :func:`srl.engine.solutions.evaluate_path`; SHACL RDF lists
reuse :class:`rdflib.collection.Collection`.
"""

import re
from typing import Any, List, Optional, Set

from rdflib import BNode, Graph
from rdflib import Literal as RDFLiteral
from rdflib import URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF, RDFS
from rdflib.term import Node

from ..ast.nodes import IRI, InversePath, PathSequence, PropertyPath
from ..engine.solutions import evaluate_path
from .model import SH, NodeShape, PropertyShape, UnsupportedShapeFeatureError, load_shape

# ---------------------------------------------------------------------------
# Small RDF helpers
# ---------------------------------------------------------------------------


def _pyval(term: Node) -> Any:
    """Best-effort Python value for an RDF term (for numeric/comparison ops)."""
    if isinstance(term, RDFLiteral):
        return term.toPython()
    return term


def _rdf_list(graph: Graph, node: Node) -> List[Node]:
    """Return the members of an RDF list, or ``[]`` if ``node`` is not a list."""
    if node == RDF.nil:
        return []
    if not isinstance(node, (BNode, URIRef)):
        return []
    if graph.value(node, RDF.first) is None:
        return []
    return list(Collection(graph, node))


def _subclass_of(sub: Node, sup: Node, graph: Graph) -> bool:
    """True if ``sub`` is ``sup`` or a transitive ``rdfs:subClassOf`` of ``sup``."""
    if sub == sup:
        return True
    seen: Set[Node] = set()
    frontier = [sub]
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for parent in graph.objects(cur, RDFS.subClassOf):
            if parent == sup:
                return True
            frontier.append(parent)
    return False


def _is_instance(node: Node, cls: Node, graph: Graph) -> bool:
    """SHACL ``sh:class`` membership: node has a type that is (a subclass of) cls."""
    return any(_subclass_of(t, cls, graph) for t in graph.objects(node, RDF.type))


def _shacl_path_to_ast(graph: Graph, path: Node) -> PropertyPath:
    """Convert a SHACL RDF path structure into an AST path (IRI/Inverse/Sequence)."""
    if isinstance(path, URIRef):
        return IRI(str(path))
    inverse = graph.value(path, SH.inversePath)
    if inverse is not None:
        return InversePath(path=_shacl_path_to_ast(graph, inverse))
    members = _rdf_list(graph, path)
    if members:
        return PathSequence(elements=[_shacl_path_to_ast(graph, m) for m in members])
    raise UnsupportedShapeFeatureError(f"Unsupported SHACL property path: {path!r}")


def _value_nodes(node: Node, path: Any, graph: Graph) -> Set[Node]:
    """Value nodes reachable from ``node`` along a SHACL property ``path``."""
    if isinstance(path, URIRef):
        return set(graph.objects(node, path))
    ast_path = _shacl_path_to_ast(graph, path)
    return {end for start, end in evaluate_path(graph, ast_path) if start == node}


_NODEKINDS = {
    str(SH.IRI): lambda t: isinstance(t, URIRef),
    str(SH.BlankNode): lambda t: isinstance(t, BNode),
    str(SH.Literal): lambda t: isinstance(t, RDFLiteral),
    str(SH.BlankNodeOrIRI): lambda t: isinstance(t, (BNode, URIRef)),
    str(SH.BlankNodeOrLiteral): lambda t: isinstance(t, (BNode, RDFLiteral)),
    str(SH.IRIOrLiteral): lambda t: isinstance(t, (URIRef, RDFLiteral)),
}


def _lang_matches(tag: Optional[str], pattern: str) -> bool:
    if not tag:
        return False
    tag = tag.lower()
    pattern = pattern.lower()
    return tag == pattern or tag.startswith(pattern + "-")


def _regex_flags(flags: Optional[str]) -> int:
    result = 0
    if not flags:
        return result
    mapping = {"i": re.IGNORECASE, "s": re.DOTALL, "m": re.MULTILINE, "x": re.VERBOSE}
    for ch in str(flags):
        result |= mapping.get(ch, 0)
    return result


def _conforms_shape_ref(node: Node, ref: Node, graph: Graph, shapes_graph: Graph) -> bool:
    """Recurse: does ``node`` conform to the (node/inline) shape at ``ref``?"""
    return conforms(node, load_shape(shapes_graph, ref), graph, shapes_graph)


# ---------------------------------------------------------------------------
# Constraint checking
# ---------------------------------------------------------------------------


def _check_constraint(
    kind: str,
    value: Node,
    focus_node: Node,
    value_nodes: Set[Node],
    graph: Graph,
    shapes_graph: Graph,
    flags: Optional[str] = None,
) -> bool:
    """Return True iff the value nodes satisfy the constraint ``kind``."""
    # Cardinality -----------------------------------------------------------
    if kind == "minCount":
        return len(value_nodes) >= int(_pyval(value))  # type: ignore[arg-type]
    if kind == "maxCount":
        return len(value_nodes) <= int(_pyval(value))  # type: ignore[arg-type]

    # Value type ------------------------------------------------------------
    if kind == "class":
        return all(_is_instance(vn, value, graph) for vn in value_nodes)
    if kind == "datatype":
        for vn in value_nodes:
            if not isinstance(vn, RDFLiteral):
                return False
            dt = vn.datatype
            if dt is None and vn.language is None:
                dt = URIRef("http://www.w3.org/2001/XMLSchema#string")
            if dt != value:
                return False
        return True
    if kind == "nodeKind":
        predicate = _NODEKINDS.get(str(value))
        if predicate is None:
            raise UnsupportedShapeFeatureError(f"sh:nodeKind {value!r} is not supported")
        return all(predicate(vn) for vn in value_nodes)

    # Value -----------------------------------------------------------------
    if kind == "hasValue":
        return value in value_nodes
    if kind == "in":
        allowed = set(_rdf_list(graph, value))
        return all(vn in allowed for vn in value_nodes)

    # Range (numeric) -------------------------------------------------------
    if kind in ("minInclusive", "maxInclusive", "minExclusive", "maxExclusive"):
        bound = _pyval(value)
        for vn in value_nodes:
            try:
                v = _pyval(vn)
                if kind == "minInclusive" and not v >= bound:  # type: ignore[operator]
                    return False
                if kind == "maxInclusive" and not v <= bound:  # type: ignore[operator]
                    return False
                if kind == "minExclusive" and not v > bound:  # type: ignore[operator]
                    return False
                if kind == "maxExclusive" and not v < bound:  # type: ignore[operator]
                    return False
            except TypeError:
                return False
        return True

    # String ----------------------------------------------------------------
    if kind in ("minLength", "maxLength"):
        bound = int(_pyval(value))  # type: ignore[arg-type]
        for vn in value_nodes:
            if isinstance(vn, BNode):
                return False
            length = len(str(vn))
            if kind == "minLength" and length < bound:
                return False
            if kind == "maxLength" and length > bound:
                return False
        return True
    if kind == "pattern":
        compiled = re.compile(str(value), _regex_flags(flags))
        for vn in value_nodes:
            if isinstance(vn, BNode):
                return False
            if compiled.search(str(vn)) is None:
                return False
        return True
    if kind == "languageIn":
        langs = [str(x) for x in _rdf_list(graph, value)]
        for vn in value_nodes:
            if not isinstance(vn, RDFLiteral):
                return False
            if not any(_lang_matches(vn.language, p) for p in langs):
                return False
        return True
    if kind == "uniqueLang":
        if not bool(_pyval(value)):
            return True
        seen: Set[str] = set()
        for vn in value_nodes:
            if isinstance(vn, RDFLiteral) and vn.language:
                if vn.language in seen:
                    return False
                seen.add(vn.language)
        return True

    # Shape-based -----------------------------------------------------------
    if kind == "node":
        return all(_conforms_shape_ref(vn, value, graph, shapes_graph) for vn in value_nodes)
    if kind == "someValue":
        return any(_conforms_shape_ref(vn, value, graph, shapes_graph) for vn in value_nodes)

    # Logical ---------------------------------------------------------------
    if kind == "and":
        shapes = _rdf_list(graph, value)
        return all(
            all(_conforms_shape_ref(vn, s, graph, shapes_graph) for s in shapes)
            for vn in value_nodes
        )
    if kind == "or":
        shapes = _rdf_list(graph, value)
        return all(
            any(_conforms_shape_ref(vn, s, graph, shapes_graph) for s in shapes)
            for vn in value_nodes
        )
    if kind == "xone":
        shapes = _rdf_list(graph, value)
        for vn in value_nodes:
            hits = sum(1 for s in shapes if _conforms_shape_ref(vn, s, graph, shapes_graph))
            if hits != 1:
                return False
        return True
    if kind == "not":
        return all(not _conforms_shape_ref(vn, value, graph, shapes_graph) for vn in value_nodes)

    # 1.2 additions ---------------------------------------------------------
    if kind == "rootClass":
        return all(_subclass_of(vn, value, graph) for vn in value_nodes)
    if kind == "subsetOf":
        superset = _value_nodes(focus_node, value, graph)
        return value_nodes <= superset

    # List family -----------------------------------------------------------
    if kind == "memberShape":
        for vn in value_nodes:
            for member in _rdf_list(graph, vn):
                if not _conforms_shape_ref(member, value, graph, shapes_graph):
                    return False
        return True
    if kind in ("minListLength", "maxListLength"):
        bound = int(_pyval(value))  # type: ignore[arg-type]
        for vn in value_nodes:
            count = len(_rdf_list(graph, vn))
            if kind == "minListLength" and count < bound:
                return False
            if kind == "maxListLength" and count > bound:
                return False
        return True
    if kind == "uniqueMembers":
        if not bool(_pyval(value)):
            return True
        for vn in value_nodes:
            members = _rdf_list(graph, vn)
            if len(members) != len(set(members)):
                return False
        return True

    # Reification (best-effort; rdflib 7.6.0 lacks first-class triple terms) -
    if kind in ("reifierShape", "reificationRequired"):
        return True

    raise UnsupportedShapeFeatureError(f"sh:{kind} is not yet evaluable")


def _check_property(
    focus_node: Node, prop: PropertyShape, graph: Graph, shapes_graph: Graph
) -> bool:
    value_nodes = _value_nodes(focus_node, prop.path, graph)
    flags = next((c.value for c in prop.constraints if c.kind == "flags"), None)
    for c in prop.constraints:
        if c.kind == "flags":
            continue  # consumed by sh:pattern
        if not _check_constraint(
            c.kind, c.value, focus_node, value_nodes, graph, shapes_graph, flags  # type: ignore[arg-type]
        ):
            return False
    return True


def conforms(node: Node, shape: NodeShape, graph: Graph, shapes_graph: Graph) -> bool:
    """Return True iff ``node`` conforms to ``shape`` (node constraints + property shapes)."""
    node_values: Set[Node] = {node}
    node_flags = next((c.value for c in shape.constraints if c.kind == "flags"), None)
    for c in shape.constraints:
        if c.kind == "flags":
            continue
        if not _check_constraint(
            c.kind, c.value, node, node_values, graph, shapes_graph, node_flags  # type: ignore[arg-type]
        ):
            return False
    for prop in shape.property_shapes:
        if not _check_property(node, prop, graph, shapes_graph):
            return False
    return True
