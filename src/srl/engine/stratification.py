"""
Dependency graph and stratification for SHACL 1.2 Rules.

Implements spec sections #rule-dependency, #dependency-graph,
#dependency-graph-construction-algorithm, #stratification,
#stratification-condition, and #stratification-algorithm.

The dependency graph has one vertex per rule and edges labeled "open" or
"closed". A dependency of R1 on R2 is *closed* if:
  (a) a triple pattern inside a negation element of R1 matches R2's head; or
  (b) R1 depends on R2 and R1 has an assignment element; or
  (c) R1 depends on R2 and R1's head contains a blank node.
Otherwise it is *open*.

Stratification partitions the rules into layers; each layer is a pair
(once, general) where run-once rules (assignment element or blank node in the
head) are evaluated once and general rules to fixpoint. The stratification
condition forbids any recursive dependency involving a closed dependency.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS

from ..ast.nodes import (
    Rule,
    RuleSet,
    TargetedRule,
    Variable,
    IRI,
    Literal,
    BlankNode,
    TripleTerm,
    TriplePattern,
    TripleTemplate,
    NegationElement,
    InversePath,
    PathSequence,
)

OPEN = "open"
CLOSED = "closed"


class StratificationError(Exception):
    """Raised when a rule set violates the stratification condition."""

    pass


@dataclass
class StratificationLayer:
    """A stratification layer: disjoint sets of run-once and general rules.

    ``targeted`` holds indices into ``RuleSet.targeted_rules`` for the opt-in
    rule-to-shape targeting extension; it is empty on the spec-conformant path.
    """

    once: List[int] = field(default_factory=list)
    general: List[int] = field(default_factory=list)
    targeted: List[int] = field(default_factory=list)

    def all_indices(self) -> List[int]:
        return self.once + self.general


# ---------------------------------------------------------------------------
# "Possibly match" between a triple pattern and a triple template
# ---------------------------------------------------------------------------


def _path_predicate_iris(path) -> Set[str]:
    """IRIs that a property path could traverse (for matching purposes)."""
    if isinstance(path, IRI):
        return {path.value}
    if isinstance(path, InversePath):
        return _path_predicate_iris(path.path)
    if isinstance(path, PathSequence):
        iris: Set[str] = set()
        for e in path.elements:
            iris |= _path_predicate_iris(e)
        return iris
    return set()


def _terms_can_match(pat_term, tmpl_term) -> bool:
    """
    A template term can possibly generate a pattern term if either is a
    variable, or both are the same RDF term (RDF term equality).
    """
    if isinstance(pat_term, Variable) or isinstance(tmpl_term, Variable):
        return True
    # Property path in the pattern predicate position: compare via its IRIs.
    if isinstance(pat_term, (InversePath, PathSequence)):
        iris = _path_predicate_iris(pat_term)
        if isinstance(tmpl_term, IRI):
            return tmpl_term.value in iris
        return True  # variable/other template predicate could match
    if isinstance(pat_term, TripleTerm) and isinstance(tmpl_term, TripleTerm):
        return (
            _terms_can_match(pat_term.subject, tmpl_term.subject)
            and _terms_can_match(pat_term.predicate, tmpl_term.predicate)
            and _terms_can_match(pat_term.object, tmpl_term.object)
        )
    if isinstance(pat_term, TripleTerm) != isinstance(tmpl_term, TripleTerm):
        return False
    return pat_term == tmpl_term


def _pattern_positions(pattern: TriplePattern):
    return (pattern.subject, pattern.predicate, pattern.object)


def _template_positions(template: TripleTemplate):
    return (template.subject, template.predicate, template.object)


def possibly_matches(pattern: TriplePattern, template: TripleTemplate) -> bool:
    """
    True if the triple template could possibly generate a triple matching the
    triple pattern. All three positions must be compatible, and if any pair of
    template positions are the same variable, the corresponding pattern
    positions must be equal (the repeated-variable constraint).
    """
    p_pos = _pattern_positions(pattern)
    t_pos = _template_positions(template)

    for pp, tp in zip(p_pos, t_pos):
        if not _terms_can_match(pp, tp):
            return False

    # Repeated-variable constraint on the template side: if two template
    # positions carry the same variable, the corresponding pattern positions
    # must be the same RDF term (or share a variable).
    for i in range(3):
        for j in range(i + 1, 3):
            if isinstance(t_pos[i], Variable) and t_pos[i] == t_pos[j]:
                a, b = p_pos[i], p_pos[j]
                if isinstance(a, Variable) or isinstance(b, Variable):
                    continue
                if a != b:
                    return False
    return True


def pattern_depends_on_rule(pattern: TriplePattern, rule: Rule) -> bool:
    """A triple pattern depends on a rule if it could match any head template."""
    return any(possibly_matches(pattern, t) for t in rule.head.templates)


# ---------------------------------------------------------------------------
# Rule-to-shape targeting gate (opt-in extension, not part of the SRL spec)
# ---------------------------------------------------------------------------


def shape_referenced_predicates(shape) -> Set[str]:
    """Predicate IRIs a shape reads when selecting/validating its focus nodes.

    Covers the shape's targets (``targetClass``/``class`` read ``rdf:type``;
    ``targetSubjectsOf``/``targetObjectsOf`` read their predicate) and the
    predicate IRIs of every property shape's (simple) path plus its value-type
    ``class`` constraints. Complex (non-``URIRef``) property paths are skipped
    best-effort. Used to place a targeted rule strictly above any rule whose
    head could change the shape's conformance verdict.
    """
    preds: Set[str] = set()

    def _add_class_read() -> None:
        preds.add(str(RDF.type))

    for name, obj in shape.targets:
        if name == "targetClass":
            _add_class_read()
        elif name in ("targetSubjectsOf", "targetObjectsOf"):
            if isinstance(obj, URIRef):
                preds.add(str(obj))

    for c in shape.constraints:
        if c.kind == "class":
            _add_class_read()

    for ps in shape.property_shapes:
        if isinstance(ps.path, URIRef):
            preds.add(str(ps.path))
        for c in ps.constraints:
            if c.kind == "class":
                _add_class_read()

    return preds


def _head_predicate_iris(rule: Rule) -> Tuple[Set[str], bool]:
    """Return (IRI predicate strings a rule's head can assert, has_variable_pred).

    A variable in a head predicate position is a wildcard: it could assert any
    predicate, so callers must treat it as matching any referenced predicate.
    """
    iris: Set[str] = set()
    has_var = False
    for t in rule.head.templates:
        pred = t.predicate
        if isinstance(pred, IRI):
            iris.add(pred.value)
        elif isinstance(pred, Variable):
            has_var = True
    return iris, has_var


# ---------------------------------------------------------------------------
# Dependency graph construction  (#dependency-graph-construction-algorithm)
# ---------------------------------------------------------------------------


def _merge_label(old: str, new: str) -> str:
    """Closed dependency overrides open dependency."""
    if old == OPEN and new == OPEN:
        return OPEN
    return CLOSED


def _body_pattern_dependencies(rule: Rule) -> List[Tuple[TriplePattern, str]]:
    """
    Classify each body triple pattern of a rule as requiring an "open" or
    "closed" dependency: patterns inside a negation element are "closed",
    plain triple-pattern elements are "open".
    """
    deps: List[Tuple[TriplePattern, str]] = []
    for element in rule.body.elements:
        if isinstance(element, NegationElement):
            for pat in element.body_patterns:
                if isinstance(pat, TriplePattern):
                    deps.append((pat, CLOSED))
        elif isinstance(element, TriplePattern):
            deps.append((element, OPEN))
    return deps


def build_dependency_graph(rules: List[Rule]) -> Dict[Tuple[int, int], str]:
    """
    Build the dependency graph as a map (R1_index, R2_index) -> label.
    Implements the buildDependencyGraph algorithm.
    """
    edge_labels: Dict[Tuple[int, int], str] = {}

    for i, r1 in enumerate(rules):
        body_deps = _body_pattern_dependencies(r1)

        # A rule with an assignment element, or a blank node in its head,
        # forces every one of its dependencies to be closed.
        force_closed = r1.has_assignment() or r1.head_has_blank_node()

        for pattern, dep_label in body_deps:
            label = CLOSED if force_closed else dep_label
            for j, r2 in enumerate(rules):
                if pattern_depends_on_rule(pattern, r2):
                    key = (i, j)
                    if key in edge_labels:
                        edge_labels[key] = _merge_label(edge_labels[key], label)
                    else:
                        edge_labels[key] = label

    return edge_labels


# ---------------------------------------------------------------------------
# Stratification condition  (#stratification-condition)
# ---------------------------------------------------------------------------


def _has_recursive_closed_dependency(
    n: int, edges: Dict[Tuple[int, int], str]
) -> bool:
    """
    True if some cycle in the dependency graph involves a closed edge, i.e.
    there is a recursive dependency involving a closed dependency.
    """
    # Build adjacency for reachability.
    adj: Dict[int, List[int]] = {i: [] for i in range(n)}
    for (a, b) in edges:
        adj[a].append(b)

    # Precompute reachability (transitive closure) via DFS from each node.
    def reachable_from(src: int) -> Set[int]:
        seen: Set[int] = set()
        stack = [src]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return seen

    reach = {i: reachable_from(i) for i in range(n)}

    # A closed edge (a -> b) lies on a cycle iff a is reachable from b.
    for (a, b), label in edges.items():
        if label == CLOSED and a in reach[b]:
            return True
    return False


def check_stratification_condition(
    rules: List[Rule], edges: Dict[Tuple[int, int], str]
) -> None:
    """Raise StratificationError if the stratification condition is violated."""
    if _has_recursive_closed_dependency(len(rules), edges):
        raise StratificationError(
            "Stratification condition violated: a recursive dependency involves "
            "a closed dependency (negation, assignment, or blank-node head in a cycle)."
        )


# ---------------------------------------------------------------------------
# Stratification algorithm  (#stratification-algorithm)
# ---------------------------------------------------------------------------


def _assign_stratum_numbers(
    n: int, edges: Dict[Tuple[int, int], str]
) -> List[int]:
    """
    Assign a stratum number to each rule:
      * open edge  p -> q : stratum(p) >= stratum(q)
      * closed edge p -> q : stratum(p) >  stratum(q)
    Iterate to a fixpoint. The limit guard catches an unbounded stratification
    (a violation of the stratification condition that escaped earlier checks).
    """
    stratum = [0] * n
    limit = n + 1

    changed = True
    while changed:
        changed = False
        for (p, q), label in edges.items():
            if label == OPEN:
                if stratum[p] < stratum[q]:
                    stratum[p] = stratum[q]
                    changed = True
            else:  # CLOSED
                if stratum[p] <= stratum[q]:
                    new_stratum = stratum[q] + 1
                    if new_stratum > limit:
                        raise StratificationError(
                            "Stratification error: unbounded stratification "
                            "(stratification condition violated)."
                        )
                    stratum[p] = new_stratum
                    changed = True

    return stratum


def _add_edge(edges: Dict[Tuple[int, int], str], key: Tuple[int, int], label: str) -> None:
    """Add/merge an edge label into the edge map (closed overrides open)."""
    if key in edges:
        edges[key] = _merge_label(edges[key], label)
    else:
        edges[key] = label


def _build_combined_edges(
    rules: List[Rule],
    targeted_rules: List["TargetedRule"],
    shapes_graph: Optional[Graph],
) -> Dict[Tuple[int, int], str]:
    """Build the dependency graph over plain rules (0..n-1) and targeted rules
    (vertex ``n + t`` for ``targeted_rules[t]``), for the opt-in targeting
    extension.

    Adds, on top of the plain-rule dependency graph:
      * body-pattern dependencies of/onto targeted rules (open/closed as usual);
      * a **closed** *gate* edge from each targeted rule to any rule (plain or
        targeted) whose head could assert a predicate the targeted rule's shape
        reads — so the targeted rule lands strictly above rules that can change
        its shape's conformance verdict.
    """
    n = len(rules)
    m = len(targeted_rules)
    edges = build_dependency_graph(rules)

    # (vertex_id, wrapped Rule) for every vertex, plain and targeted.
    all_vertices: List[Tuple[int, Rule]] = [(i, rules[i]) for i in range(n)]
    all_vertices += [(n + t, targeted_rules[t].rule) for t in range(m)]

    def _add_body_deps(src_vertex: int, src_rule: Rule) -> None:
        body_deps = _body_pattern_dependencies(src_rule)
        force_closed = src_rule.has_assignment() or src_rule.head_has_blank_node()
        for pattern, dep_label in body_deps:
            label = CLOSED if force_closed else dep_label
            for vj, rj in all_vertices:
                if vj == src_vertex:
                    continue
                if pattern_depends_on_rule(pattern, rj):
                    _add_edge(edges, (src_vertex, vj), label)

    # Targeted rules' bodies may depend on any (plain or targeted) head.
    for t in range(m):
        _add_body_deps(n + t, targeted_rules[t].rule)

    # Plain rules' bodies may depend on targeted-rule heads (not covered by the
    # plain-only build_dependency_graph call above).
    for i in range(n):
        r1 = rules[i]
        body_deps = _body_pattern_dependencies(r1)
        force_closed = r1.has_assignment() or r1.head_has_blank_node()
        for pattern, dep_label in body_deps:
            label = CLOSED if force_closed else dep_label
            for t in range(m):
                if pattern_depends_on_rule(pattern, targeted_rules[t].rule):
                    _add_edge(edges, (i, n + t), label)

    # Gate: a targeted rule depends (closed) on any rule whose head can assert a
    # predicate its shape reads.
    if shapes_graph is not None:
        from ..shapes import load_shape

        for t in range(m):
            tr = targeted_rules[t]
            shape = load_shape(shapes_graph, URIRef(tr.shape.value))
            refs = shape_referenced_predicates(shape)
            if not refs:
                continue
            for vj, rj in all_vertices:
                if vj == n + t:
                    continue
                iris, has_var = _head_predicate_iris(rj)
                if has_var or (iris & refs):
                    _add_edge(edges, (n + t, vj), CLOSED)

    return edges


def stratify(
    rule_set: RuleSet, shapes_graph: Optional[Graph] = None
) -> List[StratificationLayer]:
    """
    Stratify a rule set into an ordered sequence of (once, general[, targeted])
    layers.

    Args:
        rule_set: the rule set to stratify.
        shapes_graph: shapes graph for the opt-in rule-to-shape targeting
            extension. When ``rule_set.targeted_rules`` is non-empty and a
            shapes graph is given, targeted rules are placed in strata as
            closed-dependency gate vertices; otherwise targeting is ignored.

    Raises:
        StratificationError: if the stratification condition is violated.
    """
    rules = rule_set.rules
    targeted_rules = rule_set.targeted_rules
    n = len(rules)
    m = len(targeted_rules)

    if n == 0 and m == 0:
        return []

    if m == 0:
        edges = build_dependency_graph(rules)
    else:
        edges = _build_combined_edges(rules, targeted_rules, shapes_graph)

    total = n + m
    if _has_recursive_closed_dependency(total, edges):
        raise StratificationError(
            "Stratification condition violated: a recursive dependency involves "
            "a closed dependency (negation, assignment, blank-node head, or a "
            "shape-targeting gate in a cycle)."
        )
    stratum = _assign_stratum_numbers(total, edges)

    max_stratum = max(stratum) if stratum else 0
    layers = [StratificationLayer() for _ in range(max_stratum + 1)]
    for i in range(n):
        s = stratum[i]
        rule = rules[i]
        rule.layer = s
        if rule.is_run_once():
            layers[s].once.append(i)
        else:
            layers[s].general.append(i)
    for t in range(m):
        s = stratum[n + t]
        targeted_rules[t].layer = s
        layers[s].targeted.append(t)

    return layers


# ---------------------------------------------------------------------------
# Backwards-compatible helper: flat list of rule-index layers.
# ---------------------------------------------------------------------------


def stratify_rules(rule_set: RuleSet) -> List[List[int]]:
    """
    Stratify a rule set, returning a flat list of rule-index layers (each layer
    is once-rules followed by general-rules). Prefer :func:`stratify` when the
    once/general distinction is needed.
    """
    return [layer.all_indices() for layer in stratify(rule_set)]
