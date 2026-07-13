"""Focus-node selection for the opt-in rule-to-shape targeting extension.

This is NOT part of the SRL spec. It computes the set of focus nodes a shape's
targets select over a data graph, covering the SHACL target kinds parsed by
:mod:`srl.shapes.model`:

* ``sh:targetClass`` — instances of the class or any transitive subclass.
* ``sh:targetNode`` — the named node itself.
* ``sh:targetSubjectsOf`` — subjects of triples with the given predicate.
* ``sh:targetObjectsOf`` — objects of triples with the given predicate.
* ``sh:targetWhere`` — data nodes conforming to the referenced (inline) shape.
* ``sh:shape`` — data-graph subjects ``n`` with ``n sh:shape <shapeIri>``.
"""

from typing import Set, cast

from rdflib import Graph
from rdflib.namespace import RDF, RDFS
from rdflib.term import Node

from .model import SH, NodeShape, load_shape
from .validate import conforms


def _subclass_instances(cls: Node, graph: Graph) -> Set[Node]:
    """All nodes typed as ``cls`` or any transitive ``rdfs:subClassOf`` of it."""
    classes: Set[Node] = set()
    frontier = [cls]
    while frontier:
        cur = frontier.pop()
        if cur in classes:
            continue
        classes.add(cur)
        for sub in graph.subjects(RDFS.subClassOf, cur):
            frontier.append(sub)
    instances: Set[Node] = set()
    for c in classes:
        instances.update(graph.subjects(RDF.type, c))
    return instances


def _data_nodes(graph: Graph) -> Set[Node]:
    """Candidate focus nodes for a shape-based target: all data-graph subjects/objects."""
    nodes: Set[Node] = set()
    for s, _p, o in graph:
        nodes.add(s)
        nodes.add(o)
    return nodes


def focus_nodes(shape: NodeShape, data_graph: Graph, shapes_graph: Graph) -> Set[Node]:
    """Return the union of focus nodes selected by ``shape``'s targets."""
    result: Set[Node] = set()
    for name, obj in shape.targets:
        if name == "targetClass":
            result |= _subclass_instances(obj, data_graph)
        elif name == "targetNode":
            result.add(obj)
        elif name == "targetSubjectsOf":
            result |= set(data_graph.subjects(obj, None))
        elif name == "targetObjectsOf":
            result |= set(data_graph.objects(None, obj))
        elif name == "targetWhere":
            inline = load_shape(shapes_graph, obj)
            for candidate in _data_nodes(data_graph):
                if conforms(candidate, inline, data_graph, shapes_graph):
                    result.add(candidate)
    # ``sh:shape`` is an implicit target: any data node ``n`` with
    # ``n sh:shape <shapeIri>`` is a focus node of that shape.
    result |= set(data_graph.subjects(SH.shape, cast(Node, shape.iri)))
    return result
