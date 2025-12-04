"""
Solution mapping operations for SHACL 1.2 Rules.

Implements Section 5.1 of the specification: solution mappings,
substitution, compatibility, merging, and graph matching.
"""

from typing import Dict, Set, List, Optional, Union
from dataclasses import dataclass, field
from rdflib import Graph, URIRef, Literal as RDFLiteral, BNode

from ..ast.nodes import (
    Variable,
    IRI,
    Literal,
    BlankNode,
    TriplePattern,
    TripleTemplate,
    InversePath,
    PathSequence,
    PathAlternative,
)


# Type aliases for RDF terms
RDFTerm = Union[URIRef, RDFLiteral, BNode]


@dataclass(frozen=True)
class SolutionMapping:
    """
    A solution mapping μ: V → T where V is a set of variables
    and T is the set of RDF terms.

    From Section 5.1:
    "A solution mapping μ is a partial function from variables to RDF terms."
    """

    bindings: Dict[str, RDFTerm] = field(default_factory=dict)

    def __getitem__(self, var: Union[str, Variable]) -> Optional[RDFTerm]:
        """Get the binding for a variable."""
        var_name = var.name if isinstance(var, Variable) else var
        return self.bindings.get(var_name)

    def __contains__(self, var: Union[str, Variable]) -> bool:
        """Check if a variable has a binding."""
        var_name = var.name if isinstance(var, Variable) else var
        return var_name in self.bindings

    def domain(self) -> Set[str]:
        """Return the domain of the mapping (set of bound variables)."""
        return set(self.bindings.keys())

    def is_defined_for(self, var: Union[str, Variable]) -> bool:
        """Check if the mapping is defined for a variable."""
        return var in self

    def __repr__(self) -> str:
        items = [f"{k}: {v}" for k, v in self.bindings.items()]
        return "{" + ", ".join(items) + "}"


def compatible(mu1: SolutionMapping, mu2: SolutionMapping) -> bool:
    """
    Check if two solution mappings are compatible.

    From Section 5.1:
    "Two solution mappings μ₁ and μ₂ are compatible if for every variable v
    in dom(μ₁) ∩ dom(μ₂), it holds that μ₁(v) = μ₂(v)."

    Args:
        mu1: First solution mapping
        mu2: Second solution mapping

    Returns:
        True if mappings are compatible, False otherwise
    """
    common_vars = mu1.domain() & mu2.domain()

    for var in common_vars:
        if mu1[var] != mu2[var]:
            return False

    return True


def merge(mu1: SolutionMapping, mu2: SolutionMapping) -> Optional[SolutionMapping]:
    """
    Merge two compatible solution mappings.

    From Section 5.1:
    "If μ₁ and μ₂ are compatible, then μ₁ ∪ μ₂ is a solution mapping whose
    domain is dom(μ₁) ∪ dom(μ₂) and μ₁ ∪ μ₂(v) = μ₁(v) if v ∈ dom(μ₁),
    otherwise μ₁ ∪ μ₂(v) = μ₂(v)."

    Args:
        mu1: First solution mapping
        mu2: Second solution mapping

    Returns:
        Merged solution mapping if compatible, None otherwise
    """
    if not compatible(mu1, mu2):
        return None

    merged_bindings = {**mu1.bindings, **mu2.bindings}
    return SolutionMapping(bindings=merged_bindings)


def substitute_term(term: Union[Variable, IRI, Literal, BlankNode], mu: SolutionMapping) -> RDFTerm:
    """
    Apply substitution function μ̂ to an RDF term.

    From Section 5.1:
    "For a solution mapping μ, the substitution function μ̂ is defined as:
    - μ̂(v) = μ(v) if v is a variable and v ∈ dom(μ)
    - μ̂(t) = t otherwise"

    Args:
        term: Variable, IRI, Literal, or BlankNode
        mu: Solution mapping

    Returns:
        Substituted RDF term
    """
    if isinstance(term, Variable):
        if term.name in mu:
            return mu[term.name]
        else:
            # Variable not bound - in evaluation context this is typically an error
            raise ValueError(f"Variable {term.name} not bound in solution mapping")
    elif isinstance(term, IRI):
        return URIRef(term.value)
    elif isinstance(term, Literal):
        if term.datatype:
            dt = URIRef(term.datatype.value) if isinstance(term.datatype, IRI) else None
            return RDFLiteral(term.value, datatype=dt)
        elif term.language:
            return RDFLiteral(term.value, lang=term.language)
        else:
            return RDFLiteral(term.value)
    elif isinstance(term, BlankNode):
        return BNode(term.label) if term.label else BNode()
    elif isinstance(term, (InversePath, PathSequence, PathAlternative)):
        # Property paths are handled specially in graph matching, not substitution
        # Return as-is for path evaluation
        return term
    else:
        raise TypeError(f"Unknown term type: {type(term)}")


