# The `FOR ?v IN <shape>` clause

**Status:** opt-in extension to `shacl-rules` (py-srl), **not part of the W3C
[SHACL 1.2 Rules](https://www.w3.org/TR/shacl12-rules/) specification.**
This document does double duty: it explains how the clause works in this
implementation, and it is written to be lifted, more or less directly, into a
**proposal for adding rule-to-shape targeting to the SHACL 1.2 Rules spec**.

---

## 1. Overview

The SHACL 1.2 Rules spec defines rules that fire **globally**: a rule's body is
matched against the *whole* data/inference graph, with no notion of a target, a
focus node, or an attachment to a SHACL shape. `FOR ?v IN <shape>` re-introduces
targeting on top of that model. It ties a single rule to a SHACL **shape** so
the rule fires **only for the shape's target focus nodes that conform to the
shape**, with a user-named focus variable pre-bound to each such node.

It is an evolution of SHACL-AF's `sh:rule` + `$this` idea (see §4), refitted to
current SRL semantics (solution mappings, stratification, run-once/general
layers). It is **off by default** and reachable only behind the
`--extensions`/`-x` CLI flag (or `SRLParser(extensions=True)` /
`RuleEngine(..., extensions=True)`). With the flag off the parser rejects the
`FOR` clause and the engine raises `ExtensionError`, so a spec-conformant
document is byte-for-byte unaffected.

---

## 2. The clause in this implementation

### 2.1 Surface syntax

The clause is a **rule-level prefix**, sitting between the rule keyword (and its
optional IRI) and the head template. It is **not** a rule-body element — the
spec-pure body grammar (triple patterns, `FILTER`, `NOT`, `SET`) is untouched.

Both concrete rule forms accept it:

```sparql
# RULE ... WHERE form
RULE ex:r FOR ?this IN ex:AdultShape
  { ?this ex:status ex:adult }
WHERE
  { ?this ex:age ?a . FILTER(?a >= 18) }

# IF ... THEN form
IF   { ?this ex:age ?a }
THEN ex:r FOR ?this IN ex:AdultShape { ?this ex:status ex:adult }
```

- `?this` is the **focus variable** — author-chosen, any name. It is bound to
  each conforming focus node before the body runs, so it may appear in the body
  and the head.
- `ex:AdultShape` is a **shape IRI** resolved against a separately supplied SHACL
  shapes graph.

### 2.2 How it is reachable

| Surface | Gate |
| --- | --- |
| Text SRL | `SRLParser(extensions=True)`; CLI `--extensions`/`-x`, or always-on under `srl shacl` |
| SRL/RDF | `parse_rdf_rule_set(g, extensions=True)`, via `srl:targetShape` + `srl:focusVar` (rule→shape) or `sh:rule`/`srl:rule` (shape→rule) |

CLI:

```bash
srl shacl RULES_FILE DATA_FILE --shapes SHAPES_FILE [-o OUT] [-f rdf] [--format FMT]
```

### 2.3 Pipeline

| Stage | What happens | Where |
| --- | --- | --- |
| **Grammar** | Extension grammar redefines `rule1`/`rule2` to accept an optional `for_clause: "FOR"i var "IN"i iri`, spliced over the base grammar; the base `grammar.lark` is never modified. | `src/srl/parser/grammar-ext.lark:8-10`, `src/srl/parser/parser.py` |
| **Transform** | `for_clause` → `("for", Variable, IRI)`; `_wrap_targeted` builds the AST node. | `src/srl/parser/transformer.py:174-231` |
| **AST** | `TargetedRule(rule, focus_var, shape, direction)` **wraps** (does not subclass) a `Rule`, so all existing rule machinery runs on `.rule`. Targeted rules live in `RuleSet.targeted_rules`, kept separate from spec-pure `RuleSet.rules`. | `src/srl/ast/nodes.py:396-411`, `:497` |
| **Stratify** | Targeted rules become extra vertices; a **closed** gate edge is added from each to any rule whose head could change its shape's conformance verdict. | `src/srl/engine/stratification.py:416-540` |
| **Evaluate** | `load_shape` → `focus_nodes(shape)` → keep those that `conforms` → seed `focus_var → node` → run the wrapped rule once per conforming node. | `src/srl/engine/engine.py:254-280` |
| **Shapes** | In-house SHACL 1.2 Core subset used for targets + conformance. | `src/srl/shapes/` (`load_shape`, `focus_nodes`, `conforms`) |

The evaluation core is small — the seed is the whole trick:

```python
# src/srl/engine/engine.py:272-280
shape = load_shape(self.shapes_graph, URIRef(tr.shape.value))
candidates = focus_nodes(shape, eval_graph, self.shapes_graph)
new_triples: Set[Tuple] = set()
for node in candidates:
    if not conforms(node, shape, eval_graph, self.shapes_graph):
        continue
    seed = SolutionMapping(bindings={tr.focus_var.name: node})
    new_triples |= self._evaluate_single_rule(tr.rule, eval_graph, seed)
return new_triples
```

---

## 3. Formal semantics

Notation follows the spec's rule-set evaluation: a **solution mapping** μ is a
partial function from variables to RDF terms; a rule body evaluates over a
running set of solution mappings Ω, starting from an initial Ω₀; head templates
are instantiated once per μ ∈ Ω. Below, **S** is the shapes graph, **G** the
current data/inference graph.

### 3.1 Abstract syntax

Extend a rule with an optional **targeting pair** `(v, s)` where `v` is a
variable (the *focus variable*) and `s` is an IRI (the *shape*). A rule carrying
a targeting pair is a **targeted rule**; one without is an ordinary rule
(unchanged). In this implementation the pair is the `TargetedRule` wrapper over
an underlying rule *R*:

```
TargetedRule ::= (R : Rule, focusVar : Variable, shape : IRI, direction)
```

`direction ∈ {rule-to-shape, shape-to-rule}` records which surface expressed the
attachment; both normalize to the same evaluation.

### 3.2 Concrete syntax (EBNF), spec-style

The spec's current productions (quoted verbatim):

```
[12] Rule1 ::= 'RULE' iri? HeadTemplate 'WHERE' BodyPattern
[13] Rule2 ::= 'IF' BodyPattern 'THEN' HeadTemplate
```

The extension inserts one optional production and threads it into both forms
(the change actually shipped, `grammar-ext.lark:8-10`):

```
[12'] Rule1     ::= 'RULE' iri? ForClause? HeadTemplate 'WHERE' BodyPattern
[13'] Rule2     ::= 'IF' BodyPattern 'THEN' iri? ForClause? HeadTemplate
[NEW] ForClause ::= 'FOR' Var 'IN' iri
```

`Var` and `iri` are the spec's existing terminals. Nothing else in the grammar
changes; in particular `BodyPattern`, `BodyNotTriples`, `Filter`, `Negation`,
`Assignment` are untouched — targeting is a **rule prefix, not a body element**.

### 3.3 Evaluation semantics

Let `focusNodes(s, S, G)` be the set of focus nodes selected by shape `s`'s
targets, and `conforms(n, s, S, G)` the boolean conformance of node `n` to `s`.
Define the **eligible set**:

```
F(s) = { n ∈ focusNodes(s, S, G) : conforms(n, s, S, G) }
```

A targeted rule `(R, v, s)` contributes, to the inference, the union over every
`n ∈ F(s)` of the head instantiations of `R` evaluated with the body's initial
solution set **seeded** to a single mapping binding the focus variable:

```
Ω₀ = { { v ↦ n } }          (targeted rule)
```

This is the *only* departure from the spec's global rule, which starts from a
single empty mapping:

```
Ω₀ = { ∅ }                  (spec rule — fires once, globally)
```

**Reduction (proposal-relevant).** A targeted rule is exactly the spec rule
whose body carries one extra premise "`v` is a conforming target of `s`" and
whose free occurrences of `v` are pre-bound. Equivalently, `FOR v IN s` behaves
as if a virtual, non-expressible body element `TARGET(v, s)` were prepended,
producing `Ω₀ = { {v↦n} : n ∈ F(s) }`. Everything downstream — body matching,
`FILTER`, `NOT`, `SET`, head instantiation, blank-node freshness per mapping —
is the standard rule machinery, run on `R` unchanged.

### 3.4 Fixpoint and stratification fit

- **Monotonicity.** Over the supported SHACL subset (§3.6), both `focusNodes`
  and `conforms` are **monotone** in `G`: adding triples can only add focus nodes
  and can only make more nodes conform (the subset excludes non-monotone
  constructs such as `sh:maxCount`-as-gate paradoxes, `sh:closed`, `sh:not` used
  to *deny* — see §3.6). Hence `F(s)` only grows as `G` grows, and per-stratum
  fixpoint iteration still converges.
- **Gate as a closed dependency.** A targeted rule must be evaluated against a
  graph where every rule that could change its verdict is already at fixpoint.
  So the stratifier adds a **closed** edge (same class as a `NOT`/`SET`/blank-node
  dependency) from the targeted rule to any rule whose head can assert a
  predicate the shape *reads* — its target predicates plus its constraints'
  predicates (`shape_referenced_predicates`, `stratification.py:467-476`). This
  places the targeted rule **strictly above** those rules. A cyclic shape-gate
  dependency raises `StratificationError`, consistent with the existing
  closed-cycle rule.
- **Run-once vs general.** A targeted rule with an assignment or blank-node head
  is a run-once rule; otherwise it iterates to fixpoint like any general rule.

### 3.5 Well-formedness

Validate the wrapped rule `R` with the initial bound-variable set
`V₀ = { focusVar }` (the focus variable is bound at Ω-seed time). Every other
condition from the spec's well-formedness (§3.2 — each `FILTER`/`SET` variable
defined by an earlier body element; `NOT` validated as its own well-formed
sequence given the variables bound before it; every head-template variable bound
in the body) is unchanged. In the implementation the binding is realized by the
seed mapping at `engine.py:278`; the base validator
(`validate_rule_well_formedness`, `nodes.py:636`) is the `V₀ = ∅` case for
ordinary rules.

