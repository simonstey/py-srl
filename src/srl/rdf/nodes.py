"""
RDF node types (IRI, Literal, BlankNode).

Provides typed wrappers around rdflib node types.
"""

from typing import Union, Optional
from rdflib import URIRef, Literal as RDFLibLiteral, BNode


# Type alias for any RDF node
RDFNode = Union[URIRef, RDFLibLiteral, BNode]


class IRINode:
    """
    Wrapper for IRI/URI nodes.
    """
    
    def __init__(self, iri: str):
        """
        Create IRI node.
        
        Args:
            iri: IRI string
        """
        self.value = URIRef(iri)
    
    def __str__(self) -> str:
        return f"<{self.value}>"
    
    def __repr__(self) -> str:
        return f"IRINode({self.value})"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, IRINode):
            return self.value == other.value
        return self.value == other
    
    def __hash__(self) -> int:
        return hash(self.value)


class LiteralNode:
    """
    Wrapper for literal nodes.
    """
    
    def __init__(
        self,
        value: str,
        datatype: Optional[str] = None,
        language: Optional[str] = None
    ):
        """
        Create literal node.
        
        Args:
            value: Literal value string
            datatype: Optional datatype IRI
            language: Optional language tag
        """
        if datatype:
            self.value = RDFLibLiteral(value, datatype=URIRef(datatype))
        elif language:
            self.value = RDFLibLiteral(value, lang=language)
        else:
            self.value = RDFLibLiteral(value)
    
    def __str__(self) -> str:
        return str(self.value)
    
    def __repr__(self) -> str:
        return f"LiteralNode({self.value})"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, LiteralNode):
            return self.value == other.value
        return self.value == other
    
    def __hash__(self) -> int:
        return hash(self.value)


class BlankNode:
    """
    Wrapper for blank nodes.
    """
    
    def __init__(self, identifier: Optional[str] = None):
        """
        Create blank node.
        
        Args:
            identifier: Optional blank node identifier
        """
        self.value = BNode(identifier) if identifier else BNode()
    
    def __str__(self) -> str:
        return f"_:{self.value}"
    
    def __repr__(self) -> str:
        return f"BlankNode({self.value})"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, BlankNode):
            return self.value == other.value
        return self.value == other
    
    def __hash__(self) -> int:
        return hash(self.value)