def substitute_term_safe(term: Union[Variable, IRI, Literal, BlankNode], mu: SolutionMapping) -> Optional[RDFTerm]:
    """
    Apply substitution with graceful handling of unbound variables.

    Returns None if a variable is not bound, rather than raising an error.
    """
    try:
        return substitute_term(term, mu)
    except ValueError:
        return None


def graphMatch(graph: Graph, pattern: TriplePattern, active_graph: Optional[Graph] = None) -> List[SolutionMapping]:
    """
    Find all solution mappings that match a triple pattern against a graph.

    From Section 5.1:
    "graphMatch(G, tp) returns the set of all solution mappings μ such that
    μ̂(tp) is a triple in G, where tp is a triple pattern."

    Args:
        graph: RDF graph to match against
        pattern: Triple pattern to match
        active_graph: Optional active graph for dataset queries

    Returns:
        List of solution mappings
    """
    solutions: List[SolutionMapping] = []

    # Convert pattern terms to RDF nodes or keep as variables
    def pattern_term(term):
        """Convert AST term to RDF term or None (for variables)."""
        if isinstance(term, Variable):
            return None  # Will match any term
        elif isinstance(term, IRI):
            return URIRef(term.value)
        elif isinstance(term, Literal):
            if term.datatype:
                dt = URIRef(term.datatype.value) if isinstance(term.datatype, IRI) else None
                return RDFLiteral(term.value, datatype=dt)
            elif term.language:
                return RDFLiteral(term.value, lang=term.language)
            else:
                return RDFLiteral(term.value)
        elif isinstance(term, BlankNode):
            return BNode(term.label) if term.label else BNode()
        elif isinstance(term, (InversePath, PathSequence, PathAlternative)):
            # Property paths need special evaluation
            return term
        else:
            raise TypeError(f"Unknown term type: {type(term)}")

    subj = pattern_term(pattern.subject)
    pred = pattern_term(pattern.predicate)
    obj = pattern_term(pattern.object)

    # Check if predicate is a property path
    if isinstance(pred, (InversePath, PathSequence, PathAlternative)):
        return graphMatchWithPath(graph, pattern.subject, pred, pattern.object, active_graph)

    # Query the graph
    target_graph = active_graph if active_graph is not None else graph

    for s, p, o in target_graph.triples((subj, pred, obj)):
        bindings = {}

        # Bind subject if it's a variable
        if isinstance(pattern.subject, Variable):
            bindings[pattern.subject.name] = s

        # Bind predicate if it's a variable
        if isinstance(pattern.predicate, Variable):
            bindings[pattern.predicate.name] = p

        # Bind object if it's a variable
        if isinstance(pattern.object, Variable):
            bindings[pattern.object.name] = o

        solutions.append(SolutionMapping(bindings=bindings))

    return solutions


def graphMatchWithPath(
    graph: Graph, subject_pattern, path, object_pattern, active_graph: Optional[Graph] = None
) -> List[SolutionMapping]:
    """
    Match a triple pattern with a property path predicate.

    Property paths allow matching patterns like:
    - ex:parent/ex:parent (sequence - grandparent)
    - ^ex:hasChild (inverse - parent)
    - ex:knows|ex:friendOf (alternative)

    Args:
        graph: RDF graph to match against
        subject_pattern: Subject term or variable
        path: Property path (InversePath, PathSequence, PathAlternative)
        object_pattern: Object term or variable
        active_graph: Optional active graph for dataset queries

    Returns:
        List of solution mappings
    """
    target_graph = active_graph if active_graph is not None else graph
    solutions: List[SolutionMapping] = []

    # Get all (start, end) pairs that satisfy the path
    path_results = evaluate_path(target_graph, path)

    for start_node, end_node in path_results:
        bindings = {}

        # Check if subject matches
        if isinstance(subject_pattern, Variable):
            bindings[subject_pattern.name] = start_node
        else:
            # Subject is a constant - check if it matches
            subj_term = _ast_to_rdf(subject_pattern)
            if subj_term != start_node:
                continue

        # Check if object matches
        if isinstance(object_pattern, Variable):
            bindings[object_pattern.name] = end_node
        else:
            # Object is a constant - check if it matches
            obj_term = _ast_to_rdf(object_pattern)
            if obj_term != end_node:
                continue

        solutions.append(SolutionMapping(bindings=bindings))

    return solutions


def _ast_to_rdf(term) -> Optional[RDFTerm]:
    """Convert AST term to RDF term."""
    if isinstance(term, IRI):
        return URIRef(term.value)
    elif isinstance(term, Literal):
        if term.datatype:
            dt = URIRef(term.datatype.value) if isinstance(term.datatype, IRI) else None
            return RDFLiteral(term.value, datatype=dt)
        elif term.language:
            return RDFLiteral(term.value, lang=term.language)
        else:
            return RDFLiteral(term.value)
    elif isinstance(term, BlankNode):
        return BNode(term.label) if term.label else BNode()
    return None


