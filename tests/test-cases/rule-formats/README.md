# Rule Format Examples

This directory contains comprehensive examples demonstrating the two rule formats supported by SHACL 1.2 Rules (Shape Rule Language).

## Rule Formats

According to the current SHACL 1.2 Rules grammar (productions [11]-[13]), rules can be written in two equivalent forms. The Datalog `head :- body` form of earlier drafts has been **removed** and no longer parses. `RULE` also accepts an optional IRI naming the rule: `RULE iri? { head } WHERE { body }`.

### 1. RULE/WHERE Form (Rule1)

```sparql
RULE {
    <head-template>
} WHERE {
    <body-pattern>
}
```

**Example:** `rule-format-001.srl`, `rule-format-004.srl`, `rule-format-007.srl`, `rule-format-010.srl`, `rule-format-012.srl`

### 2. IF/THEN Form (Rule2)

```sparql
IF {
    <body-pattern>
} THEN {
    <head-template>
}
```

**Example:** `rule-format-002.srl`, `rule-format-005.srl`, `rule-format-008.srl`

## Example Files

| File | Description | Rule Format | Features |
|------|-------------|-------------|----------|
| `rule-format-001` | Simple property inference | RULE/WHERE | Basic single pattern |
| `rule-format-002` | Type inference | IF/THEN | Multiple body patterns |
| `rule-format-003` | Sibling inference | RULE/WHERE | FILTER condition |
| `rule-format-004` | Grandparent relationship | RULE/WHERE | Chained patterns |
| `rule-format-005` | Adult classification | IF/THEN | FILTER with comparison |
| `rule-format-006` | Full name calculation | RULE/WHERE | SET with CONCAT |
| `rule-format-007` | Multiple head triples | RULE/WHERE | Multiple inferences |
| `rule-format-008` | Childless detection | IF/THEN | Negation (NOT) |
| `rule-format-009` | Type hierarchy | RULE/WHERE | Using 'a' keyword |
| `rule-format-010` | Area calculation | RULE/WHERE | Arithmetic operations |
| `rule-format-011` | Mixed formats | RULE/WHERE + IF/THEN | Multiple rules in one file |
| `rule-format-012` | Email domain extraction | RULE/WHERE | String functions (STRAFTER) |

## Running the Examples

Each example consists of two files:
- `.srl` - The rule definition
- `.ttl` - The input data and expected results

To run an example:

```python
from srl.parser import SRLParser
from srl.engine import RuleEngine
from rdflib import Graph

# Parse rules
parser = SRLParser()
with open('rule-format-001.srl') as f:
    rule_set = parser.parse(f.read())

# Load data
graph = Graph()
graph.parse('rule-format-001.ttl', format='turtle')

# Evaluate
engine = RuleEngine(rule_set)
result = engine.evaluate(graph, inplace=False)

# Check results
for s, p, o in result:
    print(f"{s} {p} {o}")
```

## Key Concepts

### Head Template
The consequent part of the rule - triples to be inferred when the body matches.

### Body Pattern
The antecedent part of the rule - patterns that must match in the data graph.

### Body Elements
- **Triple Patterns**: Match existing triples (e.g., `?x ex:parent ?y`)
- **FILTER**: Conditions that must be true (e.g., `FILTER(?age >= 18)`)
- **SET**: Variable assignments (e.g., `SET(?sum := ?x + ?y)`)
- **NOT**: Negation-as-failure (e.g., `NOT { ?x ex:hasChild ?y }`)

## Grammar References

These examples correspond to the following grammar productions:

- **[11]** `Rule ::= Rule1 | Rule2 | Declaration`
- **[12]** `Rule1 ::= 'RULE' iri? HeadTemplate 'WHERE' BodyPattern`
- **[13]** `Rule2 ::= 'IF' BodyPattern 'THEN' HeadTemplate`

See the [SHACL 1.2 Rules specification](https://w3c.github.io/data-shapes/shacl12-rules/#shapes-rules-grammar) for complete grammar details.
