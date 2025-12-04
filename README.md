# py-srl: Python SHACL 1.2 Rules (SRL) Parser and Evaluation Engine

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

```bash
# Run simple inference example
python examples/01_simple_inference.py

# Run transitive closure example
python examples/02_transitive_closure.py

# Run FILTER example
python examples/03_filter_conditions.py

# Run BIND/CONCAT example
python examples/04_bind_concat.py

# Run complete test suite
python -m pytest tests/test_complete.py -v
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

```sparql
PREFIX ex: <http://example.org/>

# RULE/WHERE form
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

# Datalog form
?x ex:ancestor ?z :- 
    ?x ex:parent ?y ,
    ?y ex:parent ?z .

# BIND expressions
RULE {
    ?person ex:fullName ?fullName .
} WHERE {
    ?person ex:firstName ?first .
    ?person ex:lastName ?last .
    BIND(CONCAT(?first, " ", ?last) AS ?fullName)
}

# Negation
RULE {
    ?person ex:hasNoChildren true .
} WHERE {
    ?person a ex:Person .
    NOT {
        ?person ex:hasChild ?child .
    }
}
```

## CLI Usage and Sample Output

This project provides a command-line interface (CLI) for parsing, analyzing, and evaluating SRL rules. The CLI is installed as the `srl` command when the package is installed (e.g. `pip install -e .`).

Basic CLI commands:

- `srl parse RULES_FILE` — Parse and validate a rules file and display an overview
- `srl analyze RULES_FILE [--show-layers]` — Analyze rules for stratification and dependencies
- `srl eval RULES_FILE DATA_FILE [-o OUTPUT] [--format FORMAT]` — Evaluate rules on an RDF data file and optionally write results
- `srl shacl` — Placeholder: SHACL shapes integration (not implemented yet)

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
│        │ <http://example.org/> │
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
✓ Successfully parsed examples/ancestor_rules.srl (2 rule(s))

Total strata: 1
Total rules: 2

Stratification Layers
└── Stratum 0 (2 rule(s))
    ├── Rule 1: ?grandparent <http://example.org/grandchildOf> ?grandchild .
    └── Rule 2: ?person <http://example.org/greatGrandparent> ?ggp .
```

```pwsh
srl -v analyze examples/ancestor_rules.srl --show-layers
```

Sample output:

```text
✓ Successfully parsed examples/ancestor_rules.srl (2 rule(s))

Total strata: 1
Total rules: 2

Stratification Layers
└── Stratum 0 (2 rule(s))
    ├── Rule 1: ?grandparent <http://example.org/grandchildOf> ?grandchild .
    │   └── PATTERN: ?grandchild <http://example.org/parentOf>/<http://example.org/parentOf> ?grandparent .
    └── Rule 2: ?person <http://example.org/greatGrandparent> ?ggp .
        └── PATTERN: ?person <http://example.org/parentOf>/<http://example.org/parentOf>/<http://example.org/parentOf> ?ggp .
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

Use -o/--output to save results to a file.
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



