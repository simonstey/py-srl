"""
Namespace management for RDF graphs.

Handles prefix declarations and IRI expansion/abbreviation.
"""

from typing import Dict, Optional
from rdflib import Namespace as RDFLibNamespace


class NamespaceManager:
    """
    Manages prefix-to-namespace mappings for RDF graphs.
    
    This class provides:
    - Prefix registration
    - IRI expansion from prefixed names
    - IRI abbreviation to prefixed names
    """
    
    def __init__(self):
        """Initialize with common prefixes."""
        self._prefixes: Dict[str, str] = {}
        self._namespaces: Dict[str, RDFLibNamespace] = {}
        
        # Register common prefixes
        self.register("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        self.register("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
        self.register("xsd", "http://www.w3.org/2001/XMLSchema#")
        self.register("sh", "http://www.w3.org/ns/shacl#")
    
    def register(self, prefix: str, namespace: str) -> None:
        """
        Register a prefix-to-namespace mapping.
        
        Args:
            prefix: Prefix string (without colon)
            namespace: Full namespace IRI
        """
        self._prefixes[prefix] = namespace
        self._namespaces[prefix] = RDFLibNamespace(namespace)
    
    def expand(self, prefixed_name: str) -> Optional[str]:
        """
        Expand a prefixed name to full IRI.
        
        Args:
            prefixed_name: Prefixed name (e.g., "ex:Person")
        
        Returns:
            Full IRI or None if prefix not found
        """
        if ":" not in prefixed_name:
            return None
        
        prefix, local_name = prefixed_name.split(":", 1)
        
        if prefix in self._prefixes:
            return self._prefixes[prefix] + local_name
        
        return None
    
    def abbreviate(self, iri: str) -> Optional[str]:
        """
        Abbreviate a full IRI to prefixed name.
        
        Args:
            iri: Full IRI
        
        Returns:
            Prefixed name or None if no matching prefix
        """
        for prefix, namespace in self._prefixes.items():
            if iri.startswith(namespace):
                local_name = iri[len(namespace):]
                return f"{prefix}:{local_name}"
        
        return None
    
    def get_namespace(self, prefix: str) -> Optional[RDFLibNamespace]:
        """
        Get rdflib Namespace object for prefix.
        
        Args:
            prefix: Prefix string
        
        Returns:
            rdflib Namespace or None
        """
        return self._namespaces.get(prefix)
