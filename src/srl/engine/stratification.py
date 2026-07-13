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
from typing import Dict, List, Set, Tuple

from ..ast.nodes import (
    Rule,
    RuleSet,
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
    """A stratification layer: disjoint sets of run-once and general rules."""

    once: List[int] = field(default_factory=list)
    general: List[int] = field(default_factory=list)

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


def stratify(rule_set: RuleSet) -> List[StratificationLayer]:
    """
    Stratify a rule set into an ordered sequence of (once, general) layers.

    Raises:
        StratificationError: if the stratification condition is violated.
    """
    rules = rule_set.rules
    n = len(rules)
    if n == 0:
        return []

    edges = build_dependency_graph(rules)
    check_stratification_condition(rules, edges)
    stratum = _assign_stratum_numbers(n, edges)

    max_stratum = max(stratum)
    layers = [StratificationLayer() for _ in range(max_stratum + 1)]
    for i, s in enumerate(stratum):
        rule = rules[i]
        rule.layer = s
        if rule.is_run_once():
            layers[s].once.append(i)
        else:
            layers[s].general.append(i)

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
