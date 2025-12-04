# Test Suite

Comprehensive tests for the SHACL 1.2 Rules implementation.

## Running Tests

### All Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=srl --cov-report=html

# Run with verbose output
python -m pytest tests/ -vv
```

### Specific Tests

```bash
# Run comprehensive test suite
python -m pytest tests/test_complete.py -v

# Run individual test script
python tests/test_complete.py
```

## Test Files

### `test_complete.py`

**Main comprehensive test suite** - Tests all core functionality:

1. **Test 1: Simple Inference**
   - Basic parent→ancestor rule
   - Tests: pattern matching, solution mappings, head instantiation
   - Expected: 2 triples inferred

2. **Test 2: Transitive Closure**
   - Two recursive rules for ancestor relationships
   - Tests: stratification, fixpoint iteration, recursion
   - Expected: 6 triples inferred (complete transitive closure)

3. **Test 3: FILTER Conditions**
   - Numeric comparison filtering (age >= 18)
   - Tests: expression evaluation, comparison operators, filtering
   - Expected: 2 adults identified, 1 child filtered out

4. **Test 4: BIND/CONCAT**
   - String concatenation for full names
   - Tests: BIND expressions, built-in functions, variable assignment
   - Expected: 2 full name triples generated

**Status:** ✅ All tests passing

### `test_rdf_graph.py`

Basic RDF graph operations and rdflib integration.

### Debug Scripts

Located in `tests/` for troubleshooting specific features:

- `debug_parser.py` - Parser output inspection
- `debug_transform.py` - AST transformation debugging
- `test_filter.py` - FILTER evaluation testing
- `test_bind.py` - BIND expression testing
- `test_ast_filter.py` - AST structure for FILTER
- `test_datatypes.py` - RDF literal datatype testing
- `test_ebv.py` - Effective boolean value testing

## Test Coverage

### Parser

- ✅ PREFIX declarations
- ✅ RULE/WHERE syntax
- ✅ Triple patterns
- ✅ FILTER conditions
- ✅ BIND assignments
- ✅ Variables, IRIs, literals
- ✅ Comparison operators (=, !=, <, >, <=, >=)
- ✅ Built-in functions (CONCAT, STR, etc.)

### AST

- ✅ RuleSet construction
- ✅ Rule with head and body
- ✅ TriplePattern nodes
- ✅ ConditionExpression nodes
- ✅ Assignment nodes
- ✅ BinaryOp expressions
- ✅ Variable, IRI, Literal terms

### Engine

- ✅ Solution mapping creation
- ✅ Pattern matching against graph
- ✅ Solution mapping join/merge
- ✅ Expression evaluation
- ✅ FILTER evaluation with EBV
- ✅ BIND evaluation
- ✅ Head instantiation
- ✅ Fixpoint iteration
- ✅ Stratification

### Built-in Functions

Tested functions:
- ✅ CONCAT - String concatenation
- ✅ Comparison operators (>=, <=, etc.)
- ✅ Boolean logic (&&, ||, !)
- ✅ Arithmetic operators (+, -, *, /)

Additional built-ins implemented (60+ total):
- String: STR, STRLEN, SUBSTR, UCASE, LCASE, STRSTARTS, STRENDS, CONTAINS, REPLACE
- Numeric: ABS, ROUND, CEIL, FLOOR, RAND
- RDF: LANG, DATATYPE, IRI, BNODE, STRDT, STRLANG
- Date/Time: NOW, YEAR, MONTH, DAY, HOURS, MINUTES, SECONDS
- Hash: MD5, SHA1, SHA256, SHA384, SHA512

## Test Data

Tests use simple, focused datasets:

```python
# Example test data
EX.Alice, EX.parent, EX.Bob
EX.Bob, EX.parent, EX.Charlie

# Ages for filtering
EX.Alice, EX.age, Literal(25)
EX.Bob, EX.age, Literal(16)

