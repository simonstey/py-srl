"""
Main rule engine for SHACL 1.2 Rules.

Implements spec section #rule-set-evaluation (Rule Set Evaluation):

  * Preparation: resolve imports and compute the stratification.
  * DATA blocks seed the evaluation graph GE = G0 ∪ D and the inference
    graph GI = { t ∈ D | t ∉ G0 }.
  * Each stratum is evaluated by first running its run-once rules exactly
    once, then iterating its general rules to a fixpoint.
  * The result is GI (inferred triples, excluding the base graph).
"""

import warnings
from typing import List, Optional, Set, Tuple

from rdflib import Graph, URIRef

from .rules import eval_rule
from .solutions import SolutionMapping, substitute_triple_template
from .stratification import StratificationLayer, stratify
from ..ast.nodes import RuleSet, Rule, IRI, TargetedRule


class ExtensionError(Exception):
    """Raised when a non-spec extension feature is used without opting in.

    Rule-to-shape targeting (``RuleSet.targeted_rules``) is an opt-in extension;
    evaluating a rule set containing targeted rules requires
    ``RuleEngine(..., extensions=True)`` and a ``shapes_graph``.
    """


class RuleEngine:
    """SHACL 1.2 Rules evaluation engine."""

    def __init__(
        self,
        rule_set: RuleSet,
        max_iterations: int = 1000,
        *,
        resolve_imports: bool = True,
        base_location: Optional[str] = None,
        import_loader=None,
        extensions: bool = False,
        shapes_graph: Optional[Graph] = None,
    ):
        """
        Args:
            rule_set: the rule set to evaluate.
            max_iterations: fixpoint iteration cap per stratum (safety guard).
            resolve_imports: if True and the rule set has imports, resolve them
                into a combined rule set before evaluation (#process-imports).
            base_location: location of the rule set (to avoid self-import).
            import_loader: optional callable mapping an import URL to SRL text.
            extensions: if True, enable the opt-in rule-to-shape targeting
                extension. When False (the spec-conformant default), a rule set
                containing targeted rules raises :class:`ExtensionError`.
            shapes_graph: the SHACL shapes graph used to resolve targeted rules'
                shapes (required when evaluating a rule set with targeted rules).
        """
        if resolve_imports and rule_set.prologue.imports:
            from .imports import resolve_imports as _resolve

            rule_set = _resolve(
                rule_set, base_location=base_location, loader=import_loader
            )
        self.rule_set = rule_set
        self.max_iterations = max_iterations
        self.extensions = extensions
        self.shapes_graph = shapes_graph
        self.layers: List[StratificationLayer] = []

        # Targeted rules are a non-spec, opt-in extension. Reject them on the
        # default (spec-conformant) path so behaviour stays byte-for-byte.
        if rule_set.targeted_rules and not extensions:
            raise ExtensionError(
                "Rule set contains targeted rules (rule-to-shape targeting), "
                "which is an opt-in extension. Construct the engine with "
                "extensions=True and a shapes_graph to evaluate them."
            )

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------

    def stratify(self) -> None:
        """Compute the stratification (once/general/targeted layers)."""
        shapes_graph = (
            self.shapes_graph
            if self.extensions and self.rule_set.targeted_rules
            else None
        )
        self.layers = stratify(self.rule_set, shapes_graph=shapes_graph)

    def _data_triples(self) -> Set[Tuple]:
        """Materialize all DATA-block triples of the rule set as RDF triples."""
        from .solutions import SolutionMapping, substitute_triple_template

        empty = SolutionMapping(bindings={})
        triples: Set[Tuple] = set()
        for block in self.rule_set.data_blocks:
            for template in block.triples:
                triple = substitute_triple_template(template, empty)
                if triple is not None:
                    triples.add(triple)
        return triples

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, graph: Graph, inplace: bool = True, results_only: bool = False) -> Graph:
        """
        Evaluate the rule set against a base graph.

        Args:
            graph: the base graph G0.
            inplace: if True, mutate ``graph`` to become the evaluation graph
                GE (= G0 ∪ D ∪ inferred); if False, work on a copy.
            results_only: if True, return only the inference graph GI (inferred
                triples plus DATA triples not already in G0), excluding the
                base graph. Cannot be combined with ``inplace``.

        Returns:
            GE (base + data + inferred) by default, or GI when results_only.
        """
        if inplace and results_only:
            raise ValueError("results_only=True requires inplace=False")

        if not self.layers:
            self.stratify()

        # Evaluation graph GE.
        if inplace:
            eval_graph = graph
        else:
            eval_graph = Graph()
            eval_graph += graph

        # Seed DATA triples: GE = G0 ∪ D, and remember which are inferred
        # (present in D but not in the base graph G0).
        data_triples = self._data_triples()
        inferred: Set[Tuple] = set()
        for t in data_triples:
            if t not in graph:
                inferred.add(t)
            eval_graph.add(t)

        # Evaluate each stratum in order.
        for stratum_num, layer in enumerate(self.layers):
            self._evaluate_layer(stratum_num, layer, eval_graph, inferred)

        if results_only:
            result = Graph()
            for t in inferred:
                result.add(t)
            return result
        return eval_graph

    def _evaluate_layer(
        self,
        stratum_num: int,
        layer: StratificationLayer,
        eval_graph: Graph,
        inferred: Set[Tuple],
    ) -> None:
        """Evaluate one stratum: run-once rules once, then general to fixpoint.

        Opt-in targeting extension: the layer's targeted rules are split the same
        way (run-once if the wrapped rule is run-once, else general) and folded
        into the same once-pass / fixpoint loop as the plain rules.
        """
        # Partition the layer's targeted rules into run-once and general.
        once_targeted: List[int] = []
        general_targeted: List[int] = []
        for t_idx in layer.targeted:
            tr = self.rule_set.targeted_rules[t_idx]
            (once_targeted if tr.rule.is_run_once() else general_targeted).append(t_idx)

        # Run-once rules: evaluated exactly once, in order.
        for rule_idx in layer.once:
            rule = self.rule_set.rules[rule_idx]
            for triple in self._evaluate_single_rule(rule, eval_graph):
                if triple not in eval_graph:
                    inferred.add(triple)
                    eval_graph.add(triple)

        # Run-once targeted rules: evaluated exactly once, in order.
        for t_idx in once_targeted:
            tr = self.rule_set.targeted_rules[t_idx]
            for triple in self._evaluate_single_targeted_rule(tr, eval_graph):
                if triple not in eval_graph:
                    inferred.add(triple)
                    eval_graph.add(triple)

        # General rules (plain + targeted): iterate to a fixpoint.
        if not layer.general and not general_targeted:
            return

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            delta: Set[Tuple] = set()
            for rule_idx in layer.general:
                rule = self.rule_set.rules[rule_idx]
                for triple in self._evaluate_single_rule(rule, eval_graph):
                    if triple not in eval_graph:
                        delta.add(triple)
            for t_idx in general_targeted:
                tr = self.rule_set.targeted_rules[t_idx]
                for triple in self._evaluate_single_targeted_rule(tr, eval_graph):
                    if triple not in eval_graph:
                        delta.add(triple)
            if not delta:
                break
            for triple in delta:
                inferred.add(triple)
                eval_graph.add(triple)

        if iteration >= self.max_iterations:
            warnings.warn(
                f"Stratum {stratum_num} did not reach fixpoint after "
                f"{self.max_iterations} iterations. Rules may not terminate."
            )

    def _evaluate_single_rule(
        self, rule: Rule, graph: Graph, seed: Optional[SolutionMapping] = None
    ) -> Set[Tuple]:
        """Evaluate a rule body and instantiate its head, returning new triples.

        When ``seed`` is given, the rule body is evaluated with that solution
        mapping pre-bound (used by the rule-to-shape targeting extension to
        pre-bind a focus node to the focus variable).
        """
        solution_mappings = eval_rule(rule, graph, seed=seed)

        new_triples: Set[Tuple] = set()
        for mu in solution_mappings:
            # Fresh blank nodes per solution mapping: a head blank node is a new
            # node for each generated set of triples, shared across that rule
            # instantiation's head templates.
            bnode_map: dict = {}
            for template in rule.head.templates:
                triple = substitute_triple_template(template, mu, bnode_map)
                if triple is not None:
                    new_triples.add(triple)
        return new_triples

    # ------------------------------------------------------------------
    # Targeted rules (opt-in extension)
    # ------------------------------------------------------------------

    def _evaluate_single_targeted_rule(
        self, tr: TargetedRule, eval_graph: Graph
    ) -> Set[Tuple]:
        """Evaluate one rule-to-shape targeted rule against the current graph.

        Selects the shape's focus nodes, keeps those that conform to the shape,
        and evaluates the wrapped rule once per conforming focus node with the
        focus variable pre-bound to that node. Returns the inferred triples (the
        caller decides which are new).
        """
        if self.shapes_graph is None:
            raise ExtensionError(
                "Evaluating targeted rules requires a shapes_graph; construct "
                "the engine with RuleEngine(..., extensions=True, shapes_graph=...)."
            )

        from ..shapes import conforms, focus_nodes, load_shape

        shape = load_shape(self.shapes_graph, URIRef(tr.shape.value))
        candidates = focus_nodes(shape, eval_graph, self.shapes_graph)
        new_triples: Set[Tuple] = set()
        for node in candidates:
            if not conforms(node, shape, eval_graph, self.shapes_graph):
                continue
            seed = SolutionMapping(bindings={tr.focus_var.name: node})
            new_triples |= self._evaluate_single_rule(tr.rule, eval_graph, seed)
        return new_triples

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------

    def evaluate_with_provenance(
        self, graph: Graph, inplace: bool = True
    ) -> Tuple[Graph, List[Tuple[Tuple, int, int]]]:
        """
        Evaluate rules while recording which rule (index) in which stratum
        inferred each triple.

        Returns:
            (evaluation_graph, provenance) where provenance is a list of
            (triple, rule_index, stratum_number).
        """
        if not self.layers:
            self.stratify()

        if inplace:
            eval_graph = graph
        else:
            eval_graph = Graph()
            eval_graph += graph

        provenance: List[Tuple[Tuple, int, int]] = []

        # DATA triples have no originating rule; record them with rule index -1.
        for t in self._data_triples():
            if t not in eval_graph:
                eval_graph.add(t)
                provenance.append((t, -1, -1))

        for stratum_num, layer in enumerate(self.layers):
            # Run-once rules.
            for rule_idx in layer.once:
                rule = self.rule_set.rules[rule_idx]
                for triple in self._evaluate_single_rule(rule, eval_graph):
                    if triple not in eval_graph:
                        eval_graph.add(triple)
                        provenance.append((triple, rule_idx, stratum_num))

            # General rules to fixpoint.
            if not layer.general:
                continue
            iteration = 0
            while iteration < self.max_iterations:
                iteration += 1
                delta: List[Tuple[Tuple, int]] = []
                for rule_idx in layer.general:
                    rule = self.rule_set.rules[rule_idx]
                    for triple in self._evaluate_single_rule(rule, eval_graph):
                        if triple not in eval_graph:
                            delta.append((triple, rule_idx))
                if not delta:
                    break
                for triple, rule_idx in delta:
                    if triple not in eval_graph:
                        eval_graph.add(triple)
                        provenance.append((triple, rule_idx, stratum_num))

            if iteration >= self.max_iterations:
                warnings.warn(
                    f"Stratum {stratum_num} did not reach fixpoint after "
                    f"{self.max_iterations} iterations."
                )

        return eval_graph, provenance

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_stratum_info(self) -> List[List[int]]:
        """Return each stratum as a flat list of rule indices (once + general)."""
        if not self.layers:
            self.stratify()
        return [layer.all_indices() for layer in self.layers]

    def get_layers(self) -> List[StratificationLayer]:
        """Return the (once, general) stratification layers."""
        if not self.layers:
            self.stratify()
        return self.layers

    def get_rule_count(self) -> int:
        return len(self.rule_set.rules)

    def get_stratum_count(self) -> int:
        if not self.layers:
            self.stratify()
        return len(self.layers)


def evaluate_rules(
    rule_set: RuleSet,
    graph: Graph,
    inplace: bool = True,
    results_only: bool = False,
    max_iterations: int = 1000,
) -> Graph:
    """
    Convenience wrapper around :class:`RuleEngine`.

    With ``results_only=True`` (and ``inplace=False``) the returned graph is the
    inference graph GI (inferred triples excluding the base graph).
    """
    engine = RuleEngine(rule_set, max_iterations=max_iterations)
    return engine.evaluate(graph, inplace=inplace, results_only=results_only)
