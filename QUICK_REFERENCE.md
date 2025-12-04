# SHACL 1.2 Rules - Quick Reference

## Rule Syntax

### RULE/WHERE Form
```sparql
RULE { ?x ex:ancestor ?y . } WHERE { ?x ex:parent ?y . }
```

### IF/THEN Form
```sparql
IF { ?x ex:parent ?y . } THEN { ?x ex:ancestor ?y . }
```

### Datalog Form
```sparql
?x ex:ancestor ?y :- ?x ex:parent ?y .
```

## Basic Usage

```python
from rdflib import Graph, Namespace
from srl.parser import SRLParser
from srl.engine import RuleEngine

# Setup
EX = Namespace("http://example.org/")
graph = Graph()
graph.add((EX.Alice, EX.parent, EX.Bob))

# Parse rule
parser = SRLParser()
rule_set = parser.parse(rule_text)

# Evaluate
engine = RuleEngine(rule_set)
result = engine.evaluate(graph, inplace=False)
```

## Common Patterns

### FILTER
```sparql
FILTER (?age >= 18)
FILTER (?price > 100 && ?inStock = true)
```

### BIND
```sparql
BIND(CONCAT(?first, " ", ?last) AS ?fullName)
BIND(?price * 0.9 AS ?salePrice)
```

### NOT (Negation)
```sparql
?person a ex:Person .
NOT { ?person ex:hasChild ?child . }
```

### Recursive Rules
```sparql
# Base case
?x ex:ancestor ?y :- ?x ex:parent ?y .

# Recursive case
?x ex:ancestor ?z :- ?x ex:ancestor ?y , ?y ex:ancestor ?z .
```

## Operators

### Comparison
`=` `!=` `<` `>` `<=` `>=`

### Logical
`&&` (AND) `||` (OR) `!` (NOT)

### Arithmetic
`+` `-` `*` `/`

## Built-in Functions

### String
- `CONCAT(s1, s2, ...)` - Concatenate strings
- `STRLEN(s)` - String length
- `SUBSTR(s, start, len)` - Substring
- `UCASE(s)` / `LCASE(s)` - Change case
- `STRSTARTS(s, prefix)` - Check prefix
- `CONTAINS(s, sub)` - Check substring

### Numeric
- `ABS(n)` - Absolute value
- `ROUND(n)` / `CEIL(n)` / `FLOOR(n)` - Rounding

### RDF
- `STR(term)` - Convert to string
- `LANG(lit)` - Get language tag
- `DATATYPE(lit)` - Get datatype
- `IRI(str)` - Create IRI
- `BOUND(var)` - Check if bound

### Date/Time
- `NOW()` - Current datetime
- `YEAR(dt)` / `MONTH(dt)` / `DAY(dt)` - Extract components

## Running Code

### Set PYTHONPATH
```bash
# Linux/Mac
export PYTHONPATH=src:$PYTHONPATH

# Windows PowerShell
$env:PYTHONPATH="src"
```

### Run Examples
```bash
python examples/01_simple_inference.py
python examples/02_transitive_closure.py
```

### Run Tests
```bash
.venv/Scripts/python.exe tests/test_complete.py  # Windows
.venv/bin/python tests/test_complete.py          # Linux/Mac
```

## Documentation

- [README.md](README.md) - Project overview
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - Full user guide
- [docs/API.md](docs/API.md) - API reference
- [examples/README.md](examples/README.md) - Example documentation

## Troubleshooting

### Import Error
```python
# Add to PYTHONPATH
import sys
sys.path.insert(0, 'src')
```

### No Inferred Triples
- Check input data matches patterns
- Verify variable names
- Test patterns separately
- Check FILTER conditions

### Parse Error
- Check syntax (commas, dots, brackets)
- Verify PREFIX declarations
- Variables start with `?`

## Quick Test

```python
from rdflib import Graph, Namespace, Literal
from srl.parser import SRLParser
from srl.engine import RuleEngine

EX = Namespace("http://example.org/")
g = Graph()
g.add((EX.Alice, EX.age, Literal(25)))

rule = """
PREFIX ex: <http://example.org/>
RULE { ?p ex:adult true . } WHERE { ?p ex:age ?a . FILTER (?a >= 18) }
"""

parser = SRLParser()
rs = parser.parse(rule)
result = RuleEngine(rs).evaluate(g, inplace=False)

print(f"{len(result)} triples (expected 2)")
assert (EX.Alice, EX.adult, Literal(True)) in result
print("✅ Working!")
```

## See Also

- SHACL Spec: https://www.w3.org/TR/shacl-af/
- RDFLib Docs: https://rdflib.readthedocs.io/
- SPARQL Spec: https://www.w3.org/TR/sparql11-query/
