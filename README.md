# py-srl: Python SHACL 1.2 Rules (SRL) Parser and Evaluation Engine

A comprehensive Python implementation of the SHACL 1.2 Rules (Shape Rule Language - SRL) specification, providing parsing, validation, and evaluation capabilities for RDF rule-based reasoning.

## Table of Contents

- [Project Status](#project-status)
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Python API Usage](#python-api-usage)
- [Example Rules](#example-rules)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Dependencies](#dependencies)

## Project Status

✅ **COMPLETE** - Full implementation with all tests passing

This project implements the complete SHACL 1.2 Rules (SRL) specification with:

- ✅ Full grammar parser (135 productions, Lark LALR)
- ✅ Complete AST construction
- ✅ Expression evaluation (60+ built-in functions)
- ✅ Rule evaluation (triple patterns, FILTER, BIND, NOT)
- ✅ Stratification and fixpoint iteration
- ✅ All comprehensive tests passing

## Overview

The Shape Rule Language (SRL) is an extension of SHACL that provides a declarative rule language for deriving new RDF triples from existing ones. This project aims to implement:

1. **Parser** - Parse SRL rule syntax into abstract syntax trees
2. **Validator** - Check well-formedness and safety conditions
3. **Evaluator** - Execute rules with fixpoint semantics and stratification
4. **SHACL Integration** - Support SHACL TripleRules and SPARQLRules

## Features

### Syntax Support

- ✅ Three rule syntax forms: RULE/WHERE, IF/THEN, HeadTemplate :- BodyPattern
- ✅ Triple patterns and triple templates
- ✅ Negation (NOT {})
- ✅ Filters (FILTER)
- ✅ Assignments (BIND)
- ✅ Expression parsing and evaluation

### Evaluation

- ✅ Fixpoint iteration algorithm
- ✅ Stratification for safe negation
- ✅ Solution mappings and substitutions
- ✅ Expression evaluation (60+ SPARQL built-in functions)
- ✅ Graph pattern matching
- ✅ Blank node handling

### Parser

- ✅ Complete Lark LALR(1) grammar (135 productions)
- ✅ AST construction with frozen dataclasses
- ✅ Well-formedness validation
- ✅ Comprehensive error reporting

### API

- ✅ Python API for programmatic use
- ✅ RDF format support via rdflib (Turtle, N-Triples, RDF/XML, JSON-LD)

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

## Documentation

- [User Guide](docs/USER_GUIDE.md) - How to use py-srl
- [API Reference](docs/API.md) - Complete API documentation
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md) - Development plan and architecture
- [Specification Analysis](docs/SPECIFICATION_ANALYSIS.md) - SHACL rules analysis

## Architecture

```text
py-srl/
├── src/srl/
│   ├── parser/        # Grammar & parsing (Lark LALR)
│   │   ├── grammar.lark
│   │   ├── parser.py
│   │   └── transformer.py
│   ├── ast/           # Abstract syntax tree (frozen dataclasses)
│   │   └── nodes.py
│   ├── engine/        # Evaluation engine
│   │   ├── engine.py        # Main rule engine
│   │   ├── solutions.py     # Solution mappings
│   │   ├── expressions.py   # Expression evaluation
│   │   ├── rules.py         # Rule evaluation
│   │   └── stratification.py # Dependency analysis
│   └── rdf/           # RDF infrastructure
│       ├── graph.py
│       ├── namespace.py
│       └── nodes.py
├── tests/             # Comprehensive test suite
├── docs/              # Documentation
└── examples/          # Working examples
```

## Dependencies

### Core

- **rdflib** ≥7.0.0 - RDF graph manipulation and SPARQL
- **lark** ≥1.1.0 - Parser generation (LALR)

### Development

- **pytest** ≥7.0.0 - Testing framework
- **pytest-cov** ≥4.0.0 - Coverage reporting
- **black** ≥23.0.0 - Code formatting
- **mypy** ≥1.0.0 - Type checking
- **flake8** ≥6.0.0 - Linting