### 3.6 SHACL Core subset used for targeting

Targets and conformance are computed by an in-house, intentionally partial
SHACL 1.2 Core subset (no external validator dependency). The authoritative list
is in [`docs/shacl-core-support-matrix.md`](shacl-core-support-matrix.md); the
sets are `_TARGET_PREDS` / `_NODE_CONSTRAINTS` / `_PROP_CONSTRAINTS` in
[`src/srl/shapes/model.py`](../src/srl/shapes/model.py). Anything outside the
supported tables raises `UnsupportedShapeFeatureError` at shape-load time — it is
never silently ignored, because a silently-dropped constraint would mis-scope the
rule. Supported targets include `sh:targetClass`, `sh:targetNode`,
`sh:targetSubjectsOf`, `sh:targetObjectsOf`, and the 1.2 additions
`sh:targetWhere` and `sh:shape`.

---

## 4. Relationship to the SHACL 1.2 Rules spec

### 4.1 The spec has no targeting

Fetched from <https://www.w3.org/TR/shacl12-rules/> (2026-07): the document's
table of contents (Abstract Syntax, Concrete Syntax, **Rule Set Evaluation**,
Grammar) contains **no** target, focus-node, or shape-attachment mechanism. A
rule's body is matched against the whole graph and its head instantiated for
every solution mapping; rules are a standalone inference layer, complementary to
but separate from shape validation. There is **zero** occurrence of `FOR` as a
syntax construct, and `sh:rule` is not part of this document.