# Names for BIND
EX.Person1, EX.firstName, Literal("John")
EX.Person1, EX.lastName, Literal("Doe")
```

## Writing Tests

### Basic Test Structure

```python
from rdflib import Graph, Namespace, Literal
from srl.parser import SRLParser
from srl.engine import RuleEngine

def test_my_feature():
    # Setup
    EX = Namespace("http://example.org/")
    graph = Graph()
    graph.add((EX.Alice, EX.age, Literal(25)))
    
    # Define rule
    rule_text = """
    PREFIX ex: <http://example.org/>
    
    RULE {
        ?person ex:isAdult true .
    } WHERE {
        ?person ex:age ?age .
        FILTER (?age >= 18)
    }
    """
    
    # Parse and evaluate
    parser = SRLParser()
    rule_set = parser.parse(rule_text)
    engine = RuleEngine(rule_set)
    result = engine.evaluate(graph, inplace=False)
    
    # Assert
    assert (EX.Alice, EX.isAdult, Literal(True)) in result
```

### Testing Guidelines

1. **Use clear, descriptive test names**
   ```python
   def test_filter_with_numeric_comparison():
   def test_bind_with_string_concatenation():
   ```

2. **Keep tests focused and independent**
   - One feature per test
   - No shared state between tests
   - Use fresh graphs for each test

3. **Test both positive and negative cases**
   ```python
   assert expected_triple in result  # Should be inferred
   assert unexpected_triple not in result  # Should not be inferred
   ```

4. **Add comments for complex rules**
   ```python
   # Test transitive closure: A→B→C should infer A→C
   ```

5. **Use meaningful test data**
   ```python
   # Good: semantic names
   graph.add((EX.Alice, EX.parent, EX.Bob))
   
   # Avoid: generic names
   graph.add((EX.x1, EX.p1, EX.x2))
   ```

## Debugging Failed Tests

### 1. Check Parse Tree

```python
parser = SRLParser()
rule_set = parser.parse(rule_text)
print(f"Parsed {len(rule_set.rules)} rules")
print(f"Body elements: {len(rule_set.rules[0].body.elements)}")
```

### 2. Inspect Solution Mappings

Add debug output in `src/srl/engine/rules.py`:

```python
def eval_rule_body(rule, graph, active_graph):
    omega = [SolutionMapping(bindings={})]
    
    for element in rule.body.elements:
        print(f"Processing: {element}")
        omega = eval_body_element(element, omega, graph, active_graph)
        print(f"Solutions: {len(omega)}")
    
    return omega
```

### 3. Check Expression Evaluation

```python
from srl.engine.expressions import eval_expr, effective_boolean_value

# Test expression
expr = parse_expression("?age >= 18")
mu = SolutionMapping({'age': Literal(25)})
result = eval_expr(expr, mu)
print(f"Result: {result}, EBV: {effective_boolean_value(result)}")
```

### 4. Verify Graph Contents

```python
print(f"Input graph: {len(graph)} triples")
for s, p, o in graph:
    print(f"  {s} {p} {o}")

print(f"Result graph: {len(result)} triples")
for s, p, o in result:
    if (s, p, o) not in graph:
        print(f"  INFERRED: {s} {p} {o}")
```

## Continuous Integration

Tests are designed to run in CI environments:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    pip install -r requirements-dev.txt
    python -m pytest tests/ -v --cov=srl
```

## Performance Benchmarks

Current performance (approximate):

- Simple inference: <10ms
- Transitive closure (6 triples): <50ms
- FILTER with 3 comparisons: <20ms
- BIND with CONCAT (2 people): <15ms

## Future Tests

Planned additions:

- [ ] NOT (negation) tests
- [ ] Complex expression tests
- [ ] Large graph performance tests
- [ ] Error handling tests
- [ ] Edge case tests (empty graphs, unbound variables)
- [ ] W3C test suite integration

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [rdflib Testing](https://rdflib.readthedocs.io/en/stable/testing.html)
- [Python unittest](https://docs.python.org/3/library/unittest.html)

---

**All tests passing ✅**

The test suite validates the complete implementation of SHACL 1.2 Rules functionality.
