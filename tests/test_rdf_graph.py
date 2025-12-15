"""
Unit tests for RDF graph wrapper.
"""

from srl.rdf import RDFGraph


def test_create_empty_graph():
    """Test creating an empty RDF graph."""
    graph = RDFGraph()
    assert len(graph) == 0


def test_graph_size(empty_graph):
    """Test graph size calculation."""
    assert empty_graph.size() == 0


# TODO: Add more tests as implementation progresses
