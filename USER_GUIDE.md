# SHACL 1.2 Rules - User Guide

## Introduction

The Shape Rule Language (SRL) is a declarative rule language for deriving new RDF triples from existing ones. This implementation provides a complete Python-based parser and evaluation engine.

## Rule Syntax

SRL supports two equivalent syntax forms. (The Datalog `head :- body` form of
earlier drafts has been removed and no longer parses.)

### 1. RULE/WHERE Form

```sparql
PREFIX ex: <http://example.org/>

RULE {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}
```

`RULE` optionally accepts an IRI that names the rule:

```sparql
RULE ex:AncestorRule {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}
```

### 2. IF/THEN Form

```sparql
IF {
    ?x ex:parent ?y .
} THEN {
    ?x ex:ancestor ?y .
}
```

## Basic Usage

### 1. Import Required Modules

```python
from rdflib import Graph, Namespace, Literal
from srl.parser import SRLParser
from srl.engine import RuleEngine
```

### 2. Create RDF Data

```python
# Define namespace
EX = Namespace("http://example.org/")

# Create graph
graph = Graph()
graph.bind("ex", EX)

# Add triples
graph.add((EX.Alice, EX.parent, EX.Bob))
graph.add((EX.Bob, EX.parent, EX.Charlie))
```

### 3. Define Rules

```python
rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}
"""
```

### 4. Parse and Evaluate

```python
# Parse rules
parser = SRLParser()
rule_set = parser.parse(rule_text)

# Create engine
engine = RuleEngine(rule_set)

# Evaluate
result_graph = engine.evaluate(graph, inplace=False)
```

### 5. Access Results

```python
# Query results
for s, p, o in result_graph:
    print(f"{s} {p} {o}")

# Check specific triple
if (EX.Alice, EX.ancestor, EX.Bob) in result_graph:
    print("Triple found!")
```

## Advanced Features

### FILTER Conditions

Filter solution mappings based on conditions:

```sparql
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:isAdult true .
} WHERE {
    ?person ex:age ?age .
    FILTER (?age >= 18)
}
```

**Supported Operators:**

- Comparison: `=`, `!=`, `<`, `>`, `<=`, `>=`
- Logical: `&&` (AND), `||` (OR), `!` (NOT)
- Arithmetic: `+`, `-`, `*`, `/`

### SET Assignments

Assign new variables with computed values. (The old `BIND(expr AS ?var)` syntax
has been replaced by `SET(?var := expr)`.)

```sparql
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:fullName ?fullName .
} WHERE {
    ?person ex:firstName ?first .
    ?person ex:lastName ?last .
    SET(?fullName := CONCAT(?first, " ", ?last))
}
```

The assignment variable must be **new** (not already bound), and every variable
used in the expression must already be bound by an earlier body element.

Built-in functions are exactly the SHACL 1.2 Rules spec list (production [121]).
Notably, `BOUND`, `RAND`, `MD5`, `SHA1`, `SHA256`, `SHA384`, `SHA512`,
`COALESCE`, and `EXISTS`/`NOT EXISTS` are **not** included and do not parse.

### Negation (NOT)

Negation-as-failure for closed-world reasoning:

```sparql
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:hasNoChildren true .
} WHERE {
    ?person a ex:Person .
    NOT {
        ?person ex:hasChild ?child .
    }
}
```

**Safety Requirement:** Variables in NOT clause must appear in positive patterns before the NOT.

### Recursive Rules

Define transitive closure with recursive rules:

```sparql
PREFIX ex: <http://example.org/>

# Base case
RULE {
    ?x ex:ancestor ?y .
} WHERE {
    ?x ex:parent ?y .
}

# Recursive case
RULE {
    ?x ex:ancestor ?z .
} WHERE {
    ?x ex:ancestor ?y .
    ?y ex:ancestor ?z .
}
```

The engine automatically handles:
- **Stratification**: Rules are organized into evaluation layers
- **Fixpoint Iteration**: Rules repeat until no new triples are derived
- **Termination**: Guaranteed for safe rules

## Rule Semantics

### Solution Mappings

Rules work by finding **solution mappings** - assignments of RDF terms to variables that make the body pattern true.

Example:
```
Body: ?x ex:parent ?y
Data: ex:Alice ex:parent ex:Bob

Solution: { ?x → ex:Alice, ?y → ex:Bob }
```

### Pattern Matching

Triple patterns match against the graph:

```sparql
?person ex:age ?age .
```

Matches all triples with predicate `ex:age`, binding subject to `?person` and object to `?age`.

### Expression Evaluation

Expressions are evaluated with variable bindings:

```sparql
?person ex:age ?age .
FILTER (?age >= 18)
```

For each solution mapping, `?age >= 18` is evaluated. If true, the mapping is kept; otherwise discarded.

### Head Instantiation

The rule head is instantiated with each solution mapping:

```
Head: ?person ex:isAdult true
Mapping: { ?person → ex:Alice }
Result: ex:Alice ex:isAdult true
```

## Best Practices

