# SRL Examples Index

This directory contains example SRL rules and RDF data to try out the py-srl engine.

Each example has two files: a `.srl` file with the rule definitions and a `.ttl` file with RDF test data, when provided.

Below is a list of available examples. To run an example, use the CLI or tests, for example:

```pwsh
# Example: run the 'ancestor' example
uv run srl -v eval .\examples\ancestor.srl .\examples\ancestor.ttl
```

| ID                  | Title                          | Category         | Description                                        | SRL file                | TTL file                | Status |
| ------------------- | ------------------------------ | ---------------- | -------------------------------------------------- | ----------------------- | ----------------------- | ------ |
| child-of            | Child-Of Relationship          | basic-inference  | Derive childOf from fatherOf and motherOf          | child-of.srl            | child-of.ttl            | OK     |
| sibling             | Sibling Inference              | basic-inference  | Derive sibling relationships from shared parents   | sibling.srl             | sibling.ttl             | OK     |
| type-inference      | Type Inference                 | basic-inference  | Infer types based on property usage                | type-inference.srl      | type-inference.ttl      | OK     |
| ancestor            | Ancestor Transitive Closure    | transitive       | Compute ancestor relationships transitively        | ancestor.srl            | ancestor.ttl            | OK     |
| part-of             | Part-Of Hierarchy              | transitive       | Transitive part-whole relationships                | part-of.srl             | part-of.ttl             | OK     |
| friend-of           | Friendship (Symmetric)         | symmetric        | Symmetric friendship relationship                  | friend-of.srl           | friend-of.ttl           | OK     |
| married-to          | Marriage (Symmetric)           | symmetric        | Symmetric marriage relationship                    | married-to.srl          | married-to.ttl          | OK     |
| inverse-properties  | Inverse Properties             | symmetric        | Declare inverse property relationships             | inverse-properties.srl  | inverse-properties.ttl  | OK     |
| default-value       | Default Value with Negation    | negation         | Assign default full name when not specified        | default-value.srl       | default-value.ttl       | OK     |
| closed-world        | Closed World Assumption        | negation         | Mark entities as inactive if not explicitly active | closed-world.srl        | closed-world.ttl        | OK     |
| unique-constraint   | Unique Value Detection         | negation         | Detect when a person has exactly one email         | unique-constraint.srl   | unique-constraint.ttl   | OK     |
| concat-names        | String Concatenation           | aggregation      | Combine first and last names                       | concat-names.srl        | concat-names.ttl        | OK     |
| age-calculation     | Age Calculation                | aggregation      | Calculate age from birth year                      | age-calculation.srl     | age-calculation.ttl     | OK     |
| required-properties | Required Properties            | validation       | Check Persons have required name and email         | required-properties.srl | required-properties.ttl | OK     |
| path-sequence       | Path Sequence                  | path-expressions | Navigate multiple properties (parent/parent)       | path-sequence.srl       | path-sequence.ttl       | OK     |
| path-alternative    | Path Alternatives              | path-expressions | Match any of several properties via alternatives   | path-alternative.srl    | path-alternative.ttl    | FAIL   |
| path-inverse        | Inverse Paths                  | path-expressions | Traverse properties in reverse direction           | path-inverse.srl        | path-inverse.ttl        | OK     |
| path-transitive     | Transitive Path Closure        | path-expressions | Use + and * for transitive path traversal          | path-transitive.srl     | path-transitive.ttl     | FAIL   |
| path-optional       | Optional Path Step             | path-expressions | Use ? for zero or one step traversal               | path-optional.srl       | path-optional.ttl       | FAIL   |
| path-negated        | Negated Property Set           | path-expressions | Match any property except specified ones           | path-negated.srl        | path-negated.ttl        | FAIL   |
| exists-filter       | EXISTS in Filter               | exists-patterns  | Use EXISTS to check for pattern existence          | exists-filter.srl       | exists-filter.ttl       | FAIL   |
| not-exists-filter   | NOT EXISTS Filter              | exists-patterns  | Use NOT EXISTS for absence checks                  | not-exists-filter.srl   | not-exists-filter.ttl   | FAIL   |
| exists-complex      | Complex EXISTS Patterns        | exists-patterns  | EXISTS with multiple conditions                    | exists-complex.srl      | exists-complex.ttl      | FAIL   |
| in-expression       | IN Expression                  | exists-patterns  | Check if value is in a list of options             | in-expression.srl       | in-expression.ttl       | OK     |
| not-in-expression   | NOT IN Expression              | exists-patterns  | Exclude values from a list                         | not-in-expression.srl   | not-in-expression.ttl   | OK     |
| reflexive-property  | Reflexive Property             | symmetric        | Example REFLEXIVE declaration with rule            | reflexive-property.srl  | reflexive-property.ttl  | FAIL   |
| string-before-after | STRBEFORE / STRAFTER           | string-functions | Extract substrings before/after separator          | string-before-after.srl | string-before-after.ttl | FAIL   |
| regex-matching      | REGEX Pattern Matching         | string-functions | Use regex functions in FILTER                      | regex-matching.srl      | regex-matching.ttl      | FAIL   |
| encode-uri          | URI Encoding                   | string-functions | Encode strings for URI usage                       | encode-uri.srl          | encode-uri.ttl          | FAIL   |
| lang-matching       | Language Tag Matching          | string-functions | Match language tags with LANGMATCHES               | lang-matching.srl       | lang-matching.ttl       | OK     |
| typed-literals      | Typed Literals (STRDT/STRLANG) | string-functions | Create typed literals and language-tagged strings  | typed-literals.srl      | typed-literals.ttl      | FAIL   |
| hash-functions      | Cryptographic Hashes           | hash-functions   | Generate MD5, SHA hashes and fingerprints          | hash-functions.srl      | hash-functions.ttl      | FAIL   |
| uuid-generation     | UUID Generation                | hash-functions   | Generate UUID IRI and strings                      | uuid-generation.srl     | uuid-generation.ttl     | FAIL   |
| same-term           | SAMETERM Comparison            | hash-functions   | Check exact term equality                          | same-term.srl           | same-term.ttl           | FAIL   |

---

If a TTL file is not present for an example, the SRL can still be executed against your own RDF graph. Use `uv run srl -v eval <rule-file.srl> <data-file.ttl>` to run an example.
