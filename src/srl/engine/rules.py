"""
Single rule evaluation for SHACL 1.2 Rules.

Implements Section 5.3 of the specification: evaluating a single rule
to produce solution mappings from the rule body.
"""

from typing import List, Optional

from rdflib import Graph

from .expressions import eval_expr, effective_boolean_value
from .solutions import (
    SolutionMapping, graphMatch, join, minus, extend
)
from ..ast.nodes import (
    Rule, RuleBody, RuleBodyElement,
    TriplePattern, ConditionExpression, NegationElement, Assignment,
)


def eval_rule(
    rule: Rule,
    graph: Graph,
    active_graph: Optional[Graph] = None,
    seed: Optional[SolutionMapping] = None,
) -> List[SolutionMapping]:
    """
    Evaluate a rule body to produce solution mappings.

    From Section 5.3:
    "The evaluation of a rule body produces a set of solution mappings.
    Each solution mapping represents a way to instantiate the variables
    in the rule body such that the body pattern matches the data graph."

    Algorithm:
    1. Start with a single empty solution mapping Ω = {μ₀} where μ₀ = {}
    2. For each element in the body pattern:
       - Triple patterns: Join with graphMatch results
       - Filters: Remove mappings that don't satisfy the condition
       - Negation (NOT): Remove mappings compatible with negation results
       - Assignments (SET): Extend mappings with new variable bindings
    3. Return final set of solution mappings

    Args:
        rule: Rule to evaluate
        graph: RDF graph to evaluate against
        active_graph: Optional active graph for dataset queries
        seed: Optional pre-bound solution mapping. When given, Ω starts as
            ``[seed]`` instead of the empty mapping (used by the opt-in
            rule-to-shape targeting extension to pre-bind a focus variable).

    Returns:
        List of solution mappings satisfying the rule body
    """
    # Start with the seed mapping if provided, else a single empty mapping.
    omega: List[SolutionMapping] = (
        [seed] if seed is not None else [SolutionMapping(bindings={})]
    )

    # Process each body element in sequence
    for element in rule.body.elements:
        omega = eval_body_element(element, omega, graph, active_graph)
        
        # Early termination if no solutions remain
        if not omega:
            break
    
    return omega


def eval_body_element(
    element: RuleBodyElement,
    omega: List[SolutionMapping],
    graph: Graph,
    active_graph: Optional[Graph] = None
) -> List[SolutionMapping]:
    """
    Evaluate a single body element against current solution mappings.
    
    Args:
        element: Body element (triple pattern, filter, negation, or assignment)
        omega: Current set of solution mappings
        graph: RDF graph
        active_graph: Optional active graph
        
    Returns:
        Updated set of solution mappings
    """
    if isinstance(element, TriplePattern):
        return eval_triple_pattern(element, omega, graph, active_graph)
    
    elif isinstance(element, ConditionExpression):
        return eval_filter(element, omega, graph, active_graph)
    
    elif isinstance(element, NegationElement):
        return eval_negation(element, omega, graph, active_graph)
    
    elif isinstance(element, Assignment):
        return eval_assignment(element, omega, graph, active_graph)
    
    else:
        # Unknown element type - skip it
        return omega


def eval_triple_pattern(
    pattern: TriplePattern,
    omega: List[SolutionMapping],
    graph: Graph,
    active_graph: Optional[Graph] = None
) -> List[SolutionMapping]:
    """
    Evaluate a triple pattern by joining with graph matches.
    
    From Section 5.3:
    "For a triple pattern tp, the evaluation joins the current solution
    mappings with the results of graphMatch(G, tp)."
    
    Algorithm: Ω' = join(Ω, graphMatch(G, tp))
    
    Args:
        pattern: Triple pattern to match
        omega: Current solution mappings
        graph: RDF graph
        active_graph: Optional active graph
        
    Returns:
        Joined solution mappings
    """
    # Get all matches for this triple pattern
    matches = graphMatch(graph, pattern, active_graph)
    
    # Join with current solution mappings
    result = join(omega, matches)
    
    return result


