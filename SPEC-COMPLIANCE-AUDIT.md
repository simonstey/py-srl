# py-srl ↔ W3C SHACL 1.2 Rules — Spec Compliance Audit

**Date:** 2026-07-13
**Spec baseline:** `w3c/data-shapes` `gh-pages` branch, `shacl12-rules/` (snapshot taken 2026-07-13, *after* the 2026-07-07 grammar restructuring — PRs #983, #952, #941, #946).
**Method:** local spec snapshot in `.spec-snapshot/`; 9 dimension auditors + adversarial dual-lens verification (spec-fidelity + code-fidelity). 50 raw findings → **46 confirmed, 1 plausible, 3 refuted**; the single-rule-evaluation dimension stalled in the batch and was re-run separately (6 more findings: 4 confirmed runtime bugs, 2 plausible).

---

## 1. What changed in the spec (root cause)

The spec was **restructured on 2026-07-07**. The local `grammar.lark`, AST, and engine were written against the *previous* revision. Concretely, the current spec now:

1. **Splits the grammar into three production families** — `Data` (no variables, no paths), `HeadTemplate` (variables, no paths), `BodyPattern` (variables + paths). py-srl reuses one shared production family for all three.
2. **Removes the Datalog `head :- body` form** (old Rule3). Only `RULE … WHERE` (Rule1, now with an optional leading `iri`) and `IF … THEN` (Rule2) remain.
3. **Changes assignment** from `BIND ( Expression AS Var )` to **`SET ( Var := Expression )`**.
4. **Reworks declarations** — postfix `( iri ) SYMMETRIC`; **removes `REFLEXIVE`**.
5. **Fixes the built-in list** ([121]) — excludes `BOUND`, `RAND`, `MD5`/`SHA*`, `COALESCE`, `EXISTS`/`NOT EXISTS`.
6. **Rewrites dependency + stratification** — a dependency graph with **open/closed edge labels** (not positive/negative), a stratification condition = *no recursive dependency involving a closed dependency*, and each stratum split into **(once, general)** where **run-once rules** (assignment element OR blank node in head) run exactly once before the general fixpoint loop.
7. **Defines rule-set evaluation** with DATA seeding (`GE = G0 ∪ D`, `GI = {t∈D | t∉G0}`), import resolution, and per-μ negation semantics.

---

## 2. Confirmed non-compliances by severity

### CRITICAL — valid current-spec input is rejected/crashes, or evaluation is silently wrong

| # | Area | Finding | Location |
|---|------|---------|----------|
| C1 | Grammar | **`a` (rdf:type shorthand) crashes the transformer** — inline literal is filtered by Lark, `verb`/`path_primary` get empty `items`, `return items[0]` → `IndexError` in body/head/data positions. | `transformer.py:351,458`; `grammar.lark:120,188` |
| C2 | Grammar | **Assignment uses removed `BIND(expr AS var)`; the only current syntax `SET(?v := expr)` is rejected.** Spec example `SET (?o := 18)` fails to parse; removed `BIND(18 AS ?o)` parses. | `grammar.lark:85`; `transformer.py:253` |
| C3 | Eval | **DATA blocks are never seeded** into the graph. `rule_set.data_blocks` is unused in `engine.py`; bodies can't match DATA facts and DATA triples are absent from output. | `engine.py:91-106,174` |
| C4 | Stratification | **Layers are not `(once, general)`; run-once rules never identified.** Every rule is re-run each fixpoint iteration → blank-node-head rules mint fresh bnodes forever (non-termination), assignment rules re-run. | `stratification.py:289-341`; `engine.py:122-148` |
| C5 | Dependency | **Closed-dependency conditions for assignment elements and blank-node heads are never computed** (no `mergeLabel`). Such deps are treated as open → wrong stratum ordering, and closed-dep cycles aren't rejected. | `stratification.py:99-129` |
| C6 | Dependency | **"Possibly match" reduced to predicate-IRI overlap** — subject/object terms and the repeated-variable constraint ignored. Over-approximates deps → **valid rule sets falsely rejected** as negation cycles. | `stratification.py:132-209` |
| C7 | Stratification | **Stratification condition only checks negation cycles** — closed cycles via assignment/blank-node head are accepted though the spec declares no defined outcome. | `stratification.py:212-286` |

### HIGH — major feature missing/removed or wrong algorithm

| # | Area | Finding | Location |
|---|------|---------|----------|
| H1 | Eval (recovered) | **`graphMatch` ignores repeated-variable consistency.** Pattern `?x p ?x` binds object over subject; returns μ where `subst(μ,TP)` is *not* in G. E.g. `ex:a ex:knows ex:b` matches `?x ex:knows ?x` → `{x:ex:b}`. | `solutions.py:205-231` |
| H2 | Eval (recovered) | **EXISTS/NOT EXISTS undispatched in `eval_expr`** → always `None` → EBV false → `FILTER(EXISTS…)` drops all rows and `FILTER(NOT EXISTS…)` also drops all rows (negated flag never read). *(Also: EXISTS isn't in spec [121] — see M-group; but the code accepts and then mis-evaluates it.)* | `expressions.py:51-76` |
| H3 | Eval (recovered) | **Evaluation graph never threaded to expressions** — `eval_filter`/`eval_assignment` pass `active_graph` (always `None`), not the `graph` they hold. Graph-dependent forms can't see any triples. | `rules.py:162,246` |
| H4 | Dependency | **Stale positive/negative-dependency model** instead of open/closed edge labels — the entire dependency graph is the wrong shape; everything downstream computes on it. | `stratification.py:27,112-119` |
| H5 | Stratification | **`assign_strata` leaves open (positive) deps unconstrained** — the `stratum(R1) ≥ stratum(R2)` rule for open edges is not implemented; only negative deps bump. A rule openly depending on a negation-raised rule stays in a lower stratum → evaluated against an incomplete graph. | `stratification.py:316-330` |
| H6 | Eval | **Run-once vs general not distinguished by the engine** — uniform fixpoint over all rules. | `engine.py:122-148` |
| H7 | Eval | **IMPORTS never resolved** — `prologue.imports` stored, never fetched/merged. Import-based rule sets silently lose rules + data. | `engine.py` (absent) |
| H8 | Grammar/AST | **`RULE` lacks the optional `iri` identifier** ([12]) — named rules rejected; AST `Rule` has no id field. | `grammar.lark:30`; `nodes.py:402-421` |
| H9 | Grammar | **Removed Datalog `:-` form still present and functional.** | `grammar.lark:36`; `transformer.py:187` |
| H10 | Grammar | **`SYMMETRIC` uses removed prefix form** — postfix `( :p ) SYMMETRIC` rejected. *(Note: the spec's own §4.1 abbreviations list still shows prefix `SYMMETRIC(uri)` and flags it at-risk — internal spec inconsistency.)* | `grammar.lark:41` |
| H11 | Grammar | **No separate Data family; DATA blocks wrongly accept variables** (`data` reuses head-template productions). | `grammar.lark:46` |
| H12 | Well-formed | **Negation-element bodies never validated** — `NegationElement` matches no branch in `validate_rule_well_formedness`; ill-formed negation bodies accepted (largest §wellformed condition missing). | `nodes.py:596-633` |
| H13 | Expressions | **RDF-star triple builtins `isTRIPLE`/`TRIPLE`/`SUBJECT`/`PREDICATE`/`OBJECT` parse but have no eval branch** → silently `None`. | `expressions.py:221-362` |
| H14 | Expressions | **`sameTerm()` unreachable** — transformer stores `"sameTerm"`, dispatch uppercases to `"SAMETERM"` with no case → `None`. | `expressions.py:227,360` |
| H15 | RDF syntax | **SRL/RDF concrete syntax entirely unimplemented** — no reader/serializer for the `srl:` RDF encoding. *(Mitigated: spec §rdf-rules-syntax is still largely editorial `@@`/ednote.)* | `src/srl/rdf/**` |

### MEDIUM

- **AST:** `Rule` has no URI field (H8 twin, low semantic impact); `ReflexiveDeclaration` node still present; `DataBlock.triples` typed `TripleTemplate` (permits variables); triple templates/patterns can't hold **triple terms** (`RDFTerm` union omits them); run-once/general unrepresented; imports modeled on `Prologue` not as a RuleSet collection, no resolved-rule-set concept.
- **Grammar:** only one leading `Prologue` (interspersed `PREFIX` between rules rejected, [2]); optional `.` after `BodyNotTriples`/`BodyBasicNotTriples` unsupported ([16]/[24]); `IRIREF`/string terminals omit the `UCHAR` `\uXXXX` escape ([122],[138]-[141]).
- **Well-formed:** assignment novelty check only compares against prior *assignments*, not triple-pattern-bound vars (too lax — `?x :p ?y . SET(?x := 1)` wrongly accepted); an **invented over-strict** rule rejects an assignment variable reused in a *later* triple pattern (`SET(?x:=1) . ?x :p ?y` wrongly rejected — condition not in current spec).
- **Eval:** default `evaluate()`/`evaluate_rules()` return `GE` (base+inferred), not spec's `GI`; combined with C3, no API path yields the normative `GI`.
- **Expressions:** `LANGDIR`/`STRLANGDIR`/`hasLANG`/`hasLANGDIR` parse but unimplemented (`None`); grammar+engine support spec-excluded `BOUND`/`RAND`/`MD5`/`SHA*`/`COALESCE`; EXISTS/NOT EXISTS accepted though not in [121]; **EBV returns false for derived numeric XSD types** (`"5"^^xsd:int` → false, internally inconsistent with `is_numeric()`); logical `&&`/`||` coerce error operands to false instead of propagating (SPARQL 3-valued logic).
- **RDF syntax:** `srl:` (`…/ns/shacl-rules#`) and `sparql:` namespaces neither defined nor registered.

### LOW

- `AggregationElement` modeled though spec leaves aggregation pending.
- Stale docs: `Assignment.__str__` emits `BIND(…AS…)` + inverted operand order; `Rule` docstring cites `:-`; well-formedness docstring cites non-existent "Section 3.2" and a fabricated 5-condition list.
- `ROUND`/`CEIL`/`FLOOR` force `xsd:integer`; `UCASE`/`LCASE`/`SUBSTR`/`STRBEFORE`/`STRAFTER`/`CONCAT` drop lang tags/datatypes (SPARQL return-type divergence).
- `src/srl/rdf/` is generic, unused dead code (models RDF, not the SRL vocabulary).
- `srl shacl` CLI + README entry are acknowledged placeholders.

---

## 3. Plausible (needs confirmation)

- **`P1` — VERSION label ignored.** `VERSION` parsed but never validated against `"1.2"`, never used; media-type `version` parameter unsupported. Spec §defined-version-labels normativity is soft, so spec-lens returned PLAUSIBLE (code fact confirmed).
- **`P2` — Negation via global `minus()` vs per-μ re-evaluation.** `eval_negation` computes `minus(omega, ⋃_μ eval(N,{μ}))`. **Provably equivalent** to the spec's per-μ empty-check *for well-formed single-rule bodies* (domain homogeneity), so no reachable bug — but it's a faithful-transcription gap relying on an unstated invariant; diverges at the algebra level on heterogeneous-domain solution sequences.

## 4. Refuted (checked and dismissed — no action)

- **Well-formedness extractor not recursing into EXISTS** — REFUTED: EXISTS isn't a spec expression form, and its inner variables are locally scoped (like a negation body given `V_{i-1}`), so *not* flagging them is spec-correct.
- **Missing "Stratification error" from the limit guard** — REFUTED: the algorithm is non-normative and a violated stratification condition is *undefined*, not a mandated error; and the guard is exhaustively-verified dead code (the cycle is always caught earlier by `detect_negation_cycles`).
- **Media type `application/shape-rules` not advertised** — REFUTED: §mediaType is an IANA registration template with no processor obligation; `detect_format` never touches the `.srl` file anyway.

---

## 5. Suggested remediation order

1. **Unblock parsing** (C1 `a`, C2 `SET`, H8 named rules, H11 Data family, H9/H10 remove `:-`/fix SYMMETRIC) — the parser currently rejects or crashes on ordinary current-spec documents.
2. **Fix evaluation correctness** (C3 DATA seeding, H1 graphMatch self-join, H3 graph threading, H13/H14/H2 builtin dispatch) — these silently produce wrong results.
3. **Rebuild dependency/stratification** on the open/closed-label model (H4, C5, C6, C7, H5, C4/H6 once-general) — the current model is structurally the wrong algorithm.
4. **Complete features** (H7 imports, H15 SRL/RDF syntax, triple terms) and clean up stale docs / spec-excluded builtins.

*Full machine-readable findings with verbatim spec quotes and dual-lens verdicts: `.spec-snapshot/audit-result.json`. Spec snapshot: `.spec-snapshot/`.*

---

## 6. Remediation outcome (2026-07-13)

Branch `feat/shacl12-rules-2026-spec-compliance`. All 46 confirmed findings were addressed; a follow-up adversarial re-audit (37 resolved / 3 partial / 0 not-resolved / 0 regressed on the original set, plus a fresh divergence sweep) drove a second fix pass. Test suite: **42 passed, 4 xfailed** (unsupported path features) + **34 dedicated regression tests** in `tests/test_spec_compliance.py`, all green.

### Fixed
- **Grammar** rewritten to the three Data/Head/Body families; `a` shorthand (named `TYPE_A` terminal), `SET(?v := expr)`, `RULE iri?`, postfix `SYMMETRIC`, removed `:-`/`REFLEXIVE`, interspersed prologue, optional `.`, `UCHAR`, builtin list trimmed to spec [121] (`BOUND`/`RAND`/`MD5`/`SHA*`/`COALESCE`/`EXISTS` removed).
- **AST**: `Rule.iri`, `TripleTerm` node + `RDFTerm` union, `is_run_once()`, imports as a rule-set collection + `is_resolved`; removed `ReflexiveDeclaration`/`AggregationElement`; `Assignment.__str__` → `SET`.
- **Well-formedness** rewritten to the V₀/vars_i/V_{i-1}/V_all semantics incl. recursive negation-body validation; removed the invented over-strict rule; fixed the too-lax assignment-novelty check.
- **Dependency + stratification** rebuilt on open/closed edge labels (`mergeLabel`), full three-position "possibly match" with the repeated-variable constraint, the recursive-closed-dependency condition, and `(once, general)` layers with run-once identification.
- **Engine**: DATA seeding into `GE`/`GI`, run-once-then-general per stratum, evaluation graph threaded to expressions, `results_only` → `GI`, per-μ negation, IMPORTS resolution (Windows `file://` safe), **fresh head blank nodes per solution mapping**.
- **`graphMatch`** repeated-variable consistency (plain **and** property-path branches); triple-term positions no longer crash.
- **Expressions**: RDF-star triple builtins, `sameTerm`, `LANGDIR`/`STRLANGDIR`/`hasLANG`/`hasLANGDIR` dispatch; EBV for derived numerics; three-valued `&&`/`||`; the eight datetime accessors (`YEAR`…`TZ`) implemented; value-equality respects language tags; `ROUND` half-up; string functions preserve language tags; `LANGMATCHES` RFC 4647 basic filtering.
- **SRL/RDF concrete syntax** (`srl.rdf.vocab`, `srl.rdf.reader`): parses the `srl:RuleSet` encoding incl. `sparql:equals`/`logical-or`/`logical-and` operator IRIs; rejects variables in data blocks; `srl:`/`sparql:` namespaces registered.

### Known remaining limitations (deferred — pre-existing, larger scope)
- **RDF-1.2 collection/reification surface not in the grammar**: blank-node property lists `[ … ]`, RDF collections `( … )`, reified triples `<< s p o >>` / `ReifiedTripleBlock`, annotation blocks `{| … |}`, and reifiers `~` are absent from all three grammar families. Only the triple-term form `<<( … )>>` is supported. Adding these is a self-contained follow-up.
- **Base-direction literals** (`LANGDIR`/`STRLANGDIR`/`hasLANGDIR`): dispatch is correct but effectively no-ops under the pinned rdflib (7.6.0 has no literal base-direction API); `hasLANG` works. Needs an rdflib with direction support (or a shim).
- **Triple terms in the graph**: the installed rdflib exposes no triple-term class, so triple terms materialize as Python tuples; full RDF-star graph round-tripping is limited by the dependency.
- **`TriplePattern.predicate`** intentionally retains `PropertyPath` (a concrete-syntax convenience) rather than expanding paths to pure abstract-syntax triple patterns — documented design choice, behaviourally equivalent for the supported `a/b` and `^a` forms.
- A handful of lower-priority SPARQL fidelity edges remain (type-error vs string-fallback for incomparable relational operands; `xsd:float`/`float` division result type) — tracked, not spec-blocking.

### Deliberately non-spec (opt-in extension)
- **Rule-to-shape targeting** (the `FOR ?v IN <shape>` clause, the `srl shacl` command, the SRL/RDF `srl:targetShape`/`srl:focusVar` attachment, and the in-house SHACL 1.2 Core subset in `src/srl/shapes/`) is an **opt-in extension and is NOT part of the SRL spec**. It is reachable only behind the `--extensions`/`-x` flag (`SRLParser(extensions=True)` / `RuleEngine(..., extensions=True)`); with the flag off the parser and engine stay byte-for-byte spec-conformant and reject the `FOR` clause / any `targeted_rules`. The supported vs. unsupported SHACL constraints are documented in [`docs/shacl-core-support-matrix.md`](docs/shacl-core-support-matrix.md).
