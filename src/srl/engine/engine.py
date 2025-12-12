"""
Main rule engine for SHACL 1.2 Rules.

Implements Section 5.5 of the specification: rule set evaluation
with stratification and fixpoint iteration.
"""

from typing import List, Set, Tuple

from rdflib import Graph

from .rules import eval_rule
from .solutions import substitute_triple_template
from .stratification import stratify_rules
from ..ast.nodes import RuleSet, Rule


class RuleEngine:
    """
    SHACL 1.2 Rules evaluation engine.
    
    Evaluates a rule set against an RDF graph using:
    1. Stratification: organize rules into evaluation layers
    2. Fixpoint iteration: within each stratum, apply rules until no new triples
    3. Head instantiation: generate new triples from rule heads
    """
    
    def __init__(self, rule_set: RuleSet, max_iterations: int = 1000):
        """
        Initialize the rule engine.
        
        Args:
            rule_set: Set of rules to evaluate
            max_iterations: Maximum iterations per stratum (prevents infinite loops)
        """
        self.rule_set = rule_set
        self.max_iterations = max_iterations
        self.strata: List[List[int]] = []
        
    def stratify(self) -> None:
        """
        Stratify the rule set.
        
        Must be called before evaluation.
        
        Raises:
            StratificationError: If rules have circular dependency through negation
        """
        self.strata = stratify_rules(self.rule_set)
    
    def evaluate(self, graph: Graph, inplace: bool = True, results_only: bool = False) -> Graph:
        """
        Evaluate the rule set against a graph.
        
        From Section 5.5:
        "Rule set evaluation proceeds stratum by stratum. Within each stratum,
        rules are applied repeatedly until a fixpoint is reached (no new triples
        are generated). The new triples generated in one stratum become input
        to the next stratum."
        
        Algorithm:
        1. Stratify rules (if not already done)
        2. For each stratum (in order):
           a. Initialize delta graph (new triples from this iteration)
           b. Repeat until fixpoint:
              - For each rule in stratum:
                - Evaluate rule body against current graph
                - Instantiate rule head with solution mappings
                - Add new triples to delta graph
              - If delta graph is empty: fixpoint reached, proceed to next stratum
              - Otherwise: add delta triples to graph and repeat
        
        Args:
            graph: RDF graph to evaluate rules against
            inplace: If True, modify graph in place; if False, work on a copy
            results_only: If True, return only the resulting triples
            
        Returns:
            Graph with inferred triples added
            
        Raises:
            StratificationError: If stratification fails
        """
        if inplace and results_only:
            raise ValueError("If you set results_only=True then you must not also select inplace=True")

        # Stratify if not already done
        if not self.strata:
            self.stratify()

        result_graph = Graph()

        # Work on a copy if not inplace
        if inplace:
            result_graph = graph
        else:
            result_graph += graph

        # Evaluate each stratum in order
        for stratum_num, rule_indices in enumerate(self.strata):
            self._evaluate_stratum(stratum_num, rule_indices, result_graph)

        if results_only:
            return result_graph - graph
        else:
            return result_graph
    
    def _evaluate_stratum(
        self,
        stratum_num: int,
        rule_indices: List[int],
        graph: Graph
    ) -> None:
        """
        Evaluate a single stratum to fixpoint.
        
        Args:
            stratum_num: Stratum number (for logging/debugging)
            rule_indices: Indices of rules in this stratum
            graph: Graph to evaluate against and add inferred triples to
        """
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Delta graph: new triples generated in this iteration
            delta = Graph()
            
            # Apply each rule in the stratum
            for rule_idx in rule_indices:
                rule = self.rule_set.rules[rule_idx]
                new_triples = self._evaluate_single_rule(rule, graph)
                
                # Add new triples to delta
                for triple in new_triples:
                    # Only add if not already in graph
                    if triple not in graph:
                        delta.add(triple)
            
            # Check for fixpoint
            if len(delta) == 0:
                # No new triples generated - fixpoint reached
                break
            
            # Add delta triples to graph for next iteration
            for triple in delta:
                graph.add(triple)
        
        if iteration >= self.max_iterations:
            # Warn about potential non-termination
            import warnings
            warnings.warn(
                f"Stratum {stratum_num} did not reach fixpoint after "
                f"{self.max_iterations} iterations. Rules may not terminate."
            )
    
    def _evaluate_single_rule(
        self,
        rule: Rule,
        graph: Graph
    ) -> Set[Tuple]:
        """
        Evaluate a single rule and generate new triples.
        
        Args:
            rule: Rule to evaluate
            graph: Graph to evaluate against
            
        Returns:
            Set of new triples (subject, predicate, object)
        """
        # Evaluate rule body to get solution mappings
        solution_mappings = eval_rule(rule, graph)
        
        # Generate new triples by instantiating head templates
        new_triples = set()
        
        for mu in solution_mappings:
            for template in rule.head.templates:
                # Substitute template with solution mapping
                triple = substitute_triple_template(template, mu)
                
                if triple is not None:
                    new_triples.add(triple)
        
        return new_triples
    
    def evaluate_with_provenance(
        self,
        graph: Graph,
        inplace: bool = True
    ) -> Tuple[Graph, List[Tuple[Tuple, int, int]]]:
        """
        Evaluate rules and track provenance of inferred triples.
        
        Args:
            graph: RDF graph to evaluate against
            inplace: If True, modify graph in place
            
        Returns:
            Tuple of (result_graph, provenance_list)
            where provenance_list contains (triple, rule_index, stratum)
        """
        # Stratify if not already done
        if not self.strata:
            self.stratify()
        
        # Work on a copy if not inplace
        if not inplace:
            result_graph = Graph()
            for triple in graph:
                result_graph.add(triple)
            graph = result_graph
        
        provenance = []
        
        # Evaluate each stratum
        for stratum_num, rule_indices in enumerate(self.strata):
            iteration = 0
            
            while iteration < self.max_iterations:
                iteration += 1
                delta = Graph()
                delta_provenance = []
                
                # Apply each rule
                for rule_idx in rule_indices:
                    rule = self.rule_set.rules[rule_idx]
                    new_triples = self._evaluate_single_rule(rule, graph)
                    
                    for triple in new_triples:
                        if triple not in graph:
                            delta.add(triple)
                            delta_provenance.append((triple, rule_idx, stratum_num))
                
                # Check fixpoint
                if len(delta) == 0:
                    break
                
                # Add to graph and record provenance
                for triple in delta:
                    graph.add(triple)
                
                provenance.extend(delta_provenance)
            
            if iteration >= self.max_iterations:
                import warnings
                warnings.warn(
                    f"Stratum {stratum_num} did not reach fixpoint after "
                    f"{self.max_iterations} iterations."
                )
        
        return graph, provenance
    
    def get_stratum_info(self) -> List[List[int]]:
        """
        Get stratification information.
        
        Returns:
            List of strata, each containing rule indices
        """
        if not self.strata:
            self.stratify()
        
        return self.strata
    
    def get_rule_count(self) -> int:
        """Get total number of rules."""
        return len(self.rule_set.rules)
    
    def get_stratum_count(self) -> int:
        """Get number of strata."""
        if not self.strata:
            self.stratify()
        
        return len(self.strata)


def evaluate_rules(
    rule_set: RuleSet,
    graph: Graph,
    inplace: bool = True,
    max_iterations: int = 1000
) -> Graph:
    """
    Convenience function to evaluate a rule set.
    
    Args:
        rule_set: Rules to evaluate
        graph: RDF graph
        inplace: If True, modify graph in place
        max_iterations: Max iterations per stratum
        
    Returns:
        Graph with inferred triples
    """
    engine = RuleEngine(rule_set, max_iterations=max_iterations)
    return engine.evaluate(graph, inplace=inplace)
