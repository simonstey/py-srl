# SHACL Core support matrix (opt-in targeting extension)

> **This is not part of the SRL spec.** The rule-to-shape targeting feature and
> the in-house SHACL 1.2 Core subset it relies on are an **opt-in extension**,
> enabled only with the `--extensions`/`-x` CLI flag (or `SRLParser(extensions=True)`
> / `RuleEngine(..., extensions=True)`). With the flag off, the parser and engine
> stay byte-for-byte spec-conformant and none of this is reachable.

This subset is intentionally partial. It covers the SHACL 1.0 Core constraints
plus a curated slice of the SHACL 1.2 additions needed for rule targeting.
Any `sh:` predicate on a shape (or property shape) outside the **Supported**
tables below raises `UnsupportedShapeFeatureError` at shape-load time, so the
model and the validator stay in lockstep — there is no silent no-op.

The canonical source of truth for what is supported is the three sets in
[`src/srl/shapes/model.py`](../src/srl/shapes/model.py):
`_TARGET_PREDS`, `_NODE_CONSTRAINTS`, `_PROP_CONSTRAINTS`. The
`tests/test_support_matrix.py` drift test asserts every entry in those sets
appears in this document.

## Supported

### Targets

| Feature | Applies to | Notes |
| --- | --- | --- |
| `sh:targetClass` | node shape | instances incl. transitive `rdfs:subClassOf` |
| `sh:targetNode` | node shape | the named node itself |
| `sh:targetSubjectsOf` | node shape | subjects of triples with the given predicate |
| `sh:targetObjectsOf` | node shape | objects of triples with the given predicate |
| `sh:targetWhere` | node shape | data nodes conforming to the inline shape (1.2) |
| `sh:shape` | node shape | data-graph nodes `n` with `n sh:shape <shapeIri>` (1.2) |

### Value-type constraints

| Feature | Applies to |
| --- | --- |
| `sh:class` | node + property |
| `sh:datatype` | node + property |
| `sh:nodeKind` | node + property |

### Cardinality constraints

| Feature | Applies to |
| --- | --- |
| `sh:minCount` | property |
| `sh:maxCount` | property |

### Value-range constraints

| Feature | Applies to |
| --- | --- |
| `sh:minInclusive` | property |
| `sh:maxInclusive` | property |
| `sh:minExclusive` | property |
| `sh:maxExclusive` | property |

### String-based constraints

| Feature | Applies to |
| --- | --- |
| `sh:minLength` | property |
| `sh:maxLength` | property |
| `sh:pattern` | property |
| `sh:flags` | property (modifies `sh:pattern`) |
| `sh:languageIn` | property |
| `sh:uniqueLang` | property |

### Value constraints

| Feature | Applies to |
| --- | --- |
| `sh:hasValue` | node + property |
| `sh:in` | node + property |

### Logical constraints

| Feature | Applies to |
| --- | --- |
| `sh:and` | node + property |
| `sh:or` | node + property |
| `sh:not` | node + property |
| `sh:xone` | node + property |

### Shape-based constraints

| Feature | Applies to |
| --- | --- |
| `sh:node` | node + property |
| `sh:property` | node (structural: nests a property shape) |
| `sh:path` | property (structural: value-node selection) |

### SHACL 1.2 additions

| Feature | Applies to | Notes |
| --- | --- | --- |
| `sh:someValue` | node + property | at least one value conforms to the referenced shape |
| `sh:rootClass` | node + property | transitive-subclass root membership |
| `sh:subsetOf` | node + property | value set is a subset of the referenced values |
| `sh:memberShape` | property | shape each list member must conform to |
| `sh:minListLength` | property | minimum RDF-list length |
| `sh:maxListLength` | property | maximum RDF-list length |
| `sh:uniqueMembers` | property | list members must be pairwise distinct |
| `sh:reifierShape` | property | best-effort (see limitation below) |
| `sh:reificationRequired` | property | best-effort (see limitation below) |

**Best-effort:** `sh:reifierShape` and `sh:reificationRequired` are evaluated via
rdflib reifier triples when available. Under the pinned rdflib (7.6.0) triple
terms materialize as plain tuples, so these are treated as vacuously satisfied
rather than raising. This is a dependency limitation, not a gate.

## Not supported yet

These raise `UnsupportedShapeFeatureError` when encountered on a shape:

| Feature | Reason / scope |
| --- | --- |
| `sh:qualifiedValueShape` (+ `sh:qualifiedMinCount`/`sh:qualifiedMaxCount`) | qualified cardinality not implemented |
| `sh:closed` (+ `sh:ignoredProperties`) | closed-shape validation not implemented |
| `sh:sparql` (SPARQL-based constraints/targets) | out of scope for the Core subset |
| `sh:uniqueValuesFor` | not implemented |
| `sh:equals` | property-pair constraint, not implemented |
| `sh:disjoint` | property-pair constraint, not implemented |
| `sh:lessThan` | property-pair constraint, not implemented |
| `sh:lessThanOrEquals` | property-pair constraint, not implemented |
| `sh:entailment` | entailment regimes not implemented |
| `sh:deactivated` | shape (de)activation not honoured |
| non-validation annotations (`sh:message`, `sh:severity`, `sh:name`, `sh:description`, …) | metadata, not evaluated (and rejected to avoid silent drift) |
