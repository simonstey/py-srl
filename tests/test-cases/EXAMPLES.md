# SRL Examples Index

This directory contains example SRL rules and RDF data to try out the py-srl engine.

Each example has two files: a `.srl` file with the rule definitions and a `.ttl` file with RDF test data, when provided.

Below is a list of available examples. To run an example, use the CLI or tests, for example:

```pwsh
# Example: run the 'ancestor' example
uv run srl -v eval .\examples\transitive\transitive-001.srl .\examples\transitive\transitive-001.ttl
```

| ID                  | Title                          | Category         | Description                                        | SRL file                                  | TTL file                                  | Status |
| ------------------- | ------------------------------ | ---------------- | -------------------------------------------------- | ----------------------------------------- | ----------------------------------------- | ------ |
| child-of            | Child-Of Relationship          | basic-inference  | Derive childOf from fatherOf and motherOf          | basic-inference/basic-inference-001.srl   | basic-inference/basic-inference-001.ttl   | OK     |
| sibling             | Sibling Inference              | basic-inference  | Derive sibling relationships from shared parents   | basic-inference/basic-inference-002.srl   | basic-inference/basic-inference-002.ttl   | OK     |
| type-inference      | Type Inference                 | basic-inference  | Infer types based on property usage                | basic-inference/basic-inference-003.srl   | basic-inference/basic-inference-003.ttl   | OK     |
| ancestor            | Ancestor Transitive Closure    | transitive       | Compute ancestor relationships transitively        | transitive/transitive-001.srl             | transitive/transitive-001.ttl             | OK     |
| part-of             | Part-Of Hierarchy              | transitive       | Transitive part-whole relationships                | transitive/transitive-002.srl             | transitive/transitive-002.ttl             | OK     |
| friend-of           | Friendship (Symmetric)         | symmetric        | Symmetric friendship relationship                  | symmetric/symmetric-001.srl               | symmetric/symmetric-001.ttl               | OK     |
| married-to          | Marriage (Symmetric)           | symmetric        | Symmetric marriage relationship                    | symmetric/symmetric-002.srl               | symmetric/symmetric-002.ttl               | OK     |
| inverse-properties  | Inverse Properties             | symmetric        | Declare inverse property relationships             | symmetric/symmetric-003.srl               | symmetric/symmetric-003.ttl               | OK     |
| default-value       | Default Value with Negation    | negation         | Assign default full name when not specified        | negation/negation-001.srl                 | negation/negation-001.ttl                 | OK     |
| closed-world        | Closed World Assumption        | negation         | Mark entities as inactive if not explicitly active | negation/negation-002.srl                 | negation/negation-002.ttl                 | OK     |
| unique-constraint   | Unique Value Detection         | negation         | Detect when a person has exactly one email         | negation/negation-003.srl                 | negation/negation-003.ttl                 | OK     |
| concat-names        | String Concatenation           | aggregation      | Combine first and last names                       | aggregation/aggregation-001.srl           | aggregation/aggregation-001.ttl           | OK     |
| age-calculation     | Age Calculation                | aggregation      | Calculate age from birth year                      | aggregation/aggregation-002.srl           | aggregation/aggregation-002.ttl           | OK     |
| required-properties | Required Properties            | validation       | Check Persons have required name and email         | validation/validation-001.srl             | validation/validation-001.ttl             | OK     |
| path-sequence       | Path Sequence                  | path-expressions | Navigate multiple properties (parent/parent)       | path-expressions/path-expressions-001.srl | path-expressions/path-expressions-001.ttl | OK     |
| path-alternative    | Path Alternatives              | path-expressions | Match any of several properties via alternatives   | path-expressions/path-expressions-002.srl | path-expressions/path-expressions-002.ttl | FAIL   |
| path-inverse        | Inverse Paths                  | path-expressions | Traverse properties in reverse direction           | path-expressions/path-expressions-003.srl | path-expressions/path-expressions-003.ttl | OK     |
| path-transitive     | Transitive Path Closure        | path-expressions | Use + and * for transitive path traversal          | path-expressions/path-expressions-004.srl | path-expressions/path-expressions-004.ttl | FAIL   |
| path-optional       | Optional Path Step             | path-expressions | Use ? for zero or one step traversal               | path-expressions/path-expressions-005.srl | path-expressions/path-expressions-005.ttl | FAIL   |
| path-negated        | Negated Property Set           | path-expressions | Match any property except specified ones           | path-expressions/path-expressions-006.srl | path-expressions/path-expressions-006.ttl | FAIL   |
| exists-filter       | EXISTS in Filter               | exists-patterns  | Use EXISTS to check for pattern existence          | exists-patterns/exists-patterns-001.srl   | exists-patterns/exists-patterns-001.ttl   | FAIL   |
| not-exists-filter   | NOT EXISTS Filter              | exists-patterns  | Use NOT EXISTS for absence checks                  | exists-patterns/exists-patterns-002.srl   | exists-patterns/exists-patterns-002.ttl   | FAIL   |
| exists-complex      | Complex EXISTS Patterns        | exists-patterns  | EXISTS with multiple conditions                    | exists-patterns/exists-patterns-003.srl   | exists-patterns/exists-patterns-003.ttl   | FAIL   |
| in-expression       | IN Expression                  | exists-patterns  | Check if value is in a list of options             | exists-patterns/exists-patterns-004.srl   | exists-patterns/exists-patterns-004.ttl   | OK     |
| not-in-expression   | NOT IN Expression              | exists-patterns  | Exclude values from a list                         | exists-patterns/exists-patterns-005.srl   | exists-patterns/exists-patterns-005.ttl   | OK     |
| reflexive-property  | Reflexive Property             | symmetric        | Example REFLEXIVE declaration with rule            | symmetric/symmetric-004.srl               | symmetric/symmetric-004.ttl               | FAIL   |
| string-before-after | STRBEFORE / STRAFTER           | string-functions | Extract substrings before/after separator          | string-functions/string-functions-001.srl | string-functions/string-functions-001.ttl | FAIL   |
| regex-matching      | REGEX Pattern Matching         | string-functions | Use regex functions in FILTER                      | string-functions/string-functions-002.srl | string-functions/string-functions-002.ttl | FAIL   |
| encode-uri          | URI Encoding                   | string-functions | Encode strings for URI usage                       | string-functions/string-functions-003.srl | string-functions/string-functions-003.ttl | FAIL   |
| lang-matching       | Language Tag Matching          | string-functions | Match language tags with LANGMATCHES               | string-functions/string-functions-004.srl | string-functions/string-functions-004.ttl | OK     |
| typed-literals      | Typed Literals (STRDT/STRLANG) | string-functions | Create typed literals and language-tagged strings  | string-functions/string-functions-005.srl | string-functions/string-functions-005.ttl | FAIL   |
| hash-functions      | Cryptographic Hashes           | hash-functions   | Generate MD5, SHA hashes and fingerprints          | hash-functions/hash-functions-001.srl     | hash-functions/hash-functions-001.ttl     | FAIL   |
| uuid-generation     | UUID Generation                | hash-functions   | Generate UUID IRI and strings                      | hash-functions/hash-functions-002.srl     | hash-functions/hash-functions-002.ttl     | FAIL   |
| same-term           | SAMETERM Comparison            | hash-functions   | Check exact term equality                          | hash-functions/hash-functions-003.srl     | hash-functions/hash-functions-003.ttl     | FAIL   |

---

If a TTL file is not present for an example, the SRL can still be executed against your own RDF graph. Use `uv run srl -v eval <rule-file.srl> <data-file.ttl>` to run an example.
