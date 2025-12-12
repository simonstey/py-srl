"""
Stratification algorithm for SHACL 1.2 Rules.

Implements Section 5.4 of the specification: stratifying a rule set
to determine evaluation order and detect problematic negation cycles.
"""

from dataclasses import dataclass
from typing import List, Set, Tuple

from ..ast.nodes import (
    Rule, RuleSet, Variable,
    TriplePattern, NegationElement,
)


@dataclass
class StrataInfo:
    """Information about a rule's stratum."""
    rule_index: int
    stratum: int
    depends_on: Set[int]  # Indices of rules this rule depends on
    negatively_depends_on: Set[int]  # Indices with negation dependency


class StratificationError(Exception):
    """Error during stratification (e.g., cycle through negation)."""
    pass


def stratify_rules(rule_set: RuleSet) -> List[List[int]]:
    """
    Stratify a rule set into evaluation layers.
    
    From Section 5.4:
    "Stratification organizes rules into strata (layers) such that:
    1. Rules in lower strata are evaluated before rules in higher strata
    2. A rule in stratum i may depend on rules in strata j where j < i
    3. A rule may NOT depend negatively (through NOT) on a rule in the
       same or higher stratum (this would cause a cycle)"
    
    Algorithm:
    1. Build dependency graph: for each rule, identify which rules it depends on
       - Positive dependency: head of rule B matches body pattern of rule A
       - Negative dependency: head of rule B matches negated pattern in rule A
    2. Detect cycles through negation (error condition)
    3. Assign stratum levels using topological sort with negation constraints
    
    Args:
        rule_set: Set of rules to stratify
        
    Returns:
        List of strata, where each stratum is a list of rule indices
        
    Raises:
        StratificationError: If rules have circular dependency through negation
    """
    rules = rule_set.rules
    n = len(rules)
    
    if n == 0:
        return []
    
    # Build dependency graph
    dependencies = compute_dependencies(rules)
    
    # Detect cycles through negation
    detect_negation_cycles(dependencies)
    
    # Assign strata using topological sort
    strata = assign_strata(dependencies, n)
    
    return strata


def compute_dependencies(rules: List[Rule]) -> List[StrataInfo]:
    """
    Compute dependency relationships between rules.
    
    A rule R1 depends on rule R2 if:
    - The head of R2 could produce triples that match a body pattern in R1
    
    A rule R1 negatively depends on rule R2 if:
    - The head of R2 could produce triples that match a negated pattern in R1
    
    Args:
        rules: List of rules
        
    Returns:
        List of StrataInfo, one per rule
    """
    n = len(rules)
    dependencies = []
    
    for i, rule in enumerate(rules):
        depends_on = set()
        neg_depends_on = set()
        
        # Extract predicates from rule head (what this rule produces)
        head_predicates = extract_head_predicates(rule)
        
        # Check dependencies with other rules
        for j, other_rule in enumerate(rules):
            if i == j:
                continue
            
            # Check if other_rule's head could match our body patterns
            other_head_preds = extract_head_predicates(other_rule)
            
            # Positive dependencies: body patterns
            body_preds = extract_body_predicates(rule, negated=False)
            if predicates_overlap(other_head_preds, body_preds):
                depends_on.add(j)
            
            # Negative dependencies: negated patterns
            neg_body_preds = extract_body_predicates(rule, negated=True)
            if predicates_overlap(other_head_preds, neg_body_preds):
                neg_depends_on.add(j)
        
        info = StrataInfo(
            rule_index=i,
            stratum=-1,  # Will be assigned later
            depends_on=depends_on,
            negatively_depends_on=neg_depends_on
        )
        dependencies.append(info)
    
    return dependencies


def extract_head_predicates(rule: Rule) -> Set[str]:
    """
    Extract predicates from rule head templates.
    
    Returns set of predicate URIs or '*' for variables.
    """
    predicates = set()
    
    for template in rule.head.templates:
        if hasattr(template, 'predicate'):
            pred = template.predicate
            if isinstance(pred, Variable):
                predicates.add('*')  # Variable predicate - matches anything
            else:
                from ..ast.nodes import IRI
                if isinstance(pred, IRI):
                    predicates.add(pred.value)
    
    return predicates


def extract_body_predicates(rule: Rule, negated: bool = False) -> Set[str]:
    """
    Extract predicates from rule body patterns.
    
    Args:
        rule: Rule to analyze
        negated: If True, extract from negated patterns; else from positive patterns
        
    Returns:
        Set of predicate URIs or '*' for variables
    """
    predicates = set()
    
    def process_pattern(pattern):
        """Helper to extract predicate from a pattern."""
        if isinstance(pattern, TriplePattern):
            pred = pattern.predicate
            if isinstance(pred, Variable):
                predicates.add('*')
            else:
                from ..ast.nodes import IRI
                if isinstance(pred, IRI):
                    predicates.add(pred.value)
    
    for element in rule.body.elements:
        if negated:
            # Extract from negation elements
            if isinstance(element, NegationElement):
                for neg_pattern in element.body_patterns:
                    process_pattern(neg_pattern)
        else:
            # Extract from positive patterns
            if isinstance(element, TriplePattern):
                process_pattern(element)
    
    return predicates


