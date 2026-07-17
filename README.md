# shacl-rules: Python SHACL 1.2 Rules (SRL) Parser and Evaluation Engine

## Overview

The [Shape Rule Language (SRL)](https://w3c.github.io/data-shapes/shacl12-rules/) is an extension of SHACL that provides a declarative rule language for deriving new RDF triples from existing ones. This project aims to implement:

1. **Parser** - Parse SRL rule syntax into abstract syntax trees
2. **Validator** - Check well-formedness and safety conditions
3. **Evaluator** - Execute rules with fixpoint semantics and stratification

## Installation

**Development Status:** This project is in active development. Install from source:

```bash
# Clone the repository
git clone https://github.com/simonstey/py-srl.git
cd py-srl

# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

### Running Examples

The `examples/` directory contains 12 standalone scripts, each isolating one
feature (see [`examples/README.md`](examples/README.md) for the full index):

```bash
# Basic inference
python examples/01_simple_inference.py

# Recursion / transitive closure
python examples/03_recursion_transitive.py

# Rule-to-shape targeting (opt-in extension)
python examples/12_shape_targeting.py

# Run the test suite
python -m pytest
```

## Python API Usage

```python
from rdflib import Graph, Namespace, Literal
from srl.parser import SRLParser
from srl.engine import RuleEngine

# Define namespace
EX = Namespace("http://example.org/")

# Create and populate RDF graph
graph = Graph()
graph.bind("ex", EX)
graph.add((EX.Alice, EX.parent, EX.Bob))

# Define rules
rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}
"""

# Parse rules
parser = SRLParser()
rule_set = parser.parse(rule_text)

# Create engine and evaluate
engine = RuleEngine(rule_set)
result_graph = engine.evaluate(graph, inplace=False)

# Access results
for s, p, o in result_graph:
    print(f"{s} {p} {o}")
```

## Example Rules

### Rule Syntax Forms

SHACL 1.2 Rules provides two rule forms. (The Datalog `head :- body` form of
earlier drafts has been removed and no longer parses.)

```sparql
PREFIX ex: <http://example.org/>

# RULE/WHERE form (an optional IRI may name the rule: RULE ex:AdultRule { ... } WHERE { ... })
RULE {
    ?person ex:isAdult true .
} WHERE {
    ?person ex:age ?age .
    FILTER (?age >= 18)
}

# IF/THEN form
IF {
    ?x ex:parent ?y .
    ?y ex:parent ?z .
} THEN {
    ?x ex:grandparent ?z .
}

# SET assignment (BIND(expr AS ?var) has been replaced by SET(?var := expr))
RULE {
    ?person ex:fullName ?fullName .
} WHERE {
    ?person ex:firstName ?first .
    ?person ex:lastName ?last .
    SET(?fullName := CONCAT(?first, " ", ?last))
}

# Negation (NOT { ... } is the only negation construct; EXISTS/NOT EXISTS are removed)
RULE {
    ?person ex:hasNoChildren true .
} WHERE {
    ?person a ex:Person .
    NOT {
        ?person ex:hasChild ?child .
    }
}
```

## Known Limitations (Deferred)

This implementation tracks the current (2026-07) [W3C SHACL 1.2 Rules](https://w3c.github.io/data-shapes/shacl12-rules/) spec. The following parts of the spec are **not yet implemented** and are deferred for a later iteration. They are known gaps, not bugs — a full audit and remediation record is in [SPEC-COMPLIANCE-AUDIT.md](SPEC-COMPLIANCE-AUDIT.md) (§6).

- **RDF 1.2 collection & reification syntax — parsed & desugared, but evaluation is gated by rdflib.** The SRL text parser now accepts blank-node property lists `[ … ]`, RDF collections `( … )`, reified triples `<< s p o >>` / reified-triple blocks, annotation blocks `{| … |}`, and reifiers `~` (alongside the triple-term form `<<( s p o )>>`), desugaring them to plain triples per RDF 1.2 Turtle §7. Two evaluation-time caveats remain, both rooted in the engine/rdflib rather than the parser:
  - **Triple terms cannot be materialized on the pinned rdflib.** The reification constructs desugar to `reifier rdf:reifies <<( s p o )>>`; because the pinned rdflib exposes no triple-term type, evaluating a rule **head** or **DATA** block that produces such a term raises a clear `UnrepresentableTripleTermError` (rather than an opaque failure). Collections `( … )` and blank-node lists `[ … ]` — which emit no triple terms — evaluate normally. Full support needs an rdflib release with RDF 1.2 triple terms.
  - **Blank nodes in a rule body are matched by label, not as existentials.** A `[ … ]` / `( … )` / `<< … >>` in a rule *body* desugars to labeled blank nodes, and the engine's `graphMatch` treats body blank nodes as concrete labels (the same is true of a hand-written `_:b` in a body), so they do not act as existential variables and typically match nothing. Use variables (`?x`) for body matching. This is pre-existing engine behavior, not specific to the desugaring.
- **Base-direction language literals.** `LANGDIR`, `STRLANGDIR`, and `hasLANGDIR` are dispatched but effectively no-ops because the pinned rdflib exposes no literal base-direction API. `hasLANG` and language tags work normally. Full support needs an rdflib release with base-direction literals (or a shim).
- **SRL/RDF concrete syntax coverage.** The `srl.rdf` reader parses the `srl:RuleSet` RDF encoding (rules, data, filters, assignments, negation, `sparql:*` operators) and a serializer (`srl.rdf.to_rdf_graph` / `serialize`) inverts it; RDF-side triple terms / collections mirror the text-syntax gaps above.
- **Minor SPARQL-fidelity edges.** A few evaluation corners still diverge from strict SPARQL semantics: relational comparison of incomparable operand types falls back to string ordering instead of raising a type error, and `xsd:float ÷ xsd:float` yields `xsd:decimal` rather than `xsd:float`.

### Opt-in rule-to-shape targeting extension (`--extensions`)

Beyond the spec, this project ships an **opt-in** rule-to-shape targeting feature (the `FOR ?v IN <shape>` clause, the `srl shacl` command, and an in-house SHACL 1.2 Core subset). It is **not part of the SRL spec** and is reachable only behind the `--extensions`/`-x` CLI flag (or `SRLParser(extensions=True)` / `RuleEngine(..., extensions=True)`). With the flag off, the parser and engine remain byte-for-byte spec-conformant. Exactly which SHACL constraints and targets the subset supports — and what it deliberately does not — is documented in the [SHACL Core support matrix](docs/shacl-core-support-matrix.md). A worked example is [`examples/12_shape_targeting.py`](examples/12_shape_targeting.py) (`srl shacl` walkthrough in [`examples/README.md`](examples/README.md)).

**Unsupported property paths** (also deferred, and *not* in the current spec): alternative `|`, transitive `+`/`*`, optional `?`, and negated property sets. Only sequence `a/b` and inverse `^a` paths are supported. Test cases exercising the unsupported forms are marked `xfail`.

## CLI Usage and Sample Output

This project provides a command-line interface (CLI) for parsing, analyzing, and evaluating SRL rules. The CLI is installed as the `srl` command when the package is installed (e.g. `pip install -e .`).

Basic CLI commands:

- `srl parse RULES_FILE` — Parse and validate a rules file and display an overview
- `srl analyze RULES_FILE [--show-layers]` — Analyze rules for stratification and dependencies
- `srl eval RULES_FILE DATA_FILE [-o OUTPUT] [--format FORMAT]` — Evaluate rules on an RDF data file and optionally write results
- `srl shacl RULES_FILE DATA_FILE --shapes SHAPES_FILE [-o OUTPUT]` — Evaluate rule-to-shape targeting (opt-in extension; see the [support matrix](docs/shacl-core-support-matrix.md))

Examples (PowerShell / pwsh):

1) Parse rules and show summary

```pwsh
srl parse examples/ancestor_rules.srl
```

Sample output:

```text
✓ Successfully parsed examples/ancestor_rules.srl

┌────────────────────────────────────┐
│ Rule Set Summary                   │
│ Rules: 2                           │
│ Data Blocks: 0                     │
│ Prefixes: 1                        │
└────────────────────────────────────┘

             Prefixes
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Prefix ┃ IRI                   ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ ex     │ <http://example.org/> │
└────────┴───────────────────────┘
                  Rules
┏━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ #    ┃ Head Templates ┃ Body Elements ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ 1    │ 1              │ 1             │
│ 2    │ 1              │ 1             │
└──────┴────────────────┴───────────────┘
```



2) Analyze a rule set and show stratification layers

```pwsh
srl analyze examples/ancestor_rules.srl --show-layers
```

Sample output:

```text
✓ Parsed examples/ancestor_rules.srl (2 rule(s))

Total strata: 1
Total rules: 2

Stratification Layers
└── Stratum 0 (2 rule(s))
    ├── Rule 1: ?grandparent <http://example.org/grandparentOf> ?grandchild .
    └── Rule 2: ?person <http://example.org/greatGrandparentOf> ?ggc .
```

```pwsh
srl -v analyze examples/ancestor_rules.srl --show-layers
```

Sample output:

```text
✓ Parsed examples/ancestor_rules.srl (2 rule(s))

Total strata: 1
Total rules: 2

Stratification Layers
└── Stratum 0 (2 rule(s))
    ├── Rule 1: ?grandparent <http://example.org/grandparentOf> ?grandchild .
    │   └── PATTERN: ?grandparent <http://example.org/parentOf>/<http://example.org/parentOf> ?grandchild .
    └── Rule 2: ?person <http://example.org/greatGrandparentOf> ?ggc .
        └── PATTERN: ?person <http://example.org/parentOf>/<http://example.org/parentOf>/<http://example.org/parentOf> ?ggc .
```

3) Evaluate rules on an RDF data file and show inferred triples

```pwsh
srl eval examples/ancestor_rules.srl examples/family_data.ttl
```

Sample output (summary):

```text
✓ Parsed examples/ancestor_rules.srl (2 rule(s))
✓ Loaded examples/family_data.ttl (3 triple(s), format: turtle)

┌────────────────────────────────────────┐
│ Evaluation Results                     │
│ Original triples: 3                    │
│ Result triples: 6                      │
│ Inferred triples: 3                    │
└────────────────────────────────────────┘

ℹ Use -o/--output to save results to a file.
```

You can save the resulting graph to a file with the `-o` option:

```pwsh
srl eval examples/ancestor_rules.srl examples/family_data.ttl -o results.ttl
```

Sample output when writing results:

```text
✓ Result written to results.ttl (6 triple(s))
```

4) Verbose mode shows extra details like AST, rule details, and provenance

```pwsh
srl -v parse examples/ancestor_rules.srl
srl -v eval examples/ancestor_rules.srl examples/family_data.ttl
```

Verbose output will include the rule details, body elements, and—when evaluating—the provenance table showing which rule inferred which triple.



