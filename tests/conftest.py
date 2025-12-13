"""
Test configuration and fixtures for py-srl.
"""

import pytest

from src.srl.rdf import RDFGraph


@pytest.fixture
def empty_graph():
    """Provide an empty RDF graph."""
    return RDFGraph()


@pytest.fixture
def sample_graph():
    """Provide a sample RDF graph with test data."""
    graph = RDFGraph()
    # TODO: Add sample triples once RDFGraph is fully implemented
    return graph