### 4.2 Lineage — SHACL-AF

SHACL Advanced Features (SHACL-AF), an older and separate spec, attached rules to
a `sh:NodeShape` via `sh:rule`. The shape's targets became the rule's focus
nodes and the variable `$this` was bound to the focus node inside the rule. The
2026-07 SRL rewrite dropped this attachment entirely in favor of global rules.
`FOR ?v IN <shape>` is the **evolved, gated re-introduction** of that idea,
expressed as SRL solution-mapping seeding rather than SPARQL `$this` injection,
and with an author-chosen focus variable instead of the fixed `$this`.

### 4.3 Spec rule vs `FOR`-targeted rule

| Aspect | Spec rule (global) | `FOR ?v IN <shape>` |
| --- | --- | --- |
| Scope | whole graph | shape's target focus nodes |
| Focus binding | none | `?v` pre-bound per focus node |
| Initial Ω₀ | `{ ∅ }` (one empty mapping) | `{ {?v ↦ n} : n ∈ F(shape) }` |
| Conformance gate | none | rule fires only if `n` conforms to `shape` |
| Shape attachment | none | required (rule↔shape) |
| In current spec? | ✅ yes | ❌ no (opt-in extension) |

---

## 5. Proposal: adding this to the spec

The extension is deliberately shaped as a minimal, additive delta.

### 5.1 Grammar delta

Add production `[NEW] ForClause ::= 'FOR' Var 'IN' iri` and make it optional in
`[12] Rule1` and `[13] Rule2` (see §3.2). No other production changes; the body
grammar is untouched, so existing conforming documents keep parsing unchanged.