def predicates_overlap(preds1: Set[str], preds2: Set[str]) -> bool:
    """
    Check if two predicate sets could overlap.
    
    They overlap if:
    - They share a common IRI
    - Either contains '*' (variable predicate)
    """
    if '*' in preds1 or '*' in preds2:
        return True
    
    return len(preds1 & preds2) > 0


def detect_negation_cycles(dependencies: List[StrataInfo]) -> None:
    """
    Detect cycles through negation in the dependency graph.
    
    From Section 5.4:
    "A stratification error occurs if there exists a cycle in the dependency
    graph that includes at least one negative edge."
    
    Uses depth-first search to detect cycles.
    
    Args:
        dependencies: Dependency information for all rules
        
    Raises:
        StratificationError: If a cycle through negation is detected
    """
    n = len(dependencies)
    
    # States: 0 = unvisited, 1 = visiting, 2 = visited
    state = [0] * n
    
    def dfs(node: int, path: List[int], neg_edges: Set[Tuple[int, int]]) -> None:
        """
        DFS to detect cycles with negation.
        
        Args:
            node: Current rule index
            path: Current path of rule indices
            neg_edges: Set of negative edges (i, j) encountered in current path
        """
        state[node] = 1  # Mark as visiting
        path.append(node)
        
        info = dependencies[node]
        
        # Check positive dependencies
        for neighbor in info.depends_on:
            if state[neighbor] == 1:
                # Found cycle - check if it includes a negative edge
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:]
                
                # Check if cycle includes any negative edge
                for i in range(len(cycle)):
                    curr = cycle[i]
                    next_node = cycle[(i + 1) % len(cycle)]
                    if (curr, next_node) in neg_edges:
                        # Cycle through negation!
                        raise StratificationError(
                            f"Cycle through negation detected: {' -> '.join(map(str, cycle + [neighbor]))}"
                        )
            elif state[neighbor] == 0:
                dfs(neighbor, path, neg_edges)
        
        # Check negative dependencies
        for neighbor in info.negatively_depends_on:
            neg_edges_with_current = neg_edges | {(node, neighbor)}
            
            if state[neighbor] == 1:
                # Found cycle with negative edge
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:]
                raise StratificationError(
                    f"Cycle through negation detected: {' -> '.join(map(str, cycle + [neighbor]))} (negative edge)"
                )
            elif state[neighbor] == 0:
                dfs(neighbor, path, neg_edges_with_current)
        
        path.pop()
        state[node] = 2  # Mark as visited
    
    # Run DFS from each unvisited node
    for i in range(n):
        if state[i] == 0:
            dfs(i, [], set())


def assign_strata(dependencies: List[StrataInfo], n: int) -> List[List[int]]:
    """
    Assign stratum levels to rules using topological sort.
    
    Rules are assigned to the lowest stratum possible while respecting:
    1. A rule must be in a higher stratum than all rules it depends on
    2. A rule must be in a higher stratum than all rules it negatively depends on
    
    Args:
        dependencies: Dependency information
        n: Number of rules
        
    Returns:
        List of strata, each containing rule indices
    """
    # Initialize all rules to stratum 0
    stratum = [0] * n
    
    # Iteratively increase stratum until all constraints satisfied
    changed = True
    max_iterations = n + 1  # Prevent infinite loop
    iteration = 0
    
    while changed and iteration < max_iterations:
        changed = False
        iteration += 1
        
        for i in range(n):
            info = dependencies[i]
            current_stratum = stratum[i]
            
            # Find maximum stratum of dependencies
            max_dep_stratum = -1
            
            # Positive dependencies: must be in higher stratum
            for dep in info.depends_on:
                max_dep_stratum = max(max_dep_stratum, stratum[dep])
            
            # Negative dependencies: must be in strictly higher stratum
            for dep in info.negatively_depends_on:
                max_dep_stratum = max(max_dep_stratum, stratum[dep])
            
            # Assign to next stratum after dependencies
            required_stratum = max_dep_stratum + 1 if max_dep_stratum >= 0 else 0
            
            if required_stratum > current_stratum:
                stratum[i] = required_stratum
                changed = True
    
    # Group rules by stratum
    max_stratum = max(stratum) if stratum else 0
    strata: List[List[int]] = [[] for _ in range(max_stratum + 1)]
    
    for i, s in enumerate(stratum):
        strata[s].append(i)
        # Update dependencies info
        dependencies[i].stratum = s
    
    return strata


def get_rule_stratum(rule_index: int, strata: List[List[int]]) -> int:
    """
    Get the stratum number for a specific rule.
    
    Args:
        rule_index: Index of the rule
        strata: Stratification result
        
    Returns:
        Stratum number (0-indexed)
    """
    for stratum_num, rule_indices in enumerate(strata):
        if rule_index in rule_indices:
            return stratum_num
    
    return -1  # Not found
