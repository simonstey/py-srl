# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`shacl-rules` implements the W3C [SHACL 1.2 Shape Rule Language (SRL)](https://w3c.github.io/data-shapes/shacl12-rules/): a declarative language for deriving new RDF triples from existing ones. It parses SRL, validates well-formedness, and evaluates rules with fixpoint semantics and stratified (safe) negation.

## SRL syntax summary (current 2026 spec)

- **Two rule forms** (the old Datalog `head :- body` form is **removed**):
  - `RULE iri? { head } WHERE { body }` — `iri` optionally names the rule.
  - `IF { body } THEN { head }`.
- **Assignment** is `SET( ?var := <expr> )`. The old `BIND(<expr> AS ?var)` is removed. The assigned variable must be new; expression variables must be bound by an earlier body element.
- **Declarations**: `TRANSITIVE(iri)`, `( iri ) SYMMETRIC` (postfix), `INVERSE(iri, iri)`. `REFLEXIVE` is removed.
- **Built-in functions** are exactly the spec production [121] list. Removed (do not parse): `BOUND`, `RAND`, `MD5`, `SHA1`, `SHA256`, `SHA384`, `SHA512`, `COALESCE`, and `EXISTS`/`NOT EXISTS`. The only negation construct is `NOT { ... }`.
- **Property paths** in bodies support only sequence `a/b` and inverse `^a`. No alternative `|`, transitive `+`/`*`, optional `?`, or negated property set.
- **DATA blocks** hold ground triples only (no variables, no paths); they are seeded into the graph before evaluation, and `IMPORTS` are resolved.
- **Well-formedness**: every FILTER/SET variable must be defined by an earlier body element; a NOT element is validated as its own well-formed sequence given the variables bound before it (a variable bound only inside NOT does not leak out); every head-template variable must be bound in the body.

## Commands

Package manager is **uv** (`uv.lock` present). Prefix commands with `uv run`, or activate `.venv` and drop the prefix.

```bash
uv sync --extra dev              # install project + dev deps

uv run pytest                    # full test suite (testpaths=tests, pythonpath=src)
uv run pytest tests/test_complete.py -v      # full integration pipeline
uv run pytest -k "filter"                    # tests matching a keyword
uv run pytest --cov=srl --cov-report=term-missing

uv run black src tests           # format (line-length 100)
uv run isort src tests           # import sort (black profile)
uv run mypy src                  # strict type check (disallow_untyped_defs)
```

CLI (`srl`, installed via the `[project.scripts]` entry point):

```bash
srl parse   RULES.srl                    # parse + validate, show summary
srl analyze RULES.srl --show-layers      # stratification layers + dependencies
srl eval    RULES.srl DATA.ttl -o OUT.ttl   # evaluate rules over data
srl -v ...                               # verbose: AST detail, provenance table
```

W3C conformance runner (generates an EARL report from the bundled test suite):

```bash
uv run python tests/run_shacl_rules_tests.py -o report.ttl [--test-type syntax|eval|...]
```

## Import path gotcha

Installed package and all tests import `from srl import ...` (pyproject sets `pythonpath = ["src"]`). The README's `from src.srl import ...` only works when running scripts from the repo root without installing. Prefer `from srl ...`.

## Architecture

Pipeline: **Rule text → Lark LALR parser → frozen-dataclass AST → stratification → per-stratum fixpoint engine → solution mappings → triple inference → result graph.**

- **`src/srl/parser/`** — `grammar.lark` (productions [1]-[121] from the spec grammar, LALR(1) — keep it unambiguous, do not modify without a spec reference) + `transformer.py`. Transformer method names match grammar rule names and return AST nodes directly. Two surface syntaxes parse to the same AST: `RULE iri? {..} WHERE {..}` and `IF {..} THEN {..}`. `grammar.lark` is a runtime data file, force-included into the wheel via `[tool.hatch.build.targets.wheel.force-include]`.
- **`src/srl/ast/nodes.py`** — all AST nodes are `@dataclass(frozen=True)` (immutable + hashable, required by the graph algorithms). Well-formedness (variable-scoping, §3.2) lives in `validate_rule_well_formedness()`, raising `WellFormednessError`.
- **`src/srl/engine/`** — the core:
  - `stratification.py`: builds the rule dependency graph with **open/closed** edge labels (closed = dependency via a `NOT` negation element, a `SET` assignment, or a blank-node head), then assigns strata (open edge: same-or-higher stratum; closed edge: strictly higher). The stratification condition forbids a recursive dependency involving a closed edge and raises `StratificationError`. `stratify()` returns per-stratum `StratificationLayer` objects with **run-once** rules (assignment or blank-node head, evaluated once) split from **general** rules (evaluated to fixpoint).
  - `solutions.py`: `SolutionMapping` (variable bindings) plus the relational algebra — `compatible`, `merge`, `join`, `minus` (for `NOT`), and `graphMatch` (direct rdflib triple matching, not SPARQL, for speed).
  - `rules.py` (`eval_rule`): evaluates body elements left-to-right over a running set of solution mappings Ω — `TriplePattern` joins `graphMatch`, `FILTER` keeps mappings whose expression EBV is true, `NOT` applies `minus`, `SET` assignment extends Ω — then instantiates head templates.
  - `expressions.py`: `eval_expr` / `effective_boolean_value` + the spec [121] SPARQL built-ins (numeric, string, datetime, term-testing). Add a built-in here (and to `grammar.lark`).
  - `engine.py` (`RuleEngine`): drives per-stratum fixpoint iteration (bounded by `max_iterations=1000`). `evaluate(graph, inplace=..., results_only=...)` and `evaluate_with_provenance(graph)` (tracks which rule inferred each triple).
- **`src/srl/rdf/`** — namespace/prefix management and RDF term helpers.
- **`src/srl/cli/`** — rich-click commands (`main.py`) + Rich formatting (`formatting.py`). `FORMAT_MAP` in `main.py` maps file extensions to rdflib parse formats.

## Behavioural quirks

- Blank nodes: fresh per rule application, **not** skolemized.
- `evaluate(inplace=True)` mutates the input graph; `inplace=False` copies first.
- Recursive rules that don't converge hit the `max_iterations` cap and raise.

## Conventions

- **Conventional commits** always (`feat:`, `fix:`, `docs:`, `test:`, ...).
- Strict typing: annotate everything; `Any` only for dynamically-typed expression-evaluation results.
- Debug parse issues with `scripts/debug_parser.py` (Lark tree) and `scripts/debug_transform.py` (AST); or `srl -v parse` for AST detail.