def eval_filter(
    filter_expr: ConditionExpression,
    omega: List[SolutionMapping],
    graph: Graph,
    active_graph: Optional[Graph] = None
) -> List[SolutionMapping]:
    """
    Evaluate a FILTER by removing solution mappings that don't satisfy it.

    From #eval-rule (condition element):
    "for each solution μ in SEQ: let x = evalFunction(F, μ);
     if EBV(x) is true: add μ to SEQ1."

    Algorithm: Ω' = { μ ∈ Ω | EBV(eval(expr, μ, G)) = true }

    Args:
        filter_expr: Filter condition expression
        omega: Current solution mappings
        graph: the evaluation graph G
        active_graph: Optional active graph (defaults to G)

    Returns:
        Filtered solution mappings
    """
    # The spec evaluates expressions against the evaluation graph G; thread it
    # through so graph-dependent forms can consult it.
    eval_graph = active_graph if active_graph is not None else graph
    result = []

    for mu in omega:
        # Evaluate the filter expression
        value = eval_expr(filter_expr.expression, mu, eval_graph)

        # Keep mapping if effective boolean value is true
        if effective_boolean_value(value):
            result.append(mu)

    return result


def eval_negation(
    negation: NegationElement,
    omega: List[SolutionMapping],
    graph: Graph,
    active_graph: Optional[Graph] = None
) -> List[SolutionMapping]:
    """
    Evaluate a negation (NOT {...}) by removing compatible mappings.
    
    From Section 5.3:
    "For a negation NOT { P }, solution mappings μ are retained if they
    are not compatible with any solution mapping from evaluating P."
    
    Algorithm:
    1. Evaluate the negated pattern P to get Ω₂
    2. Return minus(Ω, Ω₂)
    
    Args:
        negation: Negation element with body patterns
        omega: Current solution mappings
        graph: RDF graph
        active_graph: Optional active graph
        
    Returns:
        Solution mappings after negation
    """
    # Per #eval-rule: for each μ, seed the negation body with the single
    # solution {μ} and evaluate it; keep μ iff that yields NO solutions.
    # This is a per-μ empty-check, not a global set-minus.
    result = []

    for mu in omega:
        omega_neg = [mu]
        for pattern in negation.body_patterns:
            omega_neg = eval_body_element(pattern, omega_neg, graph, active_graph)
            if not omega_neg:
                break
        if not omega_neg:
            result.append(mu)

    return result


def eval_assignment(
    assignment: Assignment,
    omega: List[SolutionMapping],
    graph: Graph,
    active_graph: Optional[Graph] = None
) -> List[SolutionMapping]:
    """
    Evaluate an assignment (SET) by extending mappings with a new variable.

    From #eval-rule (assignment element):
    "for each μ: x = evalFunction(expr, μ); if x is not an error, add
    μ ∪ {(V, x)}; else drop μ."

    Algorithm: Ω' = { extend(μ, var, eval(expr, μ, G)) | μ ∈ Ω, eval not error }
    
    Args:
        assignment: Assignment with expression and variable
        omega: Current solution mappings
        graph: RDF graph
        active_graph: Optional active graph
        
    Returns:
        Extended solution mappings
    """
    # Expressions are evaluated against the evaluation graph G.
    eval_graph = active_graph if active_graph is not None else graph
    result = []

    for mu in omega:
        # Evaluate the expression.
        value = eval_expr(assignment.expression, mu, eval_graph)

        # Per #eval-rule: on an error, drop the solution μ; otherwise add
        # μ ∪ {(V, x)}. Well-formedness guarantees V is not already bound.
        if value is None:
            continue

        extended = extend(mu, assignment.variable, value)
        result.append(extended)

    return result


def eval_rule_body(
    body: RuleBody,
    graph: Graph,
    active_graph: Optional[Graph] = None
) -> List[SolutionMapping]:
    """
    Evaluate a rule body (convenience wrapper).
    
    Args:
        body: Rule body to evaluate
        graph: RDF graph
        active_graph: Optional active graph
        
    Returns:
        Solution mappings from body evaluation
    """
    # Create a temporary rule for evaluation
    from ..ast.nodes import Rule, RuleHead
    temp_rule = Rule(
        head=RuleHead(templates=[]),
        body=body
    )
    
    return eval_rule(temp_rule, graph, active_graph)
