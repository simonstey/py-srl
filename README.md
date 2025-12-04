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


