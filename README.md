# py-srl: Python SHACL 1.2 Rules (SRL) Parser and Evaluation Engine

A comprehensive Python implementation of the SHACL 1.2 Rules (Shape Rule Language - SRL) specification, providing parsing, validation, and evaluation capabilities for RDF rule-based reasoning.

## Table of Contents

- [py-srl: Python SHACL 1.2 Rules (SRL) Parser and Evaluation Engine](#py-srl-python-shacl-12-rules-srl-parser-and-evaluation-engine)
  - [Table of Contents](#table-of-contents)
  - [Project Status](#project-status)
  - [Overview](#overview)
  - [Features (Planned)](#features-planned)
    - [Syntax Support](#syntax-support)
    - [Evaluation](#evaluation)
    - [SHACL Integration](#shacl-integration)
    - [API \& Tools](#api--tools)
  - [Installation (Future)](#installation-future)
  - [Quick Start](#quick-start)
    - [Running Examples](#running-examples)
  - [Quick Start (Future)](#quick-start-future)
    - [Command Line](#command-line)
    - [Python API](#python-api)
  - [Example](#example)
    - [Rule Syntax](#rule-syntax)
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

## Features (Planned)

### Syntax Support
- ✅ Three rule syntax forms: RULE/WHERE, IF/THEN, HeadTemplate :- BodyPattern
- ✅ Triple patterns and triple templates
- ✅ Negation (NOT {})
- ✅ Filters (FILTER)
- ✅ Assignments (BIND)
- ✅ Complex graph patterns (UNION, OPTIONAL)

### Evaluation
- ✅ Fixpoint iteration algorithm
- ✅ Stratification for safe negation
- ✅ Solution mappings and substitutions
- ✅ Expression evaluation
- ✅ Blank node handling

### SHACL Integration
- ✅ Parse SHACL shapes graphs
- ✅ Extract sh:TripleRule and sh:SPARQLRule
- ✅ Evaluate node expressions
- ✅ Target and condition support

### API & Tools
- ✅ Python API for programmatic use
- ✅ Command-line interface
- ✅ RDF format support (Turtle, N-Triples, RDF/XML, JSON-LD)

## Installation (Future)

```bash
pip install py-srl
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

## Quick Start (Future)

### Command Line

```bash
# Parse and validate rules
srl parse rules.srl

# Evaluate rules on data
srl eval rules.srl data.ttl -o output.ttl

# Analyze rule dependencies
srl analyze rules.srl --show-layers
```

### Python API

```python
from srl import RuleSet, RDFGraph

# Parse rules
with open('rules.srl') as f:
    ruleset = RuleSet.parse(f.read())

# Load data
graph = RDFGraph.load('data.ttl')

# Evaluate
result = ruleset.evaluate(graph)

# Export
result.save('output.ttl', format='turtle')
```

## Example

### Rule Syntax

```sparql
PREFIX ex: <http://example.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

# RULE/WHERE form
RULE ?person rdf:type ex:Adult
WHERE {
    ?person rdf:type ex:Person .
    ?person ex:age ?age .
    FILTER (?age >= 18)
}

# IF/THEN form
IF {
    ?x ex:parent ?y .
    ?y ex:parent ?z .
}
THEN {
    ?x ex:grandparent ?z .
}

# Datalog form
?person ex:hasUncle ?uncle :-
    ?person ex:parent ?parent ,
    ?parent ex:sibling ?uncle ,
    ?uncle ex:gender ex:Male .
```

## Documentation

- [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md) - Detailed development plan
- [Specification Analysis](SPECIFICATION_ANALYSIS.md) - SHACL-AF rules analysis
- [Extraction Template](SPECIFICATION_EXTRACTION_TEMPLATE.md) - SRL spec extraction guide

## Architecture

```
py-srl/
├── src/srl/
│   ├── rdf/           # RDF infrastructure
│   ├── parser/        # Grammar & parsing
│   ├── ast/           # Abstract syntax tree
│   ├── model/         # Semantic model
│   ├── validation/    # Well-formedness checks
│   ├── analysis/      # Dependency & stratification
│   ├── evaluation/    # Evaluation engine
│   ├── shacl/         # SHACL integration
│   └── cli/           # Command-line interface
├── tests/             # Test suite
├── docs/              # Documentation
└── examples/          # Example files
```

## Dependencies

- **rdflib** - RDF graph manipulation and SPARQL
- **pyparsing** or **lark** - Parser generation (TBD)
- **click** - CLI framework