### 1. Use Meaningful Variable Names

```sparql
# Good
?person ex:hasParent ?parent .

# Avoid
?x ex:hasParent ?y .
```

### 2. Order Patterns for Efficiency

Place more selective patterns first:

```sparql
# Better
?person ex:country ex:USA .      # More selective
?person ex:age ?age .

# Worse
?person ex:age ?age .
?person ex:country ex:USA .
```

### 3. Use FILTER After Pattern Matching

```sparql
# Efficient
?person ex:age ?age .
FILTER (?age >= 18)

# Less efficient (conceptually)
FILTER (?age >= 18)
?person ex:age ?age .
```

### 4. Avoid Unsafe Negation

Variables in NOT must be bound first:

```sparql
# Safe
?person a ex:Person .
NOT { ?person ex:hasChild ?child . }

# Unsafe (error)
NOT { ?person ex:hasChild ?child . }
?person a ex:Person .
```

### 5. Test with Small Data First

Develop rules on small test graphs before running on large datasets.

## Common Patterns

### Property Transitivity

```sparql
# Base case
RULE { ?x ex:connected ?y } WHERE { ?x ex:directLink ?y }

# Transitive case
RULE { ?x ex:connected ?z } WHERE {
    ?x ex:connected ?y .
    ?y ex:connected ?z .
}
```

Transitivity can also be declared directly: `TRANSITIVE(ex:connected)`.

### Property Symmetry

```sparql
RULE { ?y ex:knows ?x } WHERE { ?x ex:knows ?y }
```

Symmetry can also be declared directly (postfix): `(ex:knows) SYMMETRIC`.

### Property Inversion

```sparql
RULE { ?child ex:hasParent ?parent } WHERE { ?parent ex:hasChild ?child }
```

Inversion can also be declared directly: `INVERSE(ex:hasChild, ex:hasParent)`.

### Class Subsumption

```sparql
RULE { ?x a ex:Animal } WHERE { ?x a ex:Dog }
RULE { ?x a ex:LivingThing } WHERE { ?x a ex:Animal }
```

### Conditional Classification

```sparql
RULE { ?person a ex:Senior } WHERE {
    ?person a ex:Person .
    ?person ex:age ?age .
    FILTER (?age >= 65)
}
```

## Troubleshooting

### Parse Errors

**Error:** `Unexpected token at line X`

- Check syntax carefully (commas, dots, brackets)
- Ensure PREFIX declarations are before rules
- Verify variable names start with `?`

### No Triples Inferred

- Verify input data matches rule patterns
- Check variable bindings are consistent
- Test rule body pattern separately
- Add debug output to inspect solution mappings

### Stratification Errors

**Error:** `Stratification condition violated: a recursive dependency involves a closed dependency`

The stratification condition forbids any recursive (cyclic) dependency that
involves a **closed** dependency. A dependency is closed when it arises through
a `NOT { ... }` negation element, an assignment (`SET`), or a blank node in the
rule head. In practice this means a rule must not negate (nor assign from) a
predicate that it, transitively, also produces.

- Ensure variables in NOT appear in positive patterns first
- Avoid negating a rule's own head predicate (use a distinct predicate)
- Break complex rules into multiple simpler rules
- Check for circular dependencies through negation or assignment

### Performance Issues

- Reduce rule complexity
- Add more specific patterns to limit solution mappings
- Use FILTER early to eliminate mappings
- Consider indexing for very large graphs

## Examples

See the `examples/` directory (and its `README.md`) for complete working
examples. Each numbered script is standalone and isolates one feature:

- `01_simple_inference.py` - the parse → evaluate → read cycle
- `02_rule_forms.py` - `RULE`/`WHERE`, `IF`/`THEN`, and named rules
- `03_recursion_transitive.py` - recursive rules and fixpoint iteration
- `04_filter_conditions.py` - `FILTER` with comparison, `&&`, and `IN`
- `05_set_and_functions.py` - `SET` assignments and built-in functions
- `06_negation.py` - closed-world negation with `NOT { … }`
- `07_property_paths.py` - sequence `a/b` and inverse `^a` paths
- `08_declarations.py` - `TRANSITIVE`/`SYMMETRIC`/`INVERSE` declarations
- `09_data_blocks.py` - self-contained rule sets with `DATA { … }`
- `10_rdf12_syntax.py` - RDF 1.2 collections, blank-node lists, reification
- `11_api_provenance.py` - provenance, stratification layers, `results_only`

Run any script with `uv run python examples/<name>.py`. An interactive tour of
the API is in `examples/playground.ipynb`.

### Command-Line Interface

The `srl` CLI wraps the same engine. Against the bundled example files:

```bash
srl parse   examples/ancestor_rules.srl                          # parse + summary
srl analyze examples/ancestor_rules.srl --show-layers            # stratification layers
srl eval    examples/ancestor_rules.srl examples/family_data.ttl -o out.ttl
srl -v eval examples/ancestor_rules.srl examples/family_data.ttl # + provenance table
```

See `examples/README.md` for the full CLI walkthrough.