def evaluate_path(graph: Graph, path) -> Set[tuple]:
    """
    Evaluate a property path and return all (start, end) pairs.

    Args:
        graph: RDF graph
        path: Property path to evaluate

    Returns:
        Set of (start_node, end_node) pairs that satisfy the path
    """
    if isinstance(path, IRI):
        # Simple predicate path
        pred = URIRef(path.value)
        return {(s, o) for s, p, o in graph.triples((None, pred, None))}

    elif isinstance(path, InversePath):
        # Inverse path: ^p means follow p backwards
        inner_results = evaluate_path(graph, path.path)
        return {(end, start) for start, end in inner_results}

    elif isinstance(path, PathSequence):
        # Sequence path: p1/p2 means follow p1 then p2
        if not path.elements:
            return set()

        # Start with first path element
        current_results = evaluate_path(graph, path.elements[0])

        # Chain through remaining elements
        for element in path.elements[1:]:
            next_step = evaluate_path(graph, element)
            # Join: for each (a, b) in current and (b, c) in next_step, produce (a, c)
            new_results = set()
            next_step_dict = {}
            for start, end in next_step:
                if start not in next_step_dict:
                    next_step_dict[start] = []
                next_step_dict[start].append(end)

            for start, mid in current_results:
                if mid in next_step_dict:
                    for end in next_step_dict[mid]:
                        new_results.add((start, end))

            current_results = new_results

        return current_results

    elif isinstance(path, PathAlternative):
        # Alternative path: p1|p2 means either p1 or p2
        results = set()
        for alt in path.alternatives:
            results |= evaluate_path(graph, alt)
        return results

    else:
        raise TypeError(f"Unknown path type: {type(path)}")


def substitute_triple_template(
    template: TripleTemplate, mu: SolutionMapping
) -> Optional[tuple[RDFTerm, RDFTerm, RDFTerm]]:
    """
    Apply substitution to a triple template.

    Returns a concrete RDF triple if all terms can be substituted,
    None if any variable is unbound.

    Args:
        template: Triple template from rule head
        mu: Solution mapping

    Returns:
        Tuple of (subject, predicate, object) RDF terms, or None
    """
    try:
        subj = substitute_term(template.subject, mu)
        pred = substitute_term(template.predicate, mu)
        obj = substitute_term(template.object, mu)
        return (subj, pred, obj)
    except ValueError:
        # Variable not bound
        return None


def join(omega1: List[SolutionMapping], omega2: List[SolutionMapping]) -> List[SolutionMapping]:
    """
    Join two sets of solution mappings.

    From SPARQL semantics:
    "Join(Ω₁, Ω₂) = { μ₁ ∪ μ₂ | μ₁ ∈ Ω₁, μ₂ ∈ Ω₂, and μ₁ and μ₂ are compatible }"

    Args:
        omega1: First set of solution mappings
        omega2: Second set of solution mappings

    Returns:
        List of joined solution mappings
    """
    result = []

    for mu1 in omega1:
        for mu2 in omega2:
            merged = merge(mu1, mu2)
            if merged is not None:
                result.append(merged)

    return result


def minus(omega1: List[SolutionMapping], omega2: List[SolutionMapping]) -> List[SolutionMapping]:
    """
    Set difference for solution mappings (for NOT EXISTS / negation).

    From SPARQL semantics:
    "Minus(Ω₁, Ω₂) = { μ ∈ Ω₁ | for all μ' ∈ Ω₂, μ and μ' are not compatible }"

    Args:
        omega1: First set of solution mappings
        omega2: Second set of solution mappings

    Returns:
        List of solution mappings from omega1 not compatible with any in omega2
    """
    result = []

    for mu1 in omega1:
        # Check if mu1 is compatible with any mapping in omega2
        is_compatible_with_any = False
        for mu2 in omega2:
            if compatible(mu1, mu2):
                is_compatible_with_any = True
                break

        # Only include if NOT compatible with any
        if not is_compatible_with_any:
            result.append(mu1)

    return result


def extend(mu: SolutionMapping, var: Variable, value: RDFTerm) -> SolutionMapping:
    """
    Extend a solution mapping with a new variable binding.

    Used for BIND operations in rule bodies.

    Args:
        mu: Existing solution mapping
        var: Variable to bind
        value: RDF term to bind to variable

    Returns:
        New solution mapping with additional binding
    """
    new_bindings = {**mu.bindings, var.name: value}
    return SolutionMapping(bindings=new_bindings)
