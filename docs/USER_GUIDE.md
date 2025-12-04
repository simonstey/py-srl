# SHACL 1.2 Rules - User Guide

## Introduction

The Shape Rule Language (SRL) is a declarative rule language for deriving new RDF triples from existing ones. This implementation provides a complete Python-based parser and evaluation engine.

## Rule Syntax

SRL supports three equivalent syntax forms:

### 1. RULE/WHERE Form

```sparql
PREFIX ex: <http://example.org/>

RULE {
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

### 3. Datalog Form

```sparql
?x ex:ancestor ?y :- ?x ex:parent ?y .
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

### BIND Expressions

Create new variables with computed values:

```sparql
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:fullName ?fullName .
} WHERE {
    ?person ex:firstName ?first .
    ?person ex:lastName ?last .
    BIND(CONCAT(?first, " ", ?last) AS ?fullName)
}
```

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
?x ex:connected ?y :- ?x ex:directLink ?y .

# Transitive case
?x ex:connected ?z :- ?x ex:connected ?y , ?y ex:connected ?z .
```

### Property Symmetry

```sparql
?y ex:knows ?x :- ?x ex:knows ?y .
```

### Property Inversion

```sparql
?child ex:hasParent ?parent :- ?parent ex:hasChild ?child .
```

### Class Subsumption

```sparql
?x a ex:Animal :- ?x a ex:Dog .
?x a ex:LivingThing :- ?x a ex:Animal .
```

### Conditional Classification

```sparql
?person a ex:Senior :- 
    ?person a ex:Person ,
    ?person ex:age ?age ,
    FILTER (?age >= 65) .
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

**Error:** `Cannot stratify rules: unsafe negation`

- Ensure variables in NOT appear in positive patterns first
- Break complex rules into multiple simpler rules
- Check for circular dependencies through negation

### Performance Issues

- Reduce rule complexity
- Add more specific patterns to limit solution mappings
- Use FILTER early to eliminate mappings
- Consider indexing for very large graphs

## Examples

See the `examples/` directory for complete working examples:

- `01_simple_inference.py` - Basic rule inference
- `02_transitive_closure.py` - Recursive rules
- `03_filter_conditions.py` - FILTER usage
- `04_bind_concat.py` - BIND and string operations
