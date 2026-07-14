"""RDF 1.2 concrete-syntax conformance over the bundled W3C syntax suite.

Positive ``syntax-*`` tests must parse; negative ``*-bad-*`` tests must be
rejected. Four pre-existing wrong-passers (``@en--LTR`` lang-direction case /
undeclared prefix) are out of scope for RDF-1.2 construct support and are
expected to stay unchanged.
"""

import glob
import os

import pytest

from srl.parser.parser import ParseError, SRLParser

SYNTAX_DIR = os.path.join(
    os.path.dirname(__file__), "shacl12-test-suite", "tests", "rules", "syntax"
)

# Negatives that MUST reject once the RDF-1.2 constructs parse.
TARGET_NEG = {
    "syntax-data-bad-07",  # empty {| |}
    "syntax-data-bad-08",  # Var reifier-id in DATA
    "syntax-pattern-bad-04",  # empty {| |}
    "syntax-template-bad-04",  # empty {| |}
    "syntax-template-bad-06",  # path in {| |} + missing |}
}

# Pre-existing wrong-passers unrelated to RDF-1.2 (out of scope).
PREEXISTING_WRONGPASS = {
    "syntax-pattern-bad-01",  # @en--LTR
    "syntax-rule-bad-04",  # undeclared prefix
    "syntax-rule-terms-bad-01",  # @en--LTR
    "syntax-template-bad-01",  # @en--LTR
}


def test_grammar_builds_lalr():
    """Building the parser runs LALR(1) analysis; a collision raises here."""
    SRLParser()


@pytest.mark.parametrize(
    "path",
    sorted(glob.glob(os.path.join(SYNTAX_DIR, "*.srl"))),
    ids=lambda p: os.path.basename(p)[:-4],
)
def test_syntax_case(path):
    name = os.path.basename(path)[:-4]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parser = SRLParser()
    is_negative = "bad" in name
    try:
        parser.parse(text)
        parsed = True
    except ParseError:
        parsed = False

    if not is_negative:
        assert parsed, f"positive test {name} should parse"
    elif name in PREEXISTING_WRONGPASS:
        pass  # out of scope, behaviour unchanged
    else:
        assert not parsed, f"negative test {name} must reject"
