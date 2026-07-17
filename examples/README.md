# SHACL 1.2 Rules — Examples

Runnable examples covering the SHACL 1.2 Shape Rule Language (SRL) and the
py-srl API. Each numbered script is standalone and isolates one feature; they
build up from a single rule to the full programmatic API.

## Running

Run any script from the project root:

```bash
uv run python examples/01_simple_inference.py
uv run python examples/02_rule_forms.py
# ... through ...
uv run python examples/11_api_provenance.py
```

The scripts import the installed package (`from srl.parser import SRLParser`).
If you have not installed the project, set `PYTHONPATH=src` first (this is what
the test suite does): `PYTHONPATH=src python examples/01_simple_inference.py`.

## Example Descriptions

### 1. Simple Inference (`01_simple_inference.py`)

**Concept:** the parse → evaluate → read cycle.

The minimal rule: `parent(x, y) → ancestor(x, y)`. Shows `SRLParser().parse`,
`RuleEngine(...).evaluate(graph, inplace=False)`, and reading the new triples.

### 2. Rule Forms (`02_rule_forms.py`)

**Concept:** the two interchangeable syntaxes, plus named rules.

```sparql
RULE ex:PersonRule { ?p rdf:type ex:Person } WHERE { ?p ex:age ?a ; ex:name ?n }
IF   { ?p rdf:type ex:Person . ?p ex:age ?a . FILTER (?a >= 18) } THEN { ?p rdf:type ex:Adult }
```

`RULE {head} WHERE {body}` and `IF {body} THEN {head}` parse to the same AST.
An optional IRI after `RULE` names the rule (inspectable via `rule.iri`).

### 3. Recursion & Transitive Closure (`03_recursion_transitive.py`)

**Concept:** a recursive rule + fixpoint iteration.

```sparql
RULE { ?x ex:ancestor ?z } WHERE { ?x ex:ancestor ?y . ?y ex:ancestor ?z }
```

The engine stratifies the rules and iterates until no new triples appear, so a
parent chain of any depth yields the complete ancestor relation.

### 4. FILTER Conditions (`04_filter_conditions.py`)

**Concept:** keeping only the solution mappings a condition accepts.

```sparql
FILTER (?age >= 18 && ?age < 65)
FILTER (?dept IN ("Engineering", "Design"))
```

Demonstrates comparison, compound `&&`, and `IN` membership.

### 5. SET & Built-in Functions (`05_set_and_functions.py`)

**Concept:** computing new values with `SET(?v := expr)`.

```sparql
SET(?full := CONCAT(?first, " ", ?last))
SET(?disp := UCASE(?full))
SET(?err  := ABS(?pred - ?act))
SET(?rating := IF(?err <= 5, "good", "poor"))
```

Assignments chain (a later `SET` may use an earlier one). There is **no** `BIND`
keyword — assignment is always `SET`.

### 6. Negation (`06_negation.py`)

**Concept:** closed-world negation with `NOT { … }`.

```sparql
RULE { ?person ex:childless true } WHERE {
    ?person ex:type ex:Person .
    NOT { ?person ex:hasChild ?child }
}
```

Every variable used inside `NOT` must be bound by a positive pattern first, and
the negated predicate must differ from the head predicate.

### 7. Property Paths (`07_property_paths.py`)

**Concept:** the two supported path operators.

```sparql
?grandparent ex:parentOf/ex:parentOf ?grandchild   # sequence a/b
?child ^ex:parentOf ?parent                          # inverse ^a
```

Alternative (`|`), transitive (`+`/`*`), optional (`?`), and negated (`!`) paths
are not part of SRL. Use recursion (Example 3) for transitivity.

### 8. Declarations (`08_declarations.py`)

**Concept:** `TRANSITIVE`/`SYMMETRIC`/`INVERSE` as inspectable metadata.

```sparql
TRANSITIVE(ex:ancestorOf)
(ex:friendOf) SYMMETRIC
INVERSE(ex:employs, ex:worksFor)
```

These are recorded on `rule_set.declarations` (and merged across `IMPORTS`), but
this engine does **not** derive their closure automatically — the example pairs
each declaration with an explicit rule that performs the inference.

### 9. DATA Blocks (`09_data_blocks.py`)

**Concept:** ground facts that travel with the rules.

```sparql
DATA { ex:Alice ex:parent ex:Bob . ex:Bob ex:parent ex:Carol . }
```

