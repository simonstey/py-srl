"""Parse a SHACL Core node shape into an in-memory shape model.

This is part of the opt-in rule-to-shape targeting extension and is NOT part of
the SRL spec. It supports a subset of SHACL 1.2 Core (see the support matrix):
node-level parsing, ``sh:property``/``sh:path``, the value-type/cardinality/
range/string/value/logical/node constraints, the 1.2 additions
(``sh:someValue``, ``sh:rootClass``, the list family, ``sh:subsetOf``,
``sh:reifierShape``), and the targets. Any ``sh:`` predicate on a shape (or
property shape) outside the supported set raises ``UnsupportedShapeFeatureError``.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF
from rdflib.term import Node

SH = Namespace("http://www.w3.org/ns/shacl#")


class UnsupportedShapeFeatureError(Exception):
    """Raised when a shape uses a ``sh:`` feature outside the supported subset."""


@dataclass(frozen=True)
class Constraint:
    kind: str
    value: object


@dataclass(frozen=True)
class PropertyShape:
    path: object
    constraints: Tuple[Constraint, ...]


@dataclass(frozen=True)
class NodeShape:
    iri: object
    targets: Tuple[tuple, ...]
    constraints: Tuple[Constraint, ...]
    property_shapes: Tuple[PropertyShape, ...]


_TARGET_PREDS = {
    "targetClass",
    "targetNode",
    "targetSubjectsOf",
    "targetObjectsOf",
    "targetWhere",
    "shape",
}
_NODE_CONSTRAINTS = {
    "class",
    "datatype",
    "nodeKind",
    "hasValue",
    "in",
    "node",
    "and",
    "or",
    "not",
    "xone",
    "rootClass",
    "someValue",
    "subsetOf",
}
_PROP_CONSTRAINTS = _NODE_CONSTRAINTS | {
    "minCount",
    "maxCount",
    "pattern",
    "flags",
    "minInclusive",
    "maxInclusive",
    "minExclusive",
    "maxExclusive",
    "minLength",
    "maxLength",
    "languageIn",
    "uniqueLang",
    "memberShape",
    "minListLength",
    "maxListLength",
    "uniqueMembers",
    "reifierShape",
    "reificationRequired",
}
_IGNORED = {"path"}  # structural, handled explicitly


def _local(pred: Node) -> Optional[str]:
    s = str(pred)
    return s[len(str(SH)):] if s.startswith(str(SH)) else None


def _load_property(graph: Graph, node: Node) -> PropertyShape:
    path = graph.value(node, SH.path)
    constraints = []
    for pred, obj in graph.predicate_objects(node):
        name = _local(pred)
        if name is None:
            continue
        if name in _IGNORED:
            continue
        if name not in _PROP_CONSTRAINTS:
            raise UnsupportedShapeFeatureError(
                f"sh:{name} on a property shape is not supported"
            )
        constraints.append(Constraint(kind=name, value=obj))
    return PropertyShape(path=path, constraints=tuple(constraints))


def load_shape(graph: Graph, shape_iri: Node) -> NodeShape:
    targets, constraints, props = [], [], []
    for pred, obj in graph.predicate_objects(shape_iri):
        if pred == RDF.type:
            continue
        name = _local(pred)
        if name is None:
            continue
        if name in _TARGET_PREDS:
            targets.append((name, obj))
        elif name == "property":
            props.append(_load_property(graph, obj))
        elif name in _NODE_CONSTRAINTS:
            constraints.append(Constraint(kind=name, value=obj))
        else:
            raise UnsupportedShapeFeatureError(
                f"sh:{name} on a node shape is not supported"
            )
    return NodeShape(
        iri=shape_iri,
        targets=tuple(targets),
        constraints=tuple(constraints),
        property_shapes=tuple(props),
    )
