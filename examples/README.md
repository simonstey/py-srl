# SHACL 1.2 Rules - Examples

This directory contains working examples demonstrating the key features of the SHACL 1.2 Rules implementation.

## Running Examples

Each example is a standalone Python script that can be run directly:

```bash
python examples/01_simple_inference.py
python examples/02_transitive_closure.py
python examples/03_filter_conditions.py
python examples/04_bind_concat.py
```

## Example Descriptions

### 1. Simple Inference (`01_simple_inference.py`)

**Concept:** Basic rule-based inference

Demonstrates how to:
- Create RDF data with rdflib
- Define a simple SHACL rule
- Parse the rule with SRLParser
- Evaluate rules with RuleEngine
- Access inferred triples

**Rule:** `parent(x, y) → ancestor(x, y)`

**Input:** 2 parent relationships  
**Output:** 2 ancestor relationships inferred

### 2. Transitive Closure (`02_transitive_closure.py`)

**Concept:** Recursive rules with fixpoint iteration

Demonstrates how to:
- Define multiple rules in a rule set
- Use recursive rules for transitive closure
- Handle multi-level inference

**Rules:**
1. Base case: `parent(x, y) → ancestor(x, y)`
2. Recursive: `ancestor(x, y) ∧ ancestor(y, z) → ancestor(x, z)`

**Input:** 3 parent relationships (Alice→Bob→Charlie→Diana)  
**Output:** 6 ancestor relationships inferred (complete transitive closure)

**Stratification:** The engine automatically stratifies these rules and performs fixpoint iteration.

### 3. FILTER Conditions (`03_filter_conditions.py`)

**Concept:** Conditional inference based on data values

Demonstrates how to:
- Use FILTER to apply conditions
- Compare numeric values
- Selectively infer based on criteria

**Rule:** `age(person, n) ∧ n >= 18 → isAdult(person)`

**Input:** 4 people with ages (25, 16, 30, 12)  
**Output:** 2 adult classifications (age >= 18)

**FILTER:** Only people with age >= 18 are marked as adults.

### 4. BIND and String Operations (`04_bind_concat.py`)

**Concept:** Computed values with BIND expressions

Demonstrates how to:
- Use BIND to create new variables
- Call built-in functions (CONCAT)
- Generate derived data

**Rule:** `firstName(p, f) ∧ lastName(p, l) → fullName(p, CONCAT(f, " ", l))`

**Input:** 2 people with first and last names  
**Output:** 2 full name triples generated

**Built-in Function:** CONCAT combines strings with separator.

## Common Patterns

### Creating RDF Data

```python
from rdflib import Graph, Namespace, Literal

# Define namespace
EX = Namespace("http://example.org/")

# Create graph
graph = Graph()
graph.bind("ex", EX)

# Add triples
graph.add((EX.Alice, EX.age, Literal(25)))
```

### Defining Rules

```python
rule_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?person ex:isAdult true .
} WHERE {
    ?person ex:age ?age .
    FILTER (?age >= 18)
}
"""
```

### Parsing and Evaluation

```python
from srl.parser import SRLParser
from srl.engine import RuleEngine

# Parse
parser = SRLParser()
rule_set = parser.parse(rule_text)

# Evaluate
engine = RuleEngine(rule_set)
result = engine.evaluate(graph, inplace=False)
```

### Accessing Results

```python
# Iterate over results
for s, p, o in result:
    print(f"{s} {p} {o}")

# Check specific triple
if (EX.Alice, EX.isAdult, Literal(True)) in result:
    print("Alice is an adult")

# Query specific predicate
for s, p, o in result:
    if p == EX.fullName:
        print(f"{s} has full name: {o}")
```

## Extending Examples

### Add More Built-in Functions

Available functions include:
- String: STRLEN, SUBSTR, UCASE, LCASE, STRSTARTS, STRENDS, CONTAINS
- Numeric: ABS, ROUND, CEIL, FLOOR, RAND
- Date/Time: NOW, YEAR, MONTH, DAY
- Hash: MD5, SHA1, SHA256

Example:
```sparql
BIND(UCASE(?name) AS ?upperName)
BIND(STRLEN(?text) AS ?length)
```

### Combine Multiple Conditions

```sparql
FILTER (?age >= 18 && ?age < 65)
FILTER (?price > 100 || ?onSale = true)
```

### Use Complex Patterns

```sparql
RULE {
    ?x ex:friend ?z .
} WHERE {
    ?x ex:knows ?y .
    ?y ex:knows ?z .
    FILTER (?x != ?z)
}
```

## Troubleshooting

### Import Errors

Ensure py-srl is installed or add to PYTHONPATH:

```bash
export PYTHONPATH=/path/to/py-srl/src:$PYTHONPATH
```

Or run from project root:

```bash
cd py-srl
python examples/01_simple_inference.py
```

### No Output

Check that:
1. Input data matches rule patterns
2. Variables are consistent between body and head
3. PREFIX declarations match data namespaces

### Unexpected Results

Enable debugging:

```python
# Print solution mappings
for elem in rule.body.elements:
    print(f"Element: {elem}")

# Print intermediate steps
print(f"Input: {len(graph)} triples")
print(f"Output: {len(result)} triples")
```

## Next Steps

After running these examples, see:

- [User Guide](../docs/USER_GUIDE.md) - Comprehensive documentation
- [API Reference](../docs/API.md) - Detailed API documentation
- [Tests](../tests/test_complete.py) - More complex examples

## Questions?

For more information, see the main [README](../README.md) or browse the [documentation](../docs/).