`DATA` triples are seeded into the graph before evaluation, so a rule set can be
self-contained and run against an empty input graph.

### 10. RDF 1.2 Syntax (`10_rdf12_syntax.py`)

**Concept:** RDF 1.2 surface syntax desugared to plain triples.

```sparql
?c ex:items ( "milk" "eggs" "bread" )                  # collection
?c ex:contact [ ex:email "a@b.c" ; ex:priority 1 ]     # blank-node list
?s ex:validReading ?r {| ex:derivedBy ex:Rule |}       # annotation
```

Collections and blank-node lists desugar to ordinary triples and evaluate
normally. The reification family (`<< >>`, `~`, `{| |}`) desugars to RDF 1.2
*triple terms*; those parse, but on an rdflib without triple-term support
evaluating them raises `UnrepresentableTripleTermError` — the example shows both
outcomes.

### 11. API: Provenance & Strata (`11_api_provenance.py`)

**Concept:** the richer engine API.

```python
engine.get_stratum_info()                                 # rule indices per layer
engine.evaluate(graph, inplace=False, results_only=True)  # only the NEW triples
engine.evaluate_with_provenance(graph, inplace=False)     # (graph, [(triple, rule_idx, stratum)])
```

Attributes every inferred triple to the rule (and stratum) that produced it;
`rule_idx == -1` means the triple came from a `DATA` block.

### 12. Rule-to-Shape Targeting (`12_shape_targeting.py`) — opt-in extension

**Concept:** scope a rule to the focus nodes of a SHACL shape.

> **Not part of the SRL spec.** This is an opt-in extension, off by default.

```sparql
RULE ex:AdultRule FOR ?this IN ex:AdultShape {
    ?this ex:status ex:adult .
} WHERE {
    ?this ex:age ?a .
}
```

The rule fires once per data node that the shape *targets* **and** that
*conforms* to it. Enabling the extension is explicit:

```python
SRLParser(extensions=True)                       # to parse FOR ?v IN <shape>
RuleEngine(rs, extensions=True, shapes_graph=g)  # to evaluate against the shapes
```

Targeted rules are collected on `rule_set.targeted_rules` (separate from
`rule_set.rules`). On the CLI this is the `srl shacl` subcommand (below).

## CLI Usage

The `srl` command wraps the same engine. Using the bundled `ancestor_rules.srl`
+ `family_data.ttl`:

```bash
# Parse + validate, show a rule-set summary
uv run srl parse examples/ancestor_rules.srl

# Show stratification layers
uv run srl analyze examples/ancestor_rules.srl --show-layers

# Evaluate rules over data, writing the result graph
uv run srl eval examples/ancestor_rules.srl examples/family_data.ttl -o out.ttl

# Verbose eval prints a provenance table (which rule inferred each triple)
uv run srl -v eval examples/ancestor_rules.srl examples/family_data.ttl
```

The `srl shacl` subcommand evaluates the opt-in rule-to-shape targeting
extension against a SHACL shapes graph:

```bash
uv run srl shacl examples/shape_targeting.srl examples/shape_targeting_data.ttl \
    --shapes examples/shape_targeting_shapes.ttl -o out.ttl
```

## Interactive Notebook

`playground.ipynb` is a guided tour of the API: parse → inspect the `RuleSet`
→ evaluate → trace provenance → view stratification layers.

```bash
uv run jupyter lab examples/playground.ipynb
```

## Not Supported

These deliberately do **not** parse or evaluate (documented so you don't reach
for them):

- **Built-ins:** `MD5`/`SHA1`/`SHA256`/`SHA384`/`SHA512`, `RAND`, `BOUND`,
  `COALESCE`, `EXISTS`/`NOT EXISTS`. (Use `NOT { … }` instead of `NOT EXISTS`;
  add the triple pattern to the body instead of `EXISTS`.)
- **Path operators:** alternative `|`, transitive `+`/`*`, optional `?`,
  negated `!`. Only sequence `a/b` and inverse `^a` are supported.
- **Old syntax:** the Datalog `head :- body` form and `BIND(expr AS ?var)` were
  removed; use `RULE`/`WHERE` (or `IF`/`THEN`) and `SET(?var := expr)`.

## Troubleshooting

**Import errors** — install the project (`uv sync --extra dev`) or run with
`PYTHONPATH=src`.

**No output** — check that (1) input data matches the rule body patterns,
(2) variables are consistent between body and head, (3) `PREFIX` declarations
match the data namespaces.