### 5.2 Abstract-syntax hook

Add an optional targeting pair `(focusVar, shape)` to a rule's abstract syntax
(§3.1). Ordinary rules are the case where the pair is absent.

### 5.3 Evaluation semantics

Adopt §3.3: a targeted rule seeds `Ω₀ = { {focusVar ↦ n} : n ∈ F(shape) }`
where `F(shape)` is the set of the shape's conforming focus nodes; the spec's
global rule is the special case `Ω₀ = { ∅ }`. Adopt the monotonicity condition
and the closed-dependency gate stratification of §3.4, and the `V₀ = {focusVar}`
well-formedness basis of §3.5.

### 5.4 Open questions for a WG

- **RDF concrete syntax.** Encode the attachment as new SRL terms
  (`srl:targetShape` + `srl:focusVar`, as this implementation does) or reuse the
  SHACL-AF-style `sh:rule` on the shape? Both directions should normalize to one
  abstract form. This implementation accepts both and normalizes.
- **Required SHACL subset.** Which SHACL Core targets/constraints must a
  *conforming* SRL processor support for gating, and how are unsupported ones
  signaled (error, as here, vs. ignore)?
- **Monotonicity boundary.** Precisely which SHACL constraints are admissible in
  a targeting shape so that fixpoint convergence is guaranteed (§3.6 gives this
  implementation's cut).
- **Interaction with SHACL Core targets & validation** — layering order between
  rule-inferred triples and validation targets.
- **Direction.** Keep both `rule→shape` and `shape→rule` surfaces, or pick one?

---

## 6. Worked example

Shapes graph (`sh:targetClass ex:Person`, requires `ex:age ≥ 18`):

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <http://example.org/> .
ex:AdultShape a sh:NodeShape ; sh:targetClass ex:Person ;
  sh:property [ sh:path ex:age ; sh:minCount 1 ; sh:minInclusive 18 ] .
```

Rule:

```sparql
PREFIX ex: <http://example.org/>
RULE ex:r FOR ?this IN ex:AdultShape
  { ?this ex:status ex:adult }
WHERE
  { ?this ex:age ?a }
```

Data:

```turtle
ex:Alice a ex:Person ; ex:age 30 .
ex:Bob   a ex:Person ; ex:age 10 .
```

Evaluation: `focusNodes(ex:AdultShape) = {Alice, Bob}` (both `ex:Person`).
`Alice` conforms (age 30 ≥ 18) → the rule fires with `?this ↦ Alice`, inferring
`ex:Alice ex:status ex:adult`. `Bob` fails `sh:minInclusive 18` → the gate skips
him, no triple. Result:

```turtle
ex:Alice ex:status ex:adult .   # inferred
# ex:Bob ex:status ex:adult  — NOT inferred (age 10 fails conformance)
```

A companion case: if a *plain* rule first infers `ex:age` for a node, proper
stratification (the closed gate edge, §3.4) places the targeted rule in a higher
stratum so its gate sees the inferred age. Both behaviors are exercised in
[`tests/test_shape_targeting.py`](../tests/test_shape_targeting.py)
(`test_targeted_rule_fires_only_for_conforming_focus_nodes`,
`test_targeted_rule_sees_inferred_target_membership`).

---

## 7. References

- W3C SHACL 1.2 Rules — <https://www.w3.org/TR/shacl12-rules/>
  (Editor's Draft: <https://w3c.github.io/data-shapes/shacl12-rules/>)
- SHACL Advanced Features (SHACL-AF), `sh:rule` — <https://www.w3.org/TR/shacl-af/>
- [`SPEC-COMPLIANCE-AUDIT.md`](../SPEC-COMPLIANCE-AUDIT.md) — §"Deliberately non-spec (opt-in extension)"
- [`docs/shacl-core-support-matrix.md`](shacl-core-support-matrix.md) — supported SHACL subset
- [`docs/superpowers/specs/2026-07-13-shape-targeting-and-rdf-serializer-design.md`](superpowers/specs/2026-07-13-shape-targeting-and-rdf-serializer-design.md) — design rationale
- Implementation: `grammar-ext.lark`, `transformer.py`, `ast/nodes.py` (`TargetedRule`), `engine/engine.py`, `engine/stratification.py`, `src/srl/shapes/`
