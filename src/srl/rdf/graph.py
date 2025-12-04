"""
RDF Graph wrapper using rdflib.

Provides a high-level interface for RDF graph operations
needed by the SRL evaluation engine.
"""

from typing import Any, Optional, Iterator, Tuple
from rdflib import Graph as RDFLibGraph


class RDFGraph:
    """
    Wrapper around rdflib Graph with SRL-specific functionality.

    This class provides methods for:
    - Loading/saving RDF data
    - Querying triples
    - Adding/removing triples
    - SPARQL query execution
    """

    def __init__(self, graph: Optional[RDFLibGraph] = None):
        """
        Initialize RDF graph.

        Args:
            graph: Optional rdflib Graph to wrap. Creates new if None.
        """
        self._graph = graph if graph is not None else RDFLibGraph()

    @classmethod
    def load(cls, filename: str, format: str = "turtle") -> "RDFGraph":
        """
        Load RDF graph from file.

        Args:
            filename: Path to RDF file
            format: RDF format (turtle, xml, nt, json-ld, etc.)

        Returns:
            New RDFGraph instance with loaded data
        """
        graph = RDFLibGraph()
        graph.parse(filename, format=format)
        return cls(graph)

    def save(self, filename: str, format: str = "turtle") -> None:
        """
        Save RDF graph to file.

        Args:
            filename: Output file path
            format: RDF format (turtle, xml, nt, json-ld, etc.)
        """
        self._graph.serialize(destination=filename, format=format)

    def add(self, triple: Tuple) -> None:
        """
        Add a triple to the graph.

        Args:
            triple: (subject, predicate, object) tuple
        """
        self._graph.add(triple)

    def remove(self, triple: Tuple) -> None:
        """
        Remove a triple from the graph.

        Args:
            triple: (subject, predicate, object) tuple
        """
        self._graph.remove(triple)

    def __contains__(self, triple: Tuple) -> bool:
        """
        Check if triple is in graph.

        Args:
            triple: (subject, predicate, object) tuple

        Returns:
            True if triple exists in graph
        """
        return triple in self._graph

    def triples(self, pattern: Tuple[Optional[Any], Optional[Any], Optional[Any]]) -> Iterator[Tuple]:
        """
        Query triples matching pattern.

        Args:
            pattern: Triple pattern with None as wildcards

        Returns:
            Iterator of matching triples
        """
        return self._graph.triples(pattern)

    def size(self) -> int:
        """
        Get number of triples in graph.

        Returns:
            Number of triples
        """
        return len(self._graph)

    def copy(self) -> "RDFGraph":
        """
        Create a copy of this graph.

        Returns:
            New RDFGraph with same triples
        """
        new_graph = RDFLibGraph()
        for triple in self._graph:
            new_graph.add(triple)
        return RDFGraph(new_graph)

    def __len__(self) -> int:
        """Get number of triples."""
        return len(self._graph)

    def __iter__(self):
        """Iterate over triples."""
        return iter(self._graph)
