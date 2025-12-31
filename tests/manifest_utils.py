"""
Utility functions for W3C manifest-based test suite.

Provides manifest parsing, graph comparison, and test case loading.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic, to_isomorphic


# Namespaces
MF = Namespace("http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#")
SRT = Namespace("http://www.w3.org/ns/shacl-rules-test#")
PYRL = Namespace("http://example.org/py-srl/test#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")


# Test type constants
TEST_TYPE_RULES_EVAL = SRT.RulesEvalTest
TEST_TYPE_POSITIVE_SYNTAX = SRT.RulesPositiveSyntaxTest
TEST_TYPE_NEGATIVE_SYNTAX = SRT.RulesNegativeSyntaxTest
TEST_TYPE_STRATIFICATION = PYRL.StratificationTest
TEST_TYPE_EVAL_ERROR = PYRL.EvaluationErrorTest

# Status constants
STATUS_APPROVED = SRT.approved
STATUS_XFAIL = PYRL.xfail
STATUS_SKIP = PYRL.skip


@dataclass
class ManifestTestCase:
    """Represents a single test case from a manifest."""
    
    uri: URIRef
    name: str
    test_type: URIRef
    description: Optional[str]
    status: Optional[URIRef]
    
    # For eval tests
    ruleset_path: Optional[Path]
    data_path: Optional[Path]
    result_path: Optional[Path]
    
    # For syntax tests
    action_path: Optional[Path]
    
    # Source manifest for debugging
    manifest_path: Path
    
    @property
    def is_xfail(self) -> bool:
        """Check if test is expected to fail."""
        return self.status == STATUS_XFAIL
    
    @property
    def is_skip(self) -> bool:
        """Check if test should be skipped."""
        return self.status == STATUS_SKIP
    
    @property
    def is_eval_test(self) -> bool:
        """Check if this is a rules evaluation test."""
        return self.test_type == TEST_TYPE_RULES_EVAL
    
    @property
    def is_positive_syntax_test(self) -> bool:
        """Check if this is a positive syntax test."""
        return self.test_type == TEST_TYPE_POSITIVE_SYNTAX
    
    @property
    def is_negative_syntax_test(self) -> bool:
        """Check if this is a negative syntax test."""
        return self.test_type == TEST_TYPE_NEGATIVE_SYNTAX
    
    @property
    def is_stratification_test(self) -> bool:
        """Check if this is a stratification error test."""
        return self.test_type == TEST_TYPE_STRATIFICATION


def load_manifest(manifest_path: Path) -> Graph:
    """
    Load a manifest file into an RDF graph.
    
    Args:
        manifest_path: Path to the manifest.ttl file
        
    Returns:
        RDF graph containing manifest data
    """
    g = Graph()
    g.parse(str(manifest_path), format="turtle")
    return g


def get_manifest_includes(graph: Graph, manifest_uri: URIRef) -> List[URIRef]:
    """
    Get the list of included manifests.
    
    Args:
        graph: Manifest graph
        manifest_uri: URI of the manifest node
        
    Returns:
        List of included manifest URIs
    """
    includes = []
    
    # Get the mf:include value (should be an RDF list)
    include_list = graph.value(manifest_uri, MF.include)
    if include_list is None:
        return includes
    
    # Parse RDF list
    from rdflib.collection import Collection
    try:
        includes = list(Collection(graph, include_list))
    except Exception:
        pass
    
    return includes


def resolve_path(base_path: Path, ref: Union[URIRef, str]) -> Path:
    """
    Resolve a relative URI reference to an absolute path.
    
    Args:
        base_path: Base path (manifest directory)
        ref: URI reference (relative or absolute)
        
    Returns:
        Resolved absolute path
    """
    ref_str = str(ref)
    
    # Remove file:// scheme if present
    if ref_str.startswith("file://"):
        ref_str = ref_str[7:]
    
    # Handle relative paths
    if not ref_str.startswith("/"):
        return base_path / ref_str
    
    return Path(ref_str)


def parse_test_case(graph: Graph, test_uri: URIRef, manifest_path: Path) -> ManifestTestCase:
    """
    Parse a single test case from the manifest graph.
    
    Args:
        graph: Manifest graph
        test_uri: URI of the test node
        manifest_path: Path to the manifest file (for resolving relative URIs)
        
    Returns:
        TestCase object
    """
    base_dir = manifest_path.parent
    
    # Get test type
    test_type = graph.value(test_uri, RDF.type)
    
    # Get name and description
    name = str(graph.value(test_uri, MF.name) or test_uri.split("#")[-1].split("/")[-1])
    description = graph.value(test_uri, RDFS.comment)
    if description:
        description = str(description)
    
    # Get status
    status = graph.value(test_uri, MF.status)
    
    # Initialize paths
    ruleset_path = None
    data_path = None
    result_path = None
    action_path = None
    
    # Get action
    action = graph.value(test_uri, MF.action)
    
    if action:
        if isinstance(action, BNode):
            # Action is a blank node with srt:ruleset and srt:data
            ruleset_ref = graph.value(action, SRT.ruleset)
            data_ref = graph.value(action, SRT.data)
            
            if ruleset_ref:
                ruleset_path = resolve_path(base_dir, ruleset_ref)
            if data_ref:
                data_path = resolve_path(base_dir, data_ref)
        else:
            # Action is a direct file reference (for syntax tests)
            action_path = resolve_path(base_dir, action)
    
    # Get result
    result_ref = graph.value(test_uri, MF.result)
    if result_ref:
        result_path = resolve_path(base_dir, result_ref)
    
    return ManifestTestCase(
        uri=test_uri,
        name=name,
        test_type=test_type,
        description=description,
        status=status,
        ruleset_path=ruleset_path,
        data_path=data_path,
        result_path=result_path,
        action_path=action_path,
        manifest_path=manifest_path,
    )


def get_manifest_entries(graph: Graph, manifest_uri: URIRef) -> List[URIRef]:
    """
    Get the list of test entries from a manifest.
    
    Args:
        graph: Manifest graph
        manifest_uri: URI of the manifest node
        
    Returns:
        List of test entry URIs
    """
    entries = []
    
    # Get the mf:entries value (should be an RDF list)
    entries_list = graph.value(manifest_uri, MF.entries)
    if entries_list is None:
        return entries
    
    # Parse RDF list
    from rdflib.collection import Collection
    try:
        entries = list(Collection(graph, entries_list))
    except Exception:
        pass
    
    return entries


def load_tests_from_manifest(
    manifest_path: Path,
    visited: Optional[Set[Path]] = None
) -> Iterator[ManifestTestCase]:
    """
    Recursively load all test cases from a manifest and its includes.
    
    Args:
        manifest_path: Path to the manifest file
        visited: Set of already visited manifests (to avoid cycles)
        
    Yields:
        TestCase objects
    """
    if visited is None:
        visited = set()
    
    # Avoid cycles
    manifest_path = manifest_path.resolve()
    if manifest_path in visited:
        return
    visited.add(manifest_path)
    
    if not manifest_path.exists():
        return
    
    # Load manifest
    graph = load_manifest(manifest_path)
    
    # Find manifest node (usually <> which resolves to file URI)
    manifest_uri = URIRef(manifest_path.as_uri())
    
    # Try to find the manifest node
    for s in graph.subjects(RDF.type, MF.Manifest):
        manifest_uri = s
        break
    
    # Process includes first
    includes = get_manifest_includes(graph, manifest_uri)
    for include_uri in includes:
        include_path = resolve_path(manifest_path.parent, include_uri)
        yield from load_tests_from_manifest(include_path, visited)
    
    # Process entries
    entries = get_manifest_entries(graph, manifest_uri)
    for entry_uri in entries:
        yield parse_test_case(graph, entry_uri, manifest_path)


def compare_graphs(
    actual: Graph,
    expected: Graph,
    ignore_bnodes: bool = True
) -> Tuple[bool, str]:
    """
    Compare two RDF graphs for equivalence.
    
    Uses rdflib's isomorphic comparison for blank-node-aware matching.
    
    Args:
        actual: The actual/computed graph
        expected: The expected graph
        ignore_bnodes: If True, allow blank node remapping
        
    Returns:
        Tuple of (is_equal, diff_message)
    """
    if ignore_bnodes:
        # Use isomorphic comparison (handles blank node bijection)
        if isomorphic(actual, expected):
            return True, ""
        
        # Generate diff message
        actual_iso = to_isomorphic(actual)
        expected_iso = to_isomorphic(expected)
        
        # Find differences
        in_actual_only = actual_iso - expected_iso
        in_expected_only = expected_iso - actual_iso
        
        diff_parts = []
        
        if in_actual_only:
            diff_parts.append(f"In actual but not expected ({len(in_actual_only)} triples):")
            for triple in sorted(in_actual_only, key=str)[:10]:
                diff_parts.append(f"  + {triple}")
            if len(in_actual_only) > 10:
                diff_parts.append(f"  ... and {len(in_actual_only) - 10} more")
        
        if in_expected_only:
            diff_parts.append(f"In expected but not actual ({len(in_expected_only)} triples):")
            for triple in sorted(in_expected_only, key=str)[:10]:
                diff_parts.append(f"  - {triple}")
            if len(in_expected_only) > 10:
                diff_parts.append(f"  ... and {len(in_expected_only) - 10} more")
        
        return False, "\n".join(diff_parts)
    else:
        # Exact comparison (no blank node remapping)
        if set(actual) == set(expected):
            return True, ""
        
        in_actual_only = set(actual) - set(expected)
        in_expected_only = set(expected) - set(actual)
        
        diff_parts = []
        if in_actual_only:
            diff_parts.append(f"In actual but not expected: {len(in_actual_only)} triples")
        if in_expected_only:
            diff_parts.append(f"In expected but not actual: {len(in_expected_only)} triples")
        
        return False, "; ".join(diff_parts)


def compute_inferred_triples(result_graph: Graph, input_graph: Graph) -> Graph:
    """
    Compute the set of inferred triples (result minus input).
    
    Args:
        result_graph: Graph after rule evaluation
        input_graph: Original input graph
        
    Returns:
        Graph containing only inferred triples
    """
    inferred = Graph()
    
    # Copy namespace bindings
    for prefix, namespace in result_graph.namespaces():
        inferred.bind(prefix, namespace)
    
    for triple in result_graph:
        if triple not in input_graph:
            inferred.add(triple)
    
    return inferred
