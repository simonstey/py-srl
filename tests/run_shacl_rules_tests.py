#!/usr/bin/env python3
"""
SHACL 1.2 Rules Test Suite Runner and EARL Report Generator

This script runs all SHACL Rules tests from the W3C test suite against
the shacl-rules library and generates an EARL implementation report.

Usage:
    python run_shacl_rules_tests.py -o report.ttl
    python run_shacl_rules_tests.py -o report.ttl --test-type syntax
    python run_shacl_rules_tests.py -o report.ttl --test-suite-path /path/to/shacl12-test-suite
"""

import argparse
import html as _html
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, FOAF, RDF, XSD

# Import the shacl-rules library
from srl import (
    ParseError,
    RuleEngine,
    SRLParser,
    StratificationError,
    WellFormednessError,
)
from srl import __version__ as SRL_VERSION
from srl import (
    validate_rule_well_formedness,
)

# Namespaces for EARL and test manifest
EARL = Namespace("http://www.w3.org/ns/earl#")
DOAP = Namespace("http://usefulinc.com/ns/doap#")
MF = Namespace("http://www.w3.org/2001/sw/DataAccess/tests/test-manifest#")
SRT = Namespace("http://www.w3.org/ns/shacl-rules-test#")


class TestOutcome(Enum):
    """Test outcome enumeration matching EARL vocabulary."""

    PASSED = "passed"
    FAILED = "failed"
    CANT_TELL = "cantTell"
    INAPPLICABLE = "inapplicable"
    UNTESTED = "untested"


class TestType(Enum):
    """Test type enumeration for SHACL Rules tests."""

    POSITIVE_SYNTAX = "RulesPositiveSyntaxTest"
    NEGATIVE_SYNTAX = "RulesNegativeSyntaxTest"
    POSITIVE_WELLFORMEDNESS = "RulesPositiveWellFormednessTest"
    NEGATIVE_WELLFORMEDNESS = "RulesNegativeWellFormednessTest"
    POSITIVE_STRATIFICATION = "RulesPositiveStratificationTest"
    NEGATIVE_STRATIFICATION = "RulesNegativeStratificationTest"
    EVAL = "RulesEvalTest"
    TARGETING_EVAL = "RulesTargetingEvalTest"


@dataclass
class TestEntry:
    """Represents a single test entry from the manifest."""

    uri: URIRef
    name: str
    test_type: TestType
    action: URIRef  # For syntax/wellformed/stratification tests
    action_ruleset: Optional[URIRef] = None  # For eval tests
    action_data: Optional[URIRef] = None  # For eval tests
    result: Optional[URIRef] = None  # For eval tests - expected result
    action_shapes: Optional[URIRef] = None  # For targeting eval tests (opt-in extension)


@dataclass
class TestResult:
    """Represents the result of running a single test."""

    test: TestEntry
    outcome: TestOutcome
    message: Optional[str] = None
    duration_ms: Optional[float] = None
    inferred: Optional[str] = None  # Turtle of triples produced by eval/targeting tests


# Report categorization shared by the Markdown and HTML generators.
CATEGORY_ORDER = [
    ("Syntax", [TestType.POSITIVE_SYNTAX, TestType.NEGATIVE_SYNTAX]),
    ("Well-formedness", [TestType.POSITIVE_WELLFORMEDNESS, TestType.NEGATIVE_WELLFORMEDNESS]),
    ("Stratification", [TestType.POSITIVE_STRATIFICATION, TestType.NEGATIVE_STRATIFICATION]),
    ("Evaluation", [TestType.EVAL]),
    ("Targeting extension (opt-in, NOT W3C-spec)", [TestType.TARGETING_EVAL]),
]
OUTCOME_BADGE = {
    TestOutcome.PASSED: "✅",
    TestOutcome.FAILED: "❌",
    TestOutcome.CANT_TELL: "⚠️",
    TestOutcome.INAPPLICABLE: "➖",
    TestOutcome.UNTESTED: "❔",
}


class TestManifestParser:
    """Parses SHACL Rules test manifests."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.base_path = manifest_path.parent
        self.graph = Graph()

    def parse(self) -> List[TestEntry]:
        """Parse the main manifest and all included sub-manifests."""
        self.graph.parse(self.manifest_path, format="turtle")

        # Find included manifests
        tests = []

        # Process includes
        manifest_uri = self._get_manifest_uri()
        for included in self.graph.objects(manifest_uri, MF.include):
            if isinstance(included, BNode):
                # It's an RDF list
                for item in self._parse_rdf_list(included):
                    included_path = self._resolve_path(item)
                    if included_path.exists():
                        sub_parser = TestManifestParser(included_path)
                        tests.extend(sub_parser.parse())
            else:
                # It's a direct reference
                included_path = self._resolve_path(included)
                if included_path.exists():
                    sub_parser = TestManifestParser(included_path)
                    tests.extend(sub_parser.parse())

        # Process entries in this manifest
        for entry_list in self.graph.objects(manifest_uri, MF.entries):
            for entry_uri in self._parse_rdf_list(entry_list):
                test = self._parse_test_entry(entry_uri)
                if test:
                    tests.append(test)

        return tests

    def _get_manifest_uri(self) -> URIRef:
        """Get the manifest URI."""
        for s in self.graph.subjects(RDF.type, MF.Manifest):
            return s
        # Try with empty relative URI
        for s, p, o in self.graph.triples((None, RDF.type, MF.Manifest)):
            return s
        return URIRef("")

    def _parse_rdf_list(self, list_node) -> List[URIRef]:
        """Parse an RDF list into a Python list."""
        items = []
        current = list_node
        while current and current != RDF.nil:
            first = self.graph.value(current, RDF.first)
            if first:
                items.append(first)
            current = self.graph.value(current, RDF.rest)
        return items

    def _resolve_path(self, uri: URIRef) -> Path:
        """Resolve a URI to a file path relative to the manifest."""
        uri_str = str(uri)
        if uri_str.startswith("file:///"):
            # Windows: file:///C:/... -> C:/...
            # Unix: file:///path/... -> /path/...
            path_str = uri_str[8:]
            # On Windows, check if it starts with a drive letter
            if len(path_str) >= 2 and path_str[1] == ":":
                return Path(path_str)
            # On Unix, preserve the leading slash
            return Path("/" + path_str)
        if uri_str.startswith("file://"):
            return Path(uri_str[7:])
        # Handle relative URIs
        if not uri_str.startswith("http"):
            return self.base_path / uri_str
        # Handle remote URIs by extracting file name
        return self.base_path / uri_str.split("/")[-1]

    def _parse_test_entry(self, uri: URIRef) -> Optional[TestEntry]:
        """Parse a single test entry."""
        # Determine test type
        test_type = None
        for rdf_type in self.graph.objects(uri, RDF.type):
            type_str = str(rdf_type).split("#")[-1]
            for tt in TestType:
                if tt.value == type_str:
                    test_type = tt
                    break
            if test_type:
                break

        if not test_type:
            return None

        # Get test name
        name = str(self.graph.value(uri, MF.name) or uri.split("#")[-1])

        # Get action
        action = self.graph.value(uri, MF.action)

        action_ruleset = None
        action_data = None
        result = None

        action_shapes = None
        if test_type in (TestType.EVAL, TestType.TARGETING_EVAL):
            # Action is a blank node with ruleset + data (+ shapes for targeting).
            if action:
                action_ruleset = self.graph.value(action, SRT.ruleset)
                action_data = self.graph.value(action, SRT.data)
                action_shapes = self.graph.value(action, SRT.shapes)
            result = self.graph.value(uri, MF.result)

        return TestEntry(
            uri=uri,
            name=name,
            test_type=test_type,
            action=action if test_type not in (TestType.EVAL, TestType.TARGETING_EVAL) else None,
            action_ruleset=action_ruleset,
            action_data=action_data,
            result=result,
            action_shapes=action_shapes,
        )


class SHACLRulesTestRunner:
    """Runs SHACL Rules tests using the shacl-rules library."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.parser = SRLParser()

    def run_test(self, test: TestEntry) -> TestResult:
        """Run a single test and return the result."""
        try:
            if test.test_type == TestType.POSITIVE_SYNTAX:
                return self._run_positive_syntax_test(test)
            elif test.test_type == TestType.NEGATIVE_SYNTAX:
                return self._run_negative_syntax_test(test)
            elif test.test_type == TestType.POSITIVE_WELLFORMEDNESS:
                return self._run_positive_wellformedness_test(test)
            elif test.test_type == TestType.NEGATIVE_WELLFORMEDNESS:
                return self._run_negative_wellformedness_test(test)
            elif test.test_type == TestType.POSITIVE_STRATIFICATION:
                return self._run_positive_stratification_test(test)
            elif test.test_type == TestType.NEGATIVE_STRATIFICATION:
                return self._run_negative_stratification_test(test)
            elif test.test_type == TestType.EVAL:
                return self._run_eval_test(test)
            elif test.test_type == TestType.TARGETING_EVAL:
                return self._run_targeting_eval_test(test)
            else:
                return TestResult(
                    test=test,
                    outcome=TestOutcome.INAPPLICABLE,
                    message=f"Unknown test type: {test.test_type}",
                )
        except Exception as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Unexpected error: {str(e)}",
            )

    def _resolve_file(self, uri: URIRef) -> Path:
        """Resolve a URI to a file path."""
        uri_str = str(uri)
        # Handle file:// URIs
        if uri_str.startswith("file:///"):
            # Windows: file:///C:/... -> C:/...
            # Unix: file:///path/... -> /path/...
            path_str = uri_str[8:]
            # On Windows, check if it starts with a drive letter
            if len(path_str) >= 2 and path_str[1] == ":":
                return Path(path_str)
            # On Unix, preserve the leading slash
            return Path("/" + path_str)
        if uri_str.startswith("file://"):
            return Path(uri_str[7:])
        # Handle relative URIs
        if not uri_str.startswith("http"):
            return self.base_path / uri_str
        # Extract filename from URI
        filename = uri_str.split("/")[-1]
        return self.base_path / filename

    def _read_file(self, file_path: Path) -> str:
        """Read file contents."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _run_positive_syntax_test(self, test: TestEntry) -> TestResult:
        """Run a positive syntax test - parsing should succeed."""
        try:
            file_path = self._resolve_file(test.action)
            content = self._read_file(file_path)
            self.parser.parse(content)
            return TestResult(test=test, outcome=TestOutcome.PASSED)
        except ParseError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message=f"Parse error (expected success): {str(e)}",
            )
        except FileNotFoundError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Test file not found: {str(e)}",
            )

    def _run_negative_syntax_test(self, test: TestEntry) -> TestResult:
        """Run a negative syntax test - parsing should fail."""
        try:
            file_path = self._resolve_file(test.action)
            content = self._read_file(file_path)
            self.parser.parse(content)
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message="Parse succeeded (expected failure)",
            )
        except ParseError:
            return TestResult(test=test, outcome=TestOutcome.PASSED)
        except FileNotFoundError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Test file not found: {str(e)}",
            )

    def _run_positive_wellformedness_test(self, test: TestEntry) -> TestResult:
        """Run a positive well-formedness test - validation should succeed."""
        try:
            file_path = self._resolve_file(test.action)
            content = self._read_file(file_path)
            rule_set = self.parser.parse(content)

            # Validate well-formedness for each rule
            for rule in rule_set.rules:
                validate_rule_well_formedness(rule)

            return TestResult(test=test, outcome=TestOutcome.PASSED)
        except ParseError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message=f"Parse error: {str(e)}",
            )
        except WellFormednessError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message=f"Well-formedness error (expected success): {str(e)}",
            )
        except FileNotFoundError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Test file not found: {str(e)}",
            )

    def _run_negative_wellformedness_test(self, test: TestEntry) -> TestResult:
        """Run a negative well-formedness test - validation should fail."""
        try:
            file_path = self._resolve_file(test.action)
            content = self._read_file(file_path)
            rule_set = self.parser.parse(content)

            # Validate well-formedness for each rule
            for rule in rule_set.rules:
                validate_rule_well_formedness(rule)

            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message="Well-formedness validation passed (expected failure)",
            )
        except WellFormednessError:
            return TestResult(test=test, outcome=TestOutcome.PASSED)
        except ParseError:
            # Parse error counts as well-formedness failure
            return TestResult(test=test, outcome=TestOutcome.PASSED)
        except FileNotFoundError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Test file not found: {str(e)}",
            )

    def _run_positive_stratification_test(self, test: TestEntry) -> TestResult:
        """Run a positive stratification test - stratification should succeed."""
        try:
            file_path = self._resolve_file(test.action)
            content = self._read_file(file_path)
            rule_set = self.parser.parse(content)

            # Create engine and attempt stratification
            engine = RuleEngine(rule_set)
            engine.stratify()

            return TestResult(test=test, outcome=TestOutcome.PASSED)
        except ParseError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message=f"Parse error: {str(e)}",
            )
        except StratificationError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message=f"Stratification error (expected success): {str(e)}",
            )
        except FileNotFoundError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Test file not found: {str(e)}",
            )

    def _run_negative_stratification_test(self, test: TestEntry) -> TestResult:
        """Run a negative stratification test - stratification should fail."""
        try:
            file_path = self._resolve_file(test.action)
            content = self._read_file(file_path)
            rule_set = self.parser.parse(content)

            # Create engine and attempt stratification
            engine = RuleEngine(rule_set)
            engine.stratify()

            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message="Stratification succeeded (expected failure)",
            )
        except StratificationError:
            return TestResult(test=test, outcome=TestOutcome.PASSED)
        except ParseError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Parse error (could not test stratification): {str(e)}",
            )
        except FileNotFoundError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Test file not found: {str(e)}",
            )

    @staticmethod
    def _serialize_inferred(inferred_graph: Graph, expected_graph: Graph) -> Optional[str]:
        """Render the inferred triples as compact Turtle for the report.

        Reuses the expected graph's namespace bindings so terms print as prefixed
        names (``:x``) rather than full IRIs. Best-effort: returns None on failure.
        """
        try:
            for prefix, ns in expected_graph.namespaces():
                inferred_graph.bind(prefix, ns, replace=False)
            body = "\n".join(
                line
                for line in inferred_graph.serialize(format="turtle").splitlines()
                if not line.startswith("@prefix") and line.strip()
            ).strip()
            return body or "# (no triples inferred)"
        except Exception:
            return None

    def _compare_inferred(
        self, test: TestEntry, inferred_graph: Graph, expected_graph: Graph
    ) -> TestResult:
        """Compare inferred triples to the expected graph by RDF isomorphism."""
        inferred_ttl = self._serialize_inferred(inferred_graph, expected_graph)
        if isomorphic(inferred_graph, expected_graph):
            return TestResult(test=test, outcome=TestOutcome.PASSED, inferred=inferred_ttl)
        expected_count = len(expected_graph)
        actual_count = len(inferred_graph)
        msg = f"Graph mismatch: expected {expected_count} inferred triples, got {actual_count}"
        missing = [t for t in expected_graph if t not in inferred_graph]
        extra = [t for t in inferred_graph if t not in expected_graph]
        if missing:
            msg += f"; missing: {len(missing)}"
        if extra:
            msg += f"; extra: {len(extra)}"
        return TestResult(test=test, outcome=TestOutcome.FAILED, message=msg, inferred=inferred_ttl)

    def _run_eval_test(self, test: TestEntry) -> TestResult:
        """
        Run an evaluation test.

        The result file contains only the inferred triples.
        We evaluate the rules on the data graph and compute the difference
        (inferred triples = result graph - original data graph).
        """
        try:
            # Load ruleset
            ruleset_path = self._resolve_file(test.action_ruleset)
            ruleset_content = self._read_file(ruleset_path)
            rule_set = self.parser.parse(ruleset_content)

            # Load data graph
            data_path = self._resolve_file(test.action_data)
            data_graph = Graph()
            data_graph.parse(data_path, format="turtle")
            original_count = len(data_graph)

            # Load expected result (inferred triples only)
            result_path = self._resolve_file(test.result)
            expected_graph = Graph()
            expected_graph.parse(result_path, format="turtle")

            # Evaluate rules
            engine = RuleEngine(rule_set)
            result_graph = engine.evaluate(data_graph, inplace=False)

            # Compute inferred triples (result - original data)
            inferred_graph = Graph()
            for triple in result_graph:
                if triple not in data_graph:
                    inferred_graph.add(triple)

            # Compare inferred triples with expected
            return self._compare_inferred(test, inferred_graph, expected_graph)
        except ParseError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message=f"Parse error: {str(e)}",
            )
        except StratificationError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.FAILED,
                message=f"Stratification error: {str(e)}",
            )
        except FileNotFoundError as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Test file not found: {str(e)}",
            )
        except Exception as e:
            return TestResult(
                test=test,
                outcome=TestOutcome.CANT_TELL,
                message=f"Evaluation error: {str(e)}",
            )

    def _run_targeting_eval_test(self, test: TestEntry) -> TestResult:
        """Run a FOR-IN rule-to-shape targeting eval test (opt-in extension).

        Parses the ruleset with extensions enabled, loads data + shapes graphs,
        evaluates with a shapes graph, and compares the inferred triples
        (result - data) to the expected graph.
        """
        try:
            ext_parser = SRLParser(extensions=True)
            ruleset_content = self._read_file(self._resolve_file(test.action_ruleset))
            rule_set = ext_parser.parse(ruleset_content)

            data_graph = Graph()
            data_graph.parse(self._resolve_file(test.action_data), format="turtle")

            shapes_graph = Graph()
            shapes_graph.parse(self._resolve_file(test.action_shapes), format="turtle")

            expected_graph = Graph()
            expected_graph.parse(self._resolve_file(test.result), format="turtle")

            engine = RuleEngine(rule_set, extensions=True, shapes_graph=shapes_graph)
            result_graph = engine.evaluate(data_graph, inplace=False)

            inferred_graph = Graph()
            for triple in result_graph:
                if triple not in data_graph:
                    inferred_graph.add(triple)

            return self._compare_inferred(test, inferred_graph, expected_graph)
        except ParseError as e:
            return TestResult(
                test=test, outcome=TestOutcome.FAILED, message=f"Parse error: {str(e)}"
            )
        except FileNotFoundError as e:
            return TestResult(
                test=test, outcome=TestOutcome.CANT_TELL, message=f"Test file not found: {str(e)}"
            )
        except Exception as e:
            return TestResult(
                test=test, outcome=TestOutcome.CANT_TELL, message=f"Evaluation error: {str(e)}"
            )


class EARLReportGenerator:
    """Generates EARL implementation reports in Turtle format."""

    def __init__(
        self,
        project_name: str = "shacl-rules",
        project_homepage: str = "https://github.com/simonstey/py-srl",
        project_version: str = None,
        developer_name: str = "Simon Steyskal",
        developer_homepage: str = "https://github.com/simonstey",
    ):
        self.project_name = project_name
        self.project_homepage = project_homepage
        self.project_version = project_version or SRL_VERSION
        self.developer_name = developer_name
        self.developer_homepage = developer_homepage

        self.graph = Graph()
        self._bind_namespaces()
        self._create_project_and_assertor()

    def _bind_namespaces(self):
        """Bind common namespaces."""
        self.graph.bind("earl", EARL)
        self.graph.bind("doap", DOAP)
        self.graph.bind("foaf", FOAF)
        self.graph.bind("dc", DCTERMS)
        self.graph.bind("xsd", XSD)

    def _create_project_and_assertor(self):
        """Create the DOAP project and assertor information."""
        # Create project (test subject)
        self.project_uri = URIRef(self.project_homepage + "#project")
        self.graph.add((self.project_uri, RDF.type, DOAP.Project))
        self.graph.add((self.project_uri, RDF.type, EARL.TestSubject))
        self.graph.add((self.project_uri, RDF.type, EARL.Software))
        self.graph.add((self.project_uri, DOAP.name, Literal(self.project_name)))
        self.graph.add((self.project_uri, DOAP.homepage, URIRef(self.project_homepage)))
        self.graph.add((self.project_uri, DOAP.release, self._create_release()))
        self.graph.add((self.project_uri, DOAP["programming-language"], Literal("Python")))
        self.graph.add(
            (
                self.project_uri,
                DOAP.description,
                Literal("Python SHACL 1.2 Rules (SRL) Parser and Evaluation Engine"),
            )
        )

        # Create developer
        self.developer_uri = URIRef(self.developer_homepage)
        self.graph.add((self.developer_uri, RDF.type, FOAF.Person))
        self.graph.add((self.developer_uri, FOAF.name, Literal(self.developer_name)))
        self.graph.add((self.developer_uri, FOAF.homepage, URIRef(self.developer_homepage)))

        # Link developer to project
        self.graph.add((self.project_uri, DOAP.developer, self.developer_uri))

        # Create assertor (the test runner itself)
        self.assertor_uri = URIRef(self.project_homepage + "#test-runner")
        self.graph.add((self.assertor_uri, RDF.type, EARL.Assertor))
        self.graph.add((self.assertor_uri, RDF.type, EARL.Software))
        self.graph.add((self.assertor_uri, DCTERMS.title, Literal("SHACL Rules Test Runner")))
        self.graph.add(
            (
                self.assertor_uri,
                DCTERMS.description,
                Literal("Automated test runner for W3C SHACL 1.2 Rules test suite"),
            )
        )

    def _create_release(self) -> BNode:
        """Create a DOAP Version node for the current release."""
        release = BNode()
        self.graph.add((release, RDF.type, DOAP.Version))
        self.graph.add((release, DOAP.revision, Literal(self.project_version)))
        self.graph.add(
            (
                release,
                DOAP.created,
                Literal(datetime.now(timezone.utc).date().isoformat(), datatype=XSD.date),
            )
        )
        return release

    def add_result(self, result: TestResult):
        """Add a test result as an EARL assertion."""
        # Create assertion
        assertion = BNode()
        self.graph.add((assertion, RDF.type, EARL.Assertion))
        self.graph.add((assertion, EARL.assertedBy, self.assertor_uri))
        self.graph.add((assertion, EARL.subject, self.project_uri))
        self.graph.add((assertion, EARL.test, result.test.uri))
        self.graph.add((assertion, EARL.mode, EARL.automatic))

        # Create test result
        test_result = BNode()
        self.graph.add((test_result, RDF.type, EARL.TestResult))

        # Map outcome to EARL vocabulary
        outcome_uri = EARL[result.outcome.value]
        self.graph.add((test_result, EARL.outcome, outcome_uri))

        # Add timestamp
        self.graph.add(
            (
                test_result,
                DCTERMS.date,
                Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime),
            )
        )

        # Add message if present
        if result.message:
            self.graph.add((test_result, DCTERMS.description, Literal(result.message)))

        # Link result to assertion
        self.graph.add((assertion, EARL.result, test_result))

    def serialize(self, output_path: Path):
        """Serialize the EARL report to a Turtle file."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.graph.serialize(format="turtle"))


def collect_source_snippets(runner: "SHACLRulesTestRunner", test: TestEntry) -> List[tuple]:
    """Return (label, text) pairs of the source files backing a test, best-effort."""
    snippets: List[tuple] = []
    refs = []
    if test.test_type in (TestType.EVAL, TestType.TARGETING_EVAL):
        refs = [
            ("ruleset", test.action_ruleset),
            ("data", test.action_data),
            ("shapes", test.action_shapes),
            ("expected", test.result),
        ]
    else:
        refs = [("source", test.action)]
    for label, ref in refs:
        if ref is None:
            continue
        try:
            snippets.append((label, runner._read_file(runner._resolve_file(ref))))
        except OSError:
            continue
    return snippets


class MarkdownReportGenerator:
    """Renders a styled Markdown conformance report."""

    def __init__(self, project_name: str = "shacl-rules", project_version: str = None):
        self.project_name = project_name
        self.project_version = project_version or SRL_VERSION
        self.results: List[TestResult] = []
        self.runner: Optional["SHACLRulesTestRunner"] = None

    def add_results(self, results: List[TestResult], runner: "SHACLRulesTestRunner" = None):
        self.results = results
        self.runner = runner

    def _counts(self):
        passed = sum(1 for r in self.results if r.outcome == TestOutcome.PASSED)
        failed = sum(1 for r in self.results if r.outcome == TestOutcome.FAILED)
        other = len(self.results) - passed - failed
        return passed, failed, other

    def serialize(self, output_path: Path):
        passed, failed, other = self._counts()
        lines = [
            f"# {self.project_name} — SHACL 1.2 Rules conformance report",
            "",
            f"**Version:** {self.project_version}  ",
            f"**Generated:** {datetime.now(timezone.utc).date().isoformat()}",
            "",
            "| Result | Count |",
            "| --- | --- |",
            f"| ✅ Passed | {passed} |",
            f"| ❌ Failed | {failed} |",
            f"| ⚠️ Other | {other} |",
            f"| **Total** | **{len(self.results)}** |",
            "",
        ]
        by_type = {}
        for r in self.results:
            by_type.setdefault(r.test.test_type, []).append(r)
        for cat_name, types in CATEGORY_ORDER:
            cat_results = [r for tt in types for r in by_type.get(tt, [])]
            if not cat_results:
                continue
            lines.append(f"## {cat_name}")
            lines.append("")
            lines.append("| Test | Outcome | Message |")
            lines.append("| --- | --- | --- |")
            for r in cat_results:
                badge = OUTCOME_BADGE.get(r.outcome, "?")
                msg = (r.message or "").replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{r.test.name}` | {badge} {r.outcome.value} | {msg} |")
            lines.append("")
            if self.runner is not None:
                for r in cat_results:
                    snippets = collect_source_snippets(self.runner, r.test)
                    if not snippets:
                        continue
                    lines.append(f"<details><summary><code>{r.test.name}</code> source</summary>")
                    lines.append("")
                    for label, text in snippets:
                        lines.append(f"**{label}:**")
                        lines.append("")
                        lines.append("```")
                        lines.append(text.rstrip())
                        lines.append("```")
                        lines.append("")
                    lines.append("</details>")
                    lines.append("")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


# Preset scenarios seeded into the in-report playground. Each teaches one SRL
# feature and is drawn verbatim from the examples/ directory so the playground
# stays honest to what the reference implementation actually runs. `extension`
# entries carry a shapes graph and require the opt-in FOR-IN targeting toggle.
PLAYGROUND_PRESETS = [
    {
        "id": "paths",
        "label": "Sequence paths",
        "blurb": "Grandparent / great-grandparent via multi-step sequence paths (a/b).",
        "rules": (
            "PREFIX ex: <http://example.org/>\n\n"
            "# Grandparents via a two-step sequence path (parentOf/parentOf).\n"
            "RULE ex:GrandparentRule { ?gp ex:grandparentOf ?gc } WHERE {\n"
            "    ?gp ex:parentOf/ex:parentOf ?gc\n"
            "}\n\n"
            "# Great-grandparents via a three-step sequence path.\n"
            "RULE ex:GreatGrandparentRule { ?p ex:greatGrandparentOf ?ggc } WHERE {\n"
            "    ?p ex:parentOf/ex:parentOf/ex:parentOf ?ggc\n"
            "}"
        ),
        "data": (
            "@prefix ex: <http://example.org/> .\n\n"
            "ex:Alice ex:parentOf ex:Bob .\n"
            "ex:Bob ex:parentOf ex:Charlie .\n"
            "ex:Charlie ex:parentOf ex:Diana ."
        ),
    },
    {
        "id": "recursion",
        "label": "Recursive closure",
        "blurb": "Transitive ancestor relation computed to a fixed point (base + recursive rule).",
        "rules": (
            "PREFIX ex: <http://example.org/>\n\n"
            "# Base case: a parent is an ancestor.\n"
            "RULE {\n"
            "    ?x ex:ancestor ?y .\n"
            "} WHERE {\n"
            "    ?x ex:parent ?y .\n"
            "}\n\n"
            "# Recursive case: an ancestor of an ancestor is an ancestor.\n"
            "RULE {\n"
            "    ?x ex:ancestor ?z .\n"
            "} WHERE {\n"
            "    ?x ex:ancestor ?y .\n"
            "    ?y ex:ancestor ?z .\n"
            "}"
        ),
        "data": (
            "@prefix ex: <http://example.org/> .\n\n"
            "ex:Alice ex:parent ex:Bob .\n"
            "ex:Bob ex:parent ex:Charlie .\n"
            "ex:Charlie ex:parent ex:Diana ."
        ),
    },
    {
        "id": "set",
        "label": "SET + built-ins",
        "blurb": "Chained SET assignments over string and numeric built-ins "
        "(CONCAT, UCASE, STRLEN, ABS, ROUND).",
        "rules": (
            "PREFIX ex: <http://example.org/>\n\n"
            "# String pipeline: build a full name, then derive views of it.\n"
            "RULE {\n"
            "    ?p ex:fullName ?full .\n"
            "    ?p ex:displayName ?disp .\n"
            "    ?p ex:nameLength ?len .\n"
            "} WHERE {\n"
            "    ?p ex:firstName ?first .\n"
            "    ?p ex:lastName ?last .\n"
            '    SET(?full := CONCAT(?first, " ", ?last))\n'
            "    SET(?disp := UCASE(?full))\n"
            "    SET(?len := STRLEN(?full))\n"
            "}\n\n"
            "# Numeric pipeline: absolute error, then a rounded percentage error.\n"
            "RULE {\n"
            "    ?p ex:absError ?err .\n"
            "    ?p ex:pctError ?pct .\n"
            "} WHERE {\n"
            "    ?p ex:predicted ?pred .\n"
            "    ?p ex:actual ?act .\n"
            "    SET(?err := ABS(?pred - ?act))\n"
            "    SET(?pct := ROUND(100 * ?err / ?act))\n"
            "}"
        ),
        "data": (
            "@prefix ex: <http://example.org/> .\n\n"
            'ex:Person1 ex:firstName "John" ; ex:lastName "Doe" ;\n'
            "    ex:predicted 80 ; ex:actual 78 .\n"
            'ex:Person2 ex:firstName "Jane" ; ex:lastName "Smith" ;\n'
            "    ex:predicted 60 ; ex:actual 72 ."
        ),
    },
    {
        "id": "negation",
        "label": "Negation (NOT)",
        "blurb": "Closed-world reasoning: flag people with no recorded child via NOT { ... }.",
        "rules": (
            "PREFIX ex: <http://example.org/>\n\n"
            "# ?person is bound by the positive Person pattern before NOT references it.\n"
            "RULE {\n"
            "    ?person ex:childless true .\n"
            "} WHERE {\n"
            "    ?person ex:type ex:Person .\n"
            "    NOT {\n"
            "        ?person ex:hasChild ?child .\n"
            "    }\n"
            "}"
        ),
        "data": (
            "@prefix ex: <http://example.org/> .\n\n"
            "ex:Alice ex:type ex:Person ; ex:hasChild ex:Bob .\n"
            "ex:Carol ex:type ex:Person .   # no children recorded\n"
            "ex:Dave ex:type ex:Person .    # no children recorded"
        ),
    },
    {
        "id": "targeting",
        "label": "FOR-IN targeting",
        "blurb": "Opt-in rule-to-shape targeting: the rule fires only for focus nodes that "
        "conform to a SHACL shape. Not part of the W3C SRL spec.",
        "extension": True,
        "rules": (
            "PREFIX ex: <http://example.org/>\n\n"
            "# Fires only for ex:EmployeeShape focus nodes that CONFORM to it,\n"
            "# i.e. Persons that actually have a worksFor value.\n"
            "RULE ex:EmployeeRule FOR ?e IN ex:EmployeeShape { ?e a ex:Employee } WHERE {\n"
            "    ?e ex:worksFor ?company\n"
            "}"
        ),
        "data": (
            "@prefix ex: <http://example.org/> .\n\n"
            "# Eve works for a company (conforms); Frank does not.\n"
            "ex:Eve a ex:Person ; ex:worksFor ex:Acme .\n"
            "ex:Frank a ex:Person ."
        ),
        "shapes": (
            "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
            "@prefix ex: <http://example.org/> .\n\n"
            "# Targets every Person, conforms only when a worksFor value is present.\n"
            "ex:EmployeeShape a sh:NodeShape ;\n"
            "    sh:targetClass ex:Person ;\n"
            "    sh:property [ sh:path ex:worksFor ; sh:minCount 1 ] ."
        ),
    },
]


class HtmlReportGenerator:
    """Renders a self-contained, dependency-free HTML conformance report.

    One page, one system: a pass-rate hero, a sticky search/filter toolbar, and
    per-category tables whose rows expand in place to reveal their source. Ships
    light and dark themes (system default + a manual toggle) with all styling and
    behaviour inlined so the file works from disk with no server or assets.
    """

    # Design tokens + component styles. Product register: restrained palette,
    # semantic state colors, dense scannable rows. OKLCH throughout; dark theme
    # follows the system preference unless the manual toggle overrides it.
    _CSS = """
    :root {
      color-scheme: light dark;
      --bg: oklch(0.985 0.003 255); --surface: oklch(1 0 0);
      --surface-2: oklch(0.968 0.004 255); --hover: oklch(0.955 0.006 255);
      --border: oklch(0.905 0.006 255); --border-strong: oklch(0.83 0.01 255);
      --ink: oklch(0.26 0.02 262); --ink-muted: oklch(0.505 0.02 262);
      --accent: oklch(0.55 0.16 264); --ext: oklch(0.55 0.2 300);
      --pass-ink: oklch(0.46 0.11 150); --pass-bg: oklch(0.945 0.045 150);
      --pass-solid: oklch(0.63 0.14 150); --pass-row: oklch(0.986 0.012 150);
      --fail-ink: oklch(0.5 0.17 26); --fail-bg: oklch(0.948 0.045 26);
      --fail-solid: oklch(0.6 0.2 26); --fail-row: oklch(0.975 0.022 26);
      --warn-ink: oklch(0.48 0.09 80); --warn-bg: oklch(0.945 0.06 90);
      --warn-solid: oklch(0.76 0.14 85); --warn-row: oklch(0.98 0.03 90);
      --shadow: 0 1px 2px oklch(0.2 0.03 262 / 0.06), 0 4px 16px oklch(0.2 0.03 262 / 0.05);
      --radius: 14px; --radius-sm: 8px;
    }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        --bg: oklch(0.185 0.012 262); --surface: oklch(0.222 0.014 262);
        --surface-2: oklch(0.262 0.016 262); --hover: oklch(0.29 0.018 262);
        --border: oklch(0.32 0.016 262); --border-strong: oklch(0.42 0.02 262);
        --ink: oklch(0.955 0.008 262); --ink-muted: oklch(0.72 0.016 262);
        --accent: oklch(0.72 0.14 264); --ext: oklch(0.76 0.16 300);
        --pass-ink: oklch(0.86 0.14 150); --pass-bg: oklch(0.32 0.06 150);
        --pass-solid: oklch(0.66 0.15 150); --pass-row: oklch(0.24 0.03 150);
        --fail-ink: oklch(0.83 0.13 26); --fail-bg: oklch(0.34 0.08 26);
        --fail-solid: oklch(0.62 0.2 26); --fail-row: oklch(0.27 0.045 26);
        --warn-ink: oklch(0.88 0.11 90); --warn-bg: oklch(0.34 0.06 85);
        --warn-solid: oklch(0.78 0.14 85); --warn-row: oklch(0.26 0.035 85);
        --shadow: 0 1px 2px oklch(0 0 0 / 0.3), 0 6px 20px oklch(0 0 0 / 0.35);
      }
    }
    :root[data-theme="dark"] {
      --bg: oklch(0.185 0.012 262); --surface: oklch(0.222 0.014 262);
      --surface-2: oklch(0.262 0.016 262); --hover: oklch(0.29 0.018 262);
      --border: oklch(0.32 0.016 262); --border-strong: oklch(0.42 0.02 262);
      --ink: oklch(0.955 0.008 262); --ink-muted: oklch(0.72 0.016 262);
      --accent: oklch(0.72 0.14 264); --ext: oklch(0.76 0.16 300);
      --pass-ink: oklch(0.86 0.14 150); --pass-bg: oklch(0.32 0.06 150);
      --pass-solid: oklch(0.66 0.15 150); --pass-row: oklch(0.24 0.03 150);
      --fail-ink: oklch(0.83 0.13 26); --fail-bg: oklch(0.34 0.08 26);
      --fail-solid: oklch(0.62 0.2 26); --fail-row: oklch(0.27 0.045 26);
      --warn-ink: oklch(0.88 0.11 90); --warn-bg: oklch(0.34 0.06 85);
      --warn-solid: oklch(0.78 0.14 85); --warn-row: oklch(0.26 0.035 85);
      --shadow: 0 1px 2px oklch(0 0 0 / 0.3), 0 6px 20px oklch(0 0 0 / 0.35);
    }
    * { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; }
    body {
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      margin: 0; background: var(--bg); color: var(--ink);
      line-height: 1.5; font-size: 15px;
      -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
    }
    .wrap { max-width: 74rem; margin-inline: auto; padding: 2rem 1.25rem 4rem; }
    code, pre, .mono { font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace; }
    .vh {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
    }
    a { color: var(--accent); }

    /* Header */
    .top {
      display: flex; flex-wrap: wrap; gap: 1rem 1.5rem;
      align-items: flex-start; justify-content: space-between;
    }
    .brand h1 {
      font-size: clamp(1.35rem, 1rem + 1.4vw, 1.9rem); font-weight: 700;
      letter-spacing: -0.02em; margin: 0; display: flex; align-items: center;
      gap: 0.6rem; flex-wrap: wrap;
    }
    .brand .tag {
      font-size: 0.7rem; font-weight: 600; letter-spacing: 0.02em;
      color: var(--accent); background: color-mix(in oklch, var(--accent) 14%, transparent);
      padding: 0.2rem 0.55rem; border-radius: 999px; white-space: nowrap;
    }
    .brand .sub { margin: 0.35rem 0 0; color: var(--ink-muted); font-size: 0.92rem; }
    .top-right { display: flex; align-items: center; gap: 1.25rem; }
    .meta { display: flex; gap: 1.5rem; margin: 0; }
    .meta div { margin: 0; }
    .meta dt {
      font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--ink-muted); margin: 0;
    }
    .meta dd { margin: 0.15rem 0 0; font-size: 0.86rem; font-weight: 600; }
    .theme-btn {
      display: inline-flex; align-items: center; justify-content: center;
      width: 2.3rem; height: 2.3rem; padding: 0; border-radius: 10px;
      border: 1px solid var(--border); background: var(--surface); color: var(--ink);
      cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease;
    }
    .theme-btn:hover { background: var(--hover); border-color: var(--border-strong); }
    .theme-btn .ic { display: inline-flex; }
    .theme-btn .i-moon { display: none; }
    .theme-btn[data-mode="dark"] .i-sun { display: none; }
    .theme-btn[data-mode="dark"] .i-moon { display: inline-flex; }

    /* Hero */
    .hero {
      display: grid; gap: 1.5rem; margin: 1.75rem 0 1.25rem;
      padding: 1.4rem 1.5rem; background: var(--surface);
      border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow);
    }
    @media (min-width: 46rem) {
      .hero { grid-template-columns: auto 1fr; align-items: center; gap: 2.5rem; }
    }
    .rate { font-size: clamp(2.4rem, 1.6rem + 3vw, 3.2rem); font-weight: 750;
            line-height: 1; letter-spacing: -0.03em; color: var(--pass-ink); }
    .rate.has-fail { color: var(--ink); }
    .rate-sub { margin-top: 0.45rem; color: var(--ink-muted); font-size: 0.95rem; }
    .rate-note { color: var(--fail-ink); font-weight: 600; }
    .bar {
      display: flex; height: 0.8rem; border-radius: 999px; overflow: hidden;
      background: var(--surface-2); box-shadow: inset 0 0 0 1px var(--border);
    }
    .seg { min-width: 0.2rem; }
    .seg.passed { background: var(--pass-solid); }
    .seg.failed { background: var(--fail-solid); }
    .seg.other { background: var(--warn-solid); }
    .legend {
      display: flex; flex-wrap: wrap; gap: 0.4rem 1.1rem;
      list-style: none; margin: 0.9rem 0 0; padding: 0;
    }
    .leg {
      display: inline-flex; align-items: center; gap: 0.45rem;
      background: none; border: 0; padding: 0.2rem 0; font: inherit;
      font-size: 0.88rem; color: var(--ink-muted); cursor: pointer; border-radius: 6px;
    }
    .leg:hover { color: var(--ink); }
    .leg b { color: var(--ink); font-variant-numeric: tabular-nums; }
    .leg .sw { width: 0.7rem; height: 0.7rem; border-radius: 3px; flex: none; }
    .leg .sw.passed { background: var(--pass-solid); }
    .leg .sw.failed { background: var(--fail-solid); }
    .leg .sw.other { background: var(--warn-solid); }

    /* Toolbar */
    .toolbar {
      position: sticky; top: 0; z-index: 10;
      display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center;
      padding: 0.75rem 0; margin-bottom: 0.5rem;
      background: color-mix(in oklch, var(--bg) 92%, transparent);
      backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--border);
    }
    .search { position: relative; flex: 1 1 15rem; min-width: 12rem; }
    .search svg {
      position: absolute; left: 0.7rem; top: 50%; transform: translateY(-50%);
      color: var(--ink-muted); pointer-events: none;
    }
    .search input {
      width: 100%; padding: 0.5rem 0.75rem 0.5rem 2.2rem; font: inherit;
      color: var(--ink); background: var(--surface);
      border: 1px solid var(--border); border-radius: 9px;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .search input::placeholder { color: var(--ink-muted); }
    .search input:focus-visible {
      outline: none; border-color: var(--accent);
      box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent) 25%, transparent);
    }
    .filters { display: flex; gap: 0.4rem; flex-wrap: wrap; }
    .chip {
      display: inline-flex; align-items: center; gap: 0.4rem;
      padding: 0.4rem 0.75rem; font: inherit; font-size: 0.85rem; font-weight: 500;
      color: var(--ink-muted); background: var(--surface);
      border: 1px solid var(--border); border-radius: 999px; cursor: pointer;
      transition: color 0.15s ease, background 0.15s ease, border-color 0.15s ease;
    }
    .chip:hover { color: var(--ink); border-color: var(--border-strong); }
    .chip .chip-n {
      font-variant-numeric: tabular-nums; font-weight: 600; font-size: 0.78rem;
      color: var(--ink-muted);
    }
    .chip[aria-pressed="true"] {
      color: var(--ink); background: var(--hover); border-color: var(--border-strong);
    }
    .chip-pass[aria-pressed="true"] {
      color: var(--pass-ink); background: var(--pass-bg);
      border-color: color-mix(in oklch, var(--pass-solid) 45%, transparent);
    }
    .chip-fail[aria-pressed="true"] {
      color: var(--fail-ink); background: var(--fail-bg);
      border-color: color-mix(in oklch, var(--fail-solid) 45%, transparent);
    }
    .chip-other[aria-pressed="true"] {
      color: var(--warn-ink); background: var(--warn-bg);
      border-color: color-mix(in oklch, var(--warn-solid) 55%, transparent);
    }
    .chip[aria-pressed="true"] .chip-n { color: inherit; }
    .bulk { display: flex; gap: 0.25rem; margin-left: auto; }
    .txtbtn {
      background: none; border: 0; font: inherit; font-size: 0.82rem;
      color: var(--ink-muted); cursor: pointer; padding: 0.4rem 0.55rem; border-radius: 7px;
    }
    .txtbtn:hover { color: var(--accent); background: var(--hover); }

    /* Category sections */
    .cat { margin-top: 2.25rem; }
    .cat-head {
      display: flex; align-items: baseline; gap: 0.75rem; flex-wrap: wrap;
      padding-bottom: 0.5rem; border-bottom: 1px solid var(--border);
    }
    .cat-head h2 {
      font-size: 1.1rem; font-weight: 650; letter-spacing: -0.01em; margin: 0;
    }
    .cat.ext .cat-head h2 { color: var(--ext); }
    .cat-count {
      font-size: 0.85rem; color: var(--ink-muted); font-variant-numeric: tabular-nums;
    }
    .cat-badge {
      font-size: 0.75rem; font-weight: 600; padding: 0.1rem 0.5rem; border-radius: 999px;
      margin-left: auto;
    }
    .cat-badge.ok { color: var(--pass-ink); background: var(--pass-bg); }
    .cat-badge.bad { color: var(--fail-ink); background: var(--fail-bg); }
    .note { margin: 0.6rem 0 0; font-size: 0.85rem; color: var(--ink-muted); }

    /* Rows */
    .tbl { margin-top: 0.4rem; }
    .row { border-bottom: 1px solid var(--border); }
    .row[data-outcome="failed"] { background: var(--fail-row); }
    .row[data-outcome="other"] { background: var(--warn-row); }
    .rowhead {
      display: grid; align-items: center; gap: 0.15rem 0.6rem; padding: 0.5rem 0.6rem;
      grid-template-columns: 1.1rem 1fr auto;
      grid-template-areas: "caret name pill" "msg msg msg";
    }
    @media (min-width: 52rem) {
      .rowhead {
        grid-template-columns: 1.1rem minmax(0, 22rem) 7.5rem minmax(0, 1fr);
        grid-template-areas: "caret name pill msg";
      }
    }
    details.row > summary.rowhead { cursor: pointer; list-style: none; }
    details.row > summary.rowhead::-webkit-details-marker { display: none; }
    details.row > summary:hover { background: var(--hover); }
    details.row > summary:focus-visible {
      outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 7px;
    }
    .c-caret { grid-area: caret; display: inline-flex; }
    details.row > summary .c-caret::before {
      content: ""; width: 0.42rem; height: 0.42rem; margin-left: 0.15rem;
      border-right: 2px solid var(--ink-muted); border-bottom: 2px solid var(--ink-muted);
      transform: rotate(-45deg); transition: transform 0.15s ease;
    }
    details.row[open] > summary .c-caret::before { transform: rotate(45deg); }
    .c-name {
      grid-area: name; min-width: 0; font-size: 0.86rem; overflow-wrap: anywhere;
      color: var(--ink);
    }
    .c-pill { grid-area: pill; justify-self: start; }
    .c-msg {
      grid-area: msg; font-size: 0.82rem; color: var(--ink-muted); overflow-wrap: anywhere;
    }
    .c-msg:empty { display: none; }
    .pill {
      display: inline-flex; align-items: center; gap: 0.4rem;
      padding: 0.15rem 0.55rem; border-radius: 999px;
      font-size: 0.76rem; font-weight: 600; white-space: nowrap;
    }
    .pill .dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: currentColor; flex: none; }
    .pill.passed { color: var(--pass-ink); background: var(--pass-bg); }
    .pill.failed { color: var(--fail-ink); background: var(--fail-bg); }
    .pill.other { color: var(--warn-ink); background: var(--warn-bg); }

    /* Expanded source panel */
    .panel { padding: 0.25rem 0.6rem 0.9rem 1.85rem; display: grid; gap: 0.7rem; }
    .snip { display: grid; gap: 0.3rem; }
    .snip-label {
      font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--ink-muted);
    }
    .snip pre {
      margin: 0; padding: 0.7rem 0.85rem; font-size: 0.8rem; line-height: 1.55;
      background: var(--surface-2); border: 1px solid var(--border);
      border-radius: var(--radius-sm); overflow-x: auto;
    }
    .snip-inferred .snip-label { color: var(--accent); }
    .snip-inferred pre {
      background: color-mix(in oklch, var(--accent) 8%, var(--surface));
      border-color: color-mix(in oklch, var(--accent) 30%, var(--border));
    }
    details.row[open] > .panel { animation: reveal 0.18s ease; }
    @keyframes reveal { from { opacity: 0; transform: translateY(-2px); } to { opacity: 1; } }

    .empty { text-align: center; color: var(--ink-muted); padding: 3rem 1rem; font-size: 0.95rem; }
    .foot {
      margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid var(--border);
      color: var(--ink-muted); font-size: 0.82rem;
    }

    @media (prefers-reduced-motion: reduce) {
      * { transition: none !important; animation: none !important; }
    }
    """

    _JS = """
    (function () {
      var rows = [].slice.call(document.querySelectorAll('.row'));
      var sections = [].slice.call(document.querySelectorAll('.cat'));
      var chips = [].slice.call(document.querySelectorAll('.chip'));
      var q = document.getElementById('q');
      var empty = document.getElementById('empty');
      var state = { q: '', f: 'all' };

      function apply() {
        var term = state.q.trim().toLowerCase();
        var any = false;
        rows.forEach(function (row) {
          var okF = state.f === 'all' || row.getAttribute('data-outcome') === state.f;
          var okQ = !term || row.getAttribute('data-name').toLowerCase().indexOf(term) > -1;
          var vis = okF && okQ;
          row.hidden = !vis;
          if (vis) any = true;
        });
        sections.forEach(function (sec) {
          sec.hidden = sec.querySelectorAll('.row:not([hidden])').length === 0;
        });
        empty.hidden = any;
      }

      function setFilter(f) {
        state.f = f;
        chips.forEach(function (c) {
          c.setAttribute('aria-pressed', c.getAttribute('data-filter') === f ? 'true' : 'false');
        });
        apply();
      }

      q.addEventListener('input', function () { state.q = q.value; apply(); });
      chips.forEach(function (c) {
        c.addEventListener('click', function () { setFilter(c.getAttribute('data-filter')); });
      });
      [].slice.call(document.querySelectorAll('[data-filter-set]')).forEach(function (el) {
        el.addEventListener('click', function () { setFilter(el.getAttribute('data-filter-set')); });
      });
      [].slice.call(document.querySelectorAll('[data-bulk]')).forEach(function (b) {
        b.addEventListener('click', function () {
          var open = b.getAttribute('data-bulk') === 'expand';
          rows.forEach(function (r) {
            if (r.tagName === 'DETAILS' && !r.hidden) r.open = open;
          });
        });
      });

      var tbtn = document.getElementById('theme');
      function resolved() {
        return document.documentElement.getAttribute('data-theme') ||
          (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      }
      function syncTheme() { if (tbtn) tbtn.setAttribute('data-mode', resolved()); }
      if (tbtn) {
        syncTheme();
        tbtn.addEventListener('click', function () {
          var next = resolved() === 'dark' ? 'light' : 'dark';
          document.documentElement.setAttribute('data-theme', next);
          try { localStorage.setItem('srl-theme', next); } catch (e) {}
          syncTheme();
        });
      }
      apply();
    })();
    """

    _THEME_BOOT = (
        "try{var t=localStorage.getItem('srl-theme');"
        "if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}"
    )

    _SUN = (
        '<svg class="ic i-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2'
        'M5 5l1.4 1.4M17.2 17.2L18.6 18.6M18.6 5.4L17.2 6.8M6.8 17.2L5.4 18.6"/></svg>'
    )
    _MOON = (
        '<svg class="ic i-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        'aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
    )
    _SEARCH_ICON = (
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
        '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>'
    )
    _PLAY_ICON = (
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" '
        'aria-hidden="true"><path d="M7 5.2c0-.9 1-1.5 1.8-1L18.6 10a1.2 1.2 0 0 1 0 2.1'
        'L8.8 17.9c-.8.5-1.8-.1-1.8-1V5.2z"/></svg>'
    )
    _ARROW_ICON = (
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M5 12h14M13 6l6 6-6 6"/></svg>'
    )

    # Playground styles. Reuses the report's tokens (surface / border / ink /
    # accent / pass-fail-warn / radius); adds only editor-gutter, panel-grid,
    # and run-state pieces. Kept in a separate constant so the report CSS above
    # stays untouched and legible.
    _PG_CSS = """
    .pg {
      margin: 1.5rem 0 0.5rem; padding: 1.4rem 1.5rem 1.6rem;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); box-shadow: var(--shadow);
    }
    .pg-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.6rem 1rem; }
    .pg-head h2 {
      font-size: 1.1rem; font-weight: 650; letter-spacing: -0.01em; margin: 0;
      display: flex; align-items: center; gap: 0.55rem;
    }
    .pg-head h2 .tag {
      font-size: 0.68rem; font-weight: 600; letter-spacing: 0.02em; color: var(--accent);
      background: color-mix(in oklch, var(--accent) 14%, transparent);
      padding: 0.15rem 0.5rem; border-radius: 999px;
    }
    .pg-sub { margin: 0; color: var(--ink-muted); font-size: 0.9rem; flex: 1 1 16rem; }
    .pg-engine {
      display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.78rem;
      color: var(--ink-muted); white-space: nowrap;
    }
    .pg-engine .dot {
      width: 0.5rem; height: 0.5rem; border-radius: 50%; flex: none;
      background: var(--warn-solid); transition: background 0.2s ease;
    }
    .pg-engine[data-state="ready"] .dot { background: var(--pass-solid); }
    .pg-engine[data-state="error"] .dot { background: var(--fail-solid); }
    .pg-engine .lbl-loading { display: inline; }
    .pg-engine .lbl-ready, .pg-engine .lbl-error { display: none; }
    .pg-engine[data-state="ready"] .lbl-loading,
    .pg-engine[data-state="ready"] .lbl-error { display: none; }
    .pg-engine[data-state="ready"] .lbl-ready { display: inline; }
    .pg-engine[data-state="error"] .lbl-loading,
    .pg-engine[data-state="error"] .lbl-ready { display: none; }
    .pg-engine[data-state="error"] .lbl-error { display: inline; }
    .pg-engine .spin {
      width: 0.85rem; height: 0.85rem; border-radius: 50%; flex: none;
      border: 2px solid color-mix(in oklch, var(--ink-muted) 35%, transparent);
      border-top-color: var(--ink-muted); animation: pg-spin 0.7s linear infinite;
    }
    .pg-engine[data-state="ready"] .spin, .pg-engine[data-state="error"] .spin { display: none; }
    @keyframes pg-spin { to { transform: rotate(360deg); } }

    /* Presets + extension toggle */
    .pg-controls {
      display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem;
      margin: 1rem 0 0.9rem;
    }
    .pg-presets { display: flex; flex-wrap: wrap; gap: 0.35rem; }
    .pg-preset {
      font: inherit; font-size: 0.82rem; font-weight: 500; cursor: pointer;
      padding: 0.35rem 0.7rem; border-radius: 999px; color: var(--ink-muted);
      background: var(--surface-2); border: 1px solid var(--border);
      transition: color 0.15s ease, background 0.15s ease, border-color 0.15s ease;
    }
    .pg-preset:hover { color: var(--ink); border-color: var(--border-strong); }
    .pg-preset[aria-pressed="true"] {
      color: var(--accent); background: color-mix(in oklch, var(--accent) 12%, var(--surface));
      border-color: color-mix(in oklch, var(--accent) 45%, transparent);
    }
    .pg-preset.is-ext::after {
      content: "ext"; margin-left: 0.4rem; font-size: 0.62rem; font-weight: 700;
      letter-spacing: 0.03em; color: var(--ext); vertical-align: 0.05em;
    }
    .pg-ext-toggle {
      display: inline-flex; align-items: center; gap: 0.5rem; margin-left: auto;
      font-size: 0.82rem; color: var(--ink-muted); cursor: pointer; user-select: none;
    }
    .pg-ext-toggle input { position: absolute; opacity: 0; width: 0; height: 0; }
    .pg-ext-toggle .track {
      width: 2.1rem; height: 1.15rem; border-radius: 999px; flex: none; position: relative;
      background: var(--surface-2); border: 1px solid var(--border-strong);
      transition: background 0.18s ease, border-color 0.18s ease;
    }
    .pg-ext-toggle .track::after {
      content: ""; position: absolute; top: 50%; left: 0.12rem; transform: translateY(-50%);
      width: 0.85rem; height: 0.85rem; border-radius: 50%; background: var(--ink-muted);
      transition: transform 0.18s cubic-bezier(0.22, 1, 0.36, 1), background 0.18s ease;
    }
    .pg-ext-toggle input:checked + .track {
      background: color-mix(in oklch, var(--ext) 30%, transparent); border-color: var(--ext);
    }
    .pg-ext-toggle input:checked + .track::after { transform: translateY(-50%) translateX(0.92rem); background: var(--ext); }
    .pg-ext-toggle input:focus-visible + .track {
      outline: 2px solid var(--accent); outline-offset: 2px;
    }
    .pg-ext-toggle b { color: var(--ext); font-weight: 600; }

    /* Editor grid */
    .pg-grid { display: grid; gap: 0.9rem; grid-template-columns: 1fr; }
    @media (min-width: 54rem) { .pg-grid { grid-template-columns: 1fr 1fr; } }
    .pg.has-shapes .pg-grid .ed-shapes { grid-column: 1 / -1; }
    .ed { display: grid; gap: 0.35rem; min-width: 0; }
    .ed.ed-shapes { display: none; }
    .pg.has-shapes .ed.ed-shapes { display: grid; }
    .ed-top { display: flex; align-items: baseline; justify-content: space-between; gap: 0.5rem; }
    .ed-label {
      font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.05em; color: var(--ink-muted);
    }
    .ed-shapes .ed-label { color: var(--ext); }
    .ed-hint { font-size: 0.72rem; color: var(--ink-muted); }
    .ed-box {
      position: relative; display: grid; grid-template-columns: auto 1fr;
      background: var(--surface-2); border: 1px solid var(--border);
      border-radius: var(--radius-sm); overflow: hidden;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .ed-box:focus-within {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent) 22%, transparent);
    }
    .ed-box.invalid { border-color: color-mix(in oklch, var(--fail-solid) 55%, var(--border)); }
    .ed-box.invalid:focus-within {
      box-shadow: 0 0 0 3px color-mix(in oklch, var(--fail-solid) 22%, transparent);
    }
    .ed-gutter {
      margin: 0; padding: 0.7rem 0.5rem 0.7rem 0.7rem; text-align: right;
      font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
      font-size: 0.8rem; line-height: 1.6; color: var(--ink-muted);
      background: color-mix(in oklch, var(--ink) 4%, var(--surface-2));
      border-right: 1px solid var(--border); user-select: none;
      overflow: hidden; white-space: pre; opacity: 0.7; min-width: 2.4rem;
    }
    .ed-ta {
      margin: 0; padding: 0.7rem 0.85rem; border: 0; resize: vertical;
      width: 100%; min-height: 12.5rem; background: transparent; color: var(--ink);
      font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
      font-size: 0.8rem; line-height: 1.6; tab-size: 4; white-space: pre;
      overflow-wrap: normal; overflow-x: auto;
    }
    .ed-shapes .ed-ta { min-height: 8rem; }
    .ed-ta:focus { outline: none; }
    .ed-ta::placeholder { color: var(--ink-muted); }

    /* Run bar */
    .pg-run { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin: 1rem 0 0; }
    .pg-btn {
      display: inline-flex; align-items: center; gap: 0.5rem; cursor: pointer;
      font: inherit; font-size: 0.9rem; font-weight: 600; padding: 0.55rem 1.1rem;
      color: oklch(1 0 0); background: var(--accent); border: 1px solid transparent;
      border-radius: 10px; transition: filter 0.15s ease, transform 0.06s ease;
    }
    .pg-btn:hover { filter: brightness(1.07); }
    .pg-btn:active { transform: translateY(1px); }
    .pg-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .pg-btn[disabled] { opacity: 0.55; cursor: not-allowed; filter: none; transform: none; }
    .pg-btn .spin {
      width: 0.9rem; height: 0.9rem; border-radius: 50%; flex: none; display: none;
      border: 2px solid oklch(1 0 0 / 0.4); border-top-color: oklch(1 0 0);
      animation: pg-spin 0.7s linear infinite;
    }
    .pg.is-running .pg-btn .spin { display: inline-block; }
    .pg.is-running .pg-btn .pg-btn-ic { display: none; }
    .pg-share {
      display: inline-flex; align-items: center; gap: 0.4rem; cursor: pointer;
      font: inherit; font-size: 0.82rem; color: var(--ink-muted);
      background: none; border: 1px solid var(--border); border-radius: 8px;
      padding: 0.5rem 0.75rem; transition: color 0.15s ease, border-color 0.15s ease;
    }
    .pg-share:hover { color: var(--ink); border-color: var(--border-strong); }
    .pg-share.copied { color: var(--pass-ink); border-color: color-mix(in oklch, var(--pass-solid) 45%, transparent); }
    .pg-runhint { font-size: 0.8rem; color: var(--ink-muted); margin-left: auto; }
    kbd {
      font-family: ui-monospace, monospace; font-size: 0.72rem; padding: 0.1rem 0.35rem;
      border: 1px solid var(--border-strong); border-bottom-width: 2px; border-radius: 5px;
      background: var(--surface-2); color: var(--ink-muted);
    }

    /* Output */
    .pg-out { margin-top: 1.15rem; display: grid; gap: 0.9rem; }
    .pg-out[hidden] { display: none; }
    .pg-stats { display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem; align-items: baseline; }
    .pg-stat { display: inline-flex; align-items: baseline; gap: 0.4rem; }
    .pg-stat b {
      font-size: 1.15rem; font-weight: 700; font-variant-numeric: tabular-nums;
      letter-spacing: -0.01em; color: var(--ink);
    }
    .pg-stat.pg-hero b { color: var(--pass-ink); }
    .pg-stat span {
      font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--ink-muted);
    }
    .pg-diag { display: grid; gap: 0.4rem; margin: 0; padding: 0; list-style: none; }
    .pg-diag li {
      display: grid; grid-template-columns: auto auto 1fr; gap: 0.5rem 0.6rem;
      align-items: baseline; padding: 0.5rem 0.7rem; font-size: 0.82rem;
      border-radius: var(--radius-sm); border: 1px solid transparent;
    }
    .pg-diag .d-tag {
      font-size: 0.64rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
      padding: 0.1rem 0.4rem; border-radius: 5px; white-space: nowrap;
    }
    .pg-diag .d-loc {
      font-family: ui-monospace, monospace; font-size: 0.74rem; color: var(--ink-muted);
      white-space: nowrap;
    }
    .pg-diag .d-msg { overflow-wrap: anywhere; color: var(--ink); }
    .pg-diag li.error { background: var(--fail-bg); border-color: color-mix(in oklch, var(--fail-solid) 30%, transparent); }
    .pg-diag li.error .d-tag { color: oklch(1 0 0); background: var(--fail-solid); }
    .pg-diag li.warning { background: var(--warn-bg); border-color: color-mix(in oklch, var(--warn-solid) 40%, transparent); }
    .pg-diag li.warning .d-tag { color: var(--warn-ink); background: color-mix(in oklch, var(--warn-solid) 45%, transparent); }
    .pg-diag li.info { background: var(--surface-2); border-color: var(--border); }
    .pg-diag li.info .d-tag { color: var(--accent); background: color-mix(in oklch, var(--accent) 15%, transparent); }
    .pg-diag li.strat .d-tag::after { content: " · strat"; font-weight: 600; opacity: 0.8; }

    .pg-result-head {
      display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap;
      font-size: 0.82rem; color: var(--ink-muted);
    }
    .pg-result-head b { color: var(--ink); font-size: 0.95rem; }
    .pg-table-wrap { border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: auto; max-height: 26rem; }
    table.pg-triples { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    table.pg-triples th {
      position: sticky; top: 0; z-index: 1; text-align: left; font-weight: 600;
      font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--ink-muted); background: var(--surface-2);
      padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); white-space: nowrap;
    }
    table.pg-triples td {
      padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--border);
      vertical-align: top; overflow-wrap: anywhere;
    }
    table.pg-triples tr:last-child td { border-bottom: 0; }
    table.pg-triples tbody tr:hover { background: var(--hover); }
    table.pg-triples .t-term {
      font-family: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
      font-size: 0.78rem; color: var(--ink);
    }
    table.pg-triples .t-rule { white-space: nowrap; }
    .pg-rulebadge {
      display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.72rem;
      padding: 0.12rem 0.5rem; border-radius: 999px; color: var(--accent);
      background: color-mix(in oklch, var(--accent) 12%, transparent);
    }
    .pg-rulebadge .it {
      font-variant-numeric: tabular-nums; font-size: 0.66rem; color: var(--ink-muted);
    }
    .pg-empty-out {
      padding: 1.5rem 1rem; text-align: center; font-size: 0.86rem; color: var(--ink-muted);
      background: var(--surface-2); border: 1px dashed var(--border); border-radius: var(--radius-sm);
    }
    .pg-empty-out.ok { color: var(--pass-ink); border-color: color-mix(in oklch, var(--pass-solid) 35%, transparent); }
    .pg-note {
      margin: 0.9rem 0 0; padding: 0.7rem 0.85rem; font-size: 0.8rem; line-height: 1.5;
      color: var(--ext); background: color-mix(in oklch, var(--ext) 8%, var(--surface));
      border: 1px solid color-mix(in oklch, var(--ext) 30%, var(--border));
      border-radius: var(--radius-sm);
    }
    .pg-note[hidden] { display: none; }
    .pg-fail {
      margin-top: 1rem; padding: 0.8rem 0.95rem; font-size: 0.85rem; line-height: 1.5;
      color: var(--fail-ink); background: var(--fail-bg);
      border: 1px solid color-mix(in oklch, var(--fail-solid) 35%, transparent);
      border-radius: var(--radius-sm);
    }
    .pg-fail[hidden] { display: none; }
    .pg-fail code { font-size: 0.78rem; overflow-wrap: anywhere; }
    .pg-credit {
      margin: 1.15rem 0 0; padding-top: 0.9rem; border-top: 1px solid var(--border);
      font-size: 0.78rem; line-height: 1.55; color: var(--ink-muted);
    }
    .pg-credit code { font-size: 0.76rem; color: var(--ink); }
    .pg-credit a { color: var(--accent); text-underline-offset: 2px; }
    """

    def __init__(self, project_name: str = "shacl-rules", project_version: Optional[str] = None):
        self.project_name = project_name
        self.project_version = project_version or SRL_VERSION
        self.results: List[TestResult] = []
        self.runner: Optional["SHACLRulesTestRunner"] = None

    def add_results(
        self, results: List[TestResult], runner: Optional["SHACLRulesTestRunner"] = None
    ) -> None:
        self.results = results
        self.runner = runner

    @staticmethod
    def _outcome_cls(outcome: TestOutcome) -> str:
        return {TestOutcome.PASSED: "passed", TestOutcome.FAILED: "failed"}.get(outcome, "other")

    def _row_html(self, r: TestResult) -> str:
        cls = self._outcome_cls(r.outcome)
        name = _html.escape(r.test.name)
        name_attr = _html.escape(r.test.name, quote=True)
        msg = _html.escape(r.message or "")
        pill = (
            f'<span class="pill c-pill {cls}"><span class="dot"></span>'
            f"{_html.escape(r.outcome.value)}</span>"
        )
        head = (
            '<span class="c-caret" aria-hidden="true"></span>'
            f'<code class="c-name">{name}</code>{pill}'
            f'<span class="c-msg">{msg}</span>'
        )

        # (label, text, kind) — kind "src" is a static input file, "inferred" is
        # the runtime output the engine actually produced for an eval test.
        snippets: List[tuple] = [
            (label, text, "src")
            for label, text in (collect_source_snippets(self.runner, r.test) if self.runner else [])
            if text.strip()
        ]
        if r.inferred is not None:
            snippets.append(("inferred (actual)", r.inferred, "inferred"))

        if not snippets:
            return (
                f'<div class="row static" data-outcome="{cls}" data-name="{name_attr}">'
                f'<div class="rowhead">{head}</div></div>'
            )

        panel = ['<div class="panel">']
        for label, text, kind in snippets:
            panel.append(
                f'<div class="snip snip-{kind}">'
                f'<span class="snip-label">{_html.escape(label)}</span>'
                f"<pre>{_html.escape(text.rstrip())}</pre></div>"
            )
        panel.append("</div>")
        return (
            f'<details class="row" data-outcome="{cls}" data-name="{name_attr}">'
            f'<summary class="rowhead">{head}</summary>{"".join(panel)}</details>'
        )

    # Pinned engine version: the browser loads this exact release from esm.sh,
    # which bundles its chevrotain + n3 deps for a no-build ES module import.
    _ENGINE_PKG = "srl-engine@0.1.0"

    def _playground_html(self) -> str:
        """The in-report SRL playground section (rendered before the toolbar).

        All rule evaluation happens client-side in the visitor's browser via the
        srl-engine ES module; the report itself ships no engine code and stays a
        static file. If the module fails to load, the section degrades to an
        explicit error state and the rest of the report is unaffected.
        """
        first = PLAYGROUND_PRESETS[0]
        preset_buttons = []
        for i, p in enumerate(PLAYGROUND_PRESETS):
            ext_cls = " is-ext" if p.get("extension") else ""
            pressed = "true" if i == 0 else "false"
            preset_buttons.append(
                f'<button class="pg-preset{ext_cls}" type="button" role="tab" '
                f'data-preset="{_html.escape(p["id"], quote=True)}" '
                f'aria-pressed="{pressed}" title="{_html.escape(p["blurb"], quote=True)}">'
                f'{_html.escape(p["label"])}</button>'
            )
        presets_json = _html.escape(json.dumps(PLAYGROUND_PRESETS), quote=True)

        return (
            '<section class="pg" id="playground" aria-labelledby="pg-title" '
            f'data-presets="{presets_json}" data-engine-pkg="{self._ENGINE_PKG}">'
            '<div class="pg-head">'
            '<h2 id="pg-title">Playground <span class="tag">try it</span></h2>'
            '<p class="pg-sub">Write SRL rules and RDF data, then evaluate them in your '
            "browser. Each inferred triple is tagged with the rule that produced it.</p>"
            '<span class="pg-engine" id="pg-engine" data-state="loading" role="status" '
            'aria-live="polite">'
            '<span class="spin" aria-hidden="true"></span>'
            '<span class="dot" aria-hidden="true"></span>'
            f'<span class="lbl-loading">Loading engine …</span>'
            '<span class="lbl-ready">Engine ready</span>'
            '<span class="lbl-error">Engine unavailable</span>'
            "</span></div>"
            # Presets + extension toggle
            '<div class="pg-controls">'
            '<div class="pg-presets" role="tablist" aria-label="Preset scenarios">'
            f'{"".join(preset_buttons)}</div>'
            '<label class="pg-ext-toggle" title="Enable the opt-in FOR-IN rule-to-shape '
            'targeting extension (not part of the W3C SRL spec)">'
            '<input type="checkbox" id="pg-ext"><span class="track" aria-hidden="true"></span>'
            "<span>Enable <b>extensions</b></span></label></div>"
            # Editors
            '<div class="pg-grid">'
            '<div class="ed"><div class="ed-top">'
            '<label class="ed-label" for="pg-rules">Rules (SRL)</label>'
            '<span class="ed-hint">grammar-validated live</span></div>'
            '<div class="ed-box" id="pg-rules-box"><pre class="ed-gutter" id="pg-rules-gutter" '
            'aria-hidden="true">1</pre>'
            '<textarea class="ed-ta" id="pg-rules" spellcheck="false" autocomplete="off" '
            'autocapitalize="off" wrap="off" aria-label="SRL rules">'
            f'{_html.escape(first["rules"])}</textarea></div></div>'
            '<div class="ed"><div class="ed-top">'
            '<label class="ed-label" for="pg-data">Data (Turtle)</label>'
            '<span class="ed-hint">RDF input graph</span></div>'
            '<div class="ed-box" id="pg-data-box"><pre class="ed-gutter" id="pg-data-gutter" '
            'aria-hidden="true">1</pre>'
            '<textarea class="ed-ta" id="pg-data" spellcheck="false" autocomplete="off" '
            'autocapitalize="off" wrap="off" aria-label="RDF data in Turtle">'
            f'{_html.escape(first["data"])}</textarea></div></div>'
            '<div class="ed ed-shapes"><div class="ed-top">'
            '<label class="ed-label" for="pg-shapes">Shapes (Turtle)</label>'
            '<span class="ed-hint">SHACL shapes graph — extension only</span></div>'
            '<div class="ed-box" id="pg-shapes-box"><pre class="ed-gutter" id="pg-shapes-gutter" '
            'aria-hidden="true">1</pre>'
            '<textarea class="ed-ta" id="pg-shapes" spellcheck="false" autocomplete="off" '
            'autocapitalize="off" wrap="off" aria-label="SHACL shapes in Turtle"></textarea>'
            "</div></div></div>"
            # Run bar
            '<div class="pg-run">'
            '<button class="pg-btn" id="pg-run" type="button">'
            '<span class="spin" aria-hidden="true"></span>'
            f'<span class="pg-btn-ic" aria-hidden="true">{self._PLAY_ICON}</span>'
            "Run</button>"
            '<button class="pg-share" id="pg-share" type="button" title="Copy a link that '
            'restores these editors">'
            '<span aria-hidden="true">\U0001f517</span><span class="pg-share-lbl">Share</span>'
            "</button>"
            '<span class="pg-runhint">Press <kbd>Ctrl</kbd>+<kbd>Enter</kbd> to run</span>'
            "</div>"
            # Extension note (shown when extensions on)
            '<p class="pg-note" id="pg-note" hidden>Extensions on — the '
            "<code>FOR … IN</code> rule-to-shape targeting clause is an opt-in feature of "
            "this implementation and is <b>not part of the W3C SHACL 1.2 Rules specification</b>."
            "</p>"
            # Engine load failure
            '<div class="pg-fail" id="pg-fail" hidden></div>'
            # Output
            '<div class="pg-out" id="pg-out" hidden>'
            '<div class="pg-stats" id="pg-stats"></div>'
            '<ul class="pg-diag" id="pg-diag"></ul>'
            '<div id="pg-result"></div>'
            "</div>"
            # Credit: the browser-side engine is a separate JS library.
            f"{self._playground_credit()}"
            "</section>"
        )

    def _playground_credit(self) -> str:
        """A disclaimer crediting the client-side engine (a distinct JS library)."""
        pkg_name = self._ENGINE_PKG.split("@")[0]
        version = self._ENGINE_PKG.split("@")[1] if "@" in self._ENGINE_PKG else ""
        npm_url = f"https://www.npmjs.com/package/{pkg_name}"
        ver_txt = f" v{version}" if version else ""
        return (
            '<p class="pg-credit">Rule evaluation in this playground runs entirely in your '
            "browser, powered by "
            f'<a href="{npm_url}" target="_blank" rel="noopener noreferrer">'
            f"<code>{_html.escape(pkg_name)}</code></a>{_html.escape(ver_txt)} — an "
            "independent JavaScript SRL parser and engine, distinct from the Python "
            "implementation this report tests. It is loaded on demand from a public CDN.</p>"
        )

    _PG_JS = """
    (function () {
      var root = document.getElementById('playground');
      if (!root) return;
      var presets = JSON.parse(root.getAttribute('data-presets') || '[]');
      var pkg = root.getAttribute('data-engine-pkg');
      var byId = presets.reduce(function (m, p) { m[p.id] = p; return m; }, {});

      var els = {
        engine: document.getElementById('pg-engine'),
        rules: document.getElementById('pg-rules'),
        data: document.getElementById('pg-data'),
        shapes: document.getElementById('pg-shapes'),
        ext: document.getElementById('pg-ext'),
        note: document.getElementById('pg-note'),
        run: document.getElementById('pg-run'),
        share: document.getElementById('pg-share'),
        shareLbl: document.querySelector('#pg-share .pg-share-lbl'),
        fail: document.getElementById('pg-fail'),
        out: document.getElementById('pg-out'),
        stats: document.getElementById('pg-stats'),
        diag: document.getElementById('pg-diag'),
        result: document.getElementById('pg-result'),
      };
      var presetBtns = [].slice.call(root.querySelectorAll('.pg-preset'));
      var engine = null;

      function esc(s) {
        return String(s).replace(/[&<>"]/g, function (c) {
          return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
        });
      }

      /* --- line-number gutters, synced to scroll --- */
      function wireGutter(taId, gutterId) {
        var ta = document.getElementById(taId), g = document.getElementById(gutterId);
        if (!ta || !g) return;
        function sync() {
          var n = ta.value.split('\\n').length, s = '';
          for (var i = 1; i <= n; i++) s += i + (i < n ? '\\n' : '');
          g.textContent = s;
        }
        ta.addEventListener('input', sync);
        ta.addEventListener('scroll', function () { g.scrollTop = ta.scrollTop; });
        sync();
      }
      wireGutter('pg-rules', 'pg-rules-gutter');
      wireGutter('pg-data', 'pg-data-gutter');
      wireGutter('pg-shapes', 'pg-shapes-gutter');

      /* --- extension toggle: reveal shapes editor + non-spec note --- */
      function syncExt() {
        var on = els.ext.checked;
        root.classList.toggle('has-shapes', on);
        els.note.hidden = !on;
      }
      els.ext.addEventListener('change', function () {
        syncExt();
        // re-fire input on shapes gutter so line numbers show once visible
        els.shapes.dispatchEvent(new Event('input'));
      });

      /* --- presets --- */
      function applyPreset(id) {
        var p = byId[id];
        if (!p) return;
        els.rules.value = p.rules || '';
        els.data.value = p.data || '';
        els.shapes.value = p.shapes || '';
        els.ext.checked = !!p.extension;
        syncExt();
        presetBtns.forEach(function (b) {
          b.setAttribute('aria-pressed', b.getAttribute('data-preset') === id ? 'true' : 'false');
        });
        [els.rules, els.data, els.shapes].forEach(function (ta) {
          ta.dispatchEvent(new Event('input'));
        });
      }
      presetBtns.forEach(function (b) {
        b.addEventListener('click', function () { applyPreset(b.getAttribute('data-preset')); });
      });

      /* --- editors that clear the active-preset highlight when hand-edited --- */
      [els.rules, els.data, els.shapes].forEach(function (ta) {
        ta.addEventListener('input', function () {
          presetBtns.forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
        });
      });

      /* --- share via URL hash (base64 of the editor state) --- */
      function b64e(s) { return btoa(unescape(encodeURIComponent(s))); }
      function b64d(s) { return decodeURIComponent(escape(atob(s))); }
      function readHash() {
        if (!location.hash || location.hash.length < 2) return false;
        try {
          var st = JSON.parse(b64d(location.hash.slice(1)));
          if (st && typeof st.r === 'string') {
            els.rules.value = st.r || '';
            els.data.value = st.d || '';
            els.shapes.value = st.s || '';
            els.ext.checked = !!st.x;
            syncExt();
            presetBtns.forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
            [els.rules, els.data, els.shapes].forEach(function (ta) {
              ta.dispatchEvent(new Event('input'));
            });
            return true;
          }
        } catch (e) { /* malformed hash: ignore, keep default preset */ }
        return false;
      }
      els.share.addEventListener('click', function () {
        var st = { r: els.rules.value, d: els.data.value };
        if (els.shapes.value) st.s = els.shapes.value;
        if (els.ext.checked) st.x = 1;
        var hash = '#' + b64e(JSON.stringify(st));
        try { history.replaceState(null, '', location.pathname + location.search + hash); }
        catch (e) { location.hash = hash; }
        var link = location.href;
        var done = function () {
          els.share.classList.add('copied');
          els.shareLbl.textContent = 'Link copied';
          setTimeout(function () {
            els.share.classList.remove('copied');
            els.shareLbl.textContent = 'Share';
          }, 1800);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(link).then(done, done);
        } else { done(); }
      });

      /* --- render helpers --- */
      function renderDiagnostics(messages) {
        els.diag.innerHTML = '';
        if (!messages || !messages.length) return 0;
        var errors = 0;
        messages.forEach(function (m) {
          if (m.type === 'error') errors++;
          var li = document.createElement('li');
          li.className = m.type + (m.category === 'stratification' ? ' strat' : '');
          var loc = (m.startLine ? 'L' + m.startLine + (m.startColumn ? ':' + m.startColumn : '') : '');
          li.innerHTML =
            '<span class="d-tag">' + esc(m.type) + '</span>' +
            '<span class="d-loc">' + esc(loc) + '</span>' +
            '<span class="d-msg">' + esc(m.message) + '</span>';
          els.diag.appendChild(li);
        });
        return errors;
      }

      function stat(value, label, hero) {
        return '<span class="pg-stat' + (hero ? ' pg-hero' : '') + '"><b>' +
          esc(value) + '</b><span>' + esc(label) + '</span></span>';
      }

      // Collapse a full IRI to prefix:local using the rule set's prefixes, so a
      // named rule reads `ex:GrandparentRule` rather than the bare IRI.
      function collapseIri(iri, prefixes) {
        if (!prefixes || !iri || iri.indexOf('://') === -1) return iri;
        var best = null;
        prefixes.forEach(function (ns, prefix) {
          if (iri.indexOf(ns) === 0 && (!best || ns.length > best.ns.length)) {
            best = { prefix: prefix, ns: ns };
          }
        });
        return best ? best.prefix + ':' + iri.slice(best.ns.length) : iri;
      }

      // Tidy a displayed object term: drop the implicit ^^xsd:string datatype and
      // collapse any remaining ^^<datatype> IRI to prefixed form.
      function tidyTerm(term, prefixes) {
        var m = /^(".*?")\\^\\^<([^>]+)>$/.exec(term);
        if (!m) return term;
        if (m[2] === 'http://www.w3.org/2001/XMLSchema#string') return m[1];
        return m[1] + '^^' + collapseIri(m[2], prefixes);
      }

      function renderResult(result, prefixes) {
        var tris = result.inferredTriples || [];
        if (!tris.length) {
          els.result.innerHTML =
            '<div class="pg-empty-out ok">Rules are valid and ran to a fixed point, but ' +
            'inferred no new triples over this data.</div>';
          return;
        }
        var rows = tris.map(function (t) {
          var d;
          try { d = engine.formatTripleForDisplay(t.quad, prefixes); }
          catch (e) { d = null; }
          var s, p, o;
          if (d) { s = d.subject; p = d.predicate; o = d.object; }
          else {
            // fall back to the engine-provided quad string, split on whitespace
            var parts = (t.quadString || '').split(/\\s+/);
            s = parts[0] || ''; p = parts[1] || ''; o = parts.slice(2).join(' ');
          }
          var rule = collapseIri((t.sourceRule && t.sourceRule.name) || 'rule', prefixes);
          var iter = (typeof t.iteration === 'number') ? t.iteration : '';
          return '<tr>' +
            '<td class="t-term">' + esc(s) + '</td>' +
            '<td class="t-term">' + esc(p) + '</td>' +
            '<td class="t-term">' + esc(tidyTerm(o, prefixes)) + '</td>' +
            '<td class="t-rule"><span class="pg-rulebadge">' + esc(rule) +
            (iter !== '' ? ' <span class="it">iter ' + esc(iter) + '</span>' : '') +
            '</span></td></tr>';
        }).join('');
        els.result.innerHTML =
          '<div class="pg-result-head"><b>' + tris.length + '</b> inferred triple' +
          (tris.length === 1 ? '' : 's') + '</div>' +
          '<div class="pg-table-wrap"><table class="pg-triples"><thead><tr>' +
          '<th>Subject</th><th>Predicate</th><th>Object</th><th>Rule</th>' +
          '</tr></thead><tbody>' + rows + '</tbody></table></div>';
      }

      /* --- run --- */
      function run() {
        if (!engine) return;
        root.classList.add('is-running');
        els.run.disabled = true;
        // let the spinner paint before the (synchronous) engine work
        requestAnimationFrame(function () { setTimeout(doRun, 0); });
      }

      function doRun() {
        var opts = {};
        var ext = els.ext.checked;
        if (ext) { opts.extensions = true; opts.shapesGraph = els.shapes.value; }
        els.out.hidden = false;
        els.result.innerHTML = '';
        try {
          var report = engine.validateSRL(els.rules.value, ext ? { extensions: true } : undefined);
          var errCount = renderDiagnostics(report.messages);

          if (!report.isValid) {
            els.stats.innerHTML =
              stat(errCount, errCount === 1 ? 'error' : 'errors') +
              stat((report.messages || []).length, 'diagnostics');
            els.result.innerHTML =
              '<div class="pg-empty-out">Fix the error' + (errCount === 1 ? '' : 's') +
              ' above, then run again.</div>';
            return;
          }

          var ruleSet = engine.buildAST(els.rules.value, ext ? { extensions: true } : undefined);
          var result = engine.executeRules(ruleSet, els.data.value, opts);

          // Display-only: seed well-known prefixes the user may not have declared,
          // so inferred terms read as rdf:type / xsd:string rather than full IRIs.
          // User-declared prefixes win on collision.
          var displayPrefixes = new Map(ruleSet.prefixes || []);
          var wellKnown = {
            rdf: 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            rdfs: 'http://www.w3.org/2000/01/rdf-schema#',
            xsd: 'http://www.w3.org/2001/XMLSchema#',
            owl: 'http://www.w3.org/2002/07/owl#',
            sh: 'http://www.w3.org/ns/shacl#'
          };
          var declaredNs = new Set(displayPrefixes.values());
          Object.keys(wellKnown).forEach(function (pfx) {
            if (!displayPrefixes.has(pfx) && !declaredNs.has(wellKnown[pfx])) {
              displayPrefixes.set(pfx, wellKnown[pfx]);
            }
          });

          if (result.errors && result.errors.length) {
            (result.errors).forEach(function (msg) {
              var li = document.createElement('li');
              li.className = 'error';
              li.innerHTML = '<span class="d-tag">error</span><span class="d-loc"></span>' +
                '<span class="d-msg">' + esc(msg) + '</span>';
              els.diag.appendChild(li);
            });
          }

          var ms = (typeof result.executionTime === 'number')
            ? (result.executionTime < 1 ? '<1' : Math.round(result.executionTime)) : '?';
          els.stats.innerHTML =
            stat((result.inferredTriples || []).length, 'inferred', true) +
            stat(result.baseTriples ? result.baseTriples.length : '?', 'base') +
            stat(result.iterations, result.iterations === 1 ? 'iteration' : 'iterations') +
            stat(ms + ' ms', 'engine time');

          renderResult(result, displayPrefixes);
        } catch (e) {
          els.stats.innerHTML = '';
          var li = document.createElement('li');
          li.className = 'error';
          li.innerHTML = '<span class="d-tag">error</span><span class="d-loc"></span>' +
            '<span class="d-msg">' + esc((e && e.message) || String(e)) + '</span>';
          els.diag.appendChild(li);
          els.result.innerHTML = '<div class="pg-empty-out">The engine raised an error ' +
            'while running these inputs.</div>';
        } finally {
          root.classList.remove('is-running');
          els.run.disabled = false;
        }
      }

      els.run.addEventListener('click', run);
      root.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); run(); }
      });

      /* --- boot: restore shared state, then load the engine from a CDN --- */
      readHash();
      var url = 'https://esm.sh/' + pkg;
      import(/* @vite-ignore */ url).then(function (mod) {
        engine = mod;
        els.engine.setAttribute('data-state', 'ready');
      }).catch(function (err) {
        els.engine.setAttribute('data-state', 'error');
        els.run.disabled = true;
        els.fail.hidden = false;
        els.fail.innerHTML =
          'The SRL engine could not be loaded from the CDN, so the playground is ' +
          'inactive. The conformance results below are unaffected. ' +
          '<br><code>' + esc((err && err.message) || String(err)) + '</code>';
      });
    })();
    """

    def serialize(self, output_path: Path) -> None:
        passed = sum(1 for r in self.results if r.outcome == TestOutcome.PASSED)
        failed = sum(1 for r in self.results if r.outcome == TestOutcome.FAILED)
        total = len(self.results)
        other = total - passed - failed
        pct = (100.0 * passed / total) if total else 0.0
        pct_str = (f"{pct:.1f}".rstrip("0").rstrip(".")) if total else "0"
        gen = datetime.now(timezone.utc).date().isoformat()
        ver = _html.escape(self.project_version)

        fail_note = f' &middot; <span class="rate-note">{failed} failing</span>' if failed else ""
        rate_cls = " has-fail" if failed else ""

        segs = []
        if passed:
            segs.append(f'<div class="seg passed" style="flex:{passed} 1 0"></div>')
        if failed:
            segs.append(f'<div class="seg failed" style="flex:{failed} 1 0"></div>')
        if other:
            segs.append(f'<div class="seg other" style="flex:{other} 1 0"></div>')

        legend = [
            '<li><button class="leg" data-filter-set="passed">'
            f'<span class="sw passed"></span>Passed <b>{passed}</b></button></li>',
            '<li><button class="leg" data-filter-set="failed">'
            f'<span class="sw failed"></span>Failed <b>{failed}</b></button></li>',
        ]
        if other:
            legend.append(
                '<li><button class="leg" data-filter-set="other">'
                f'<span class="sw other"></span>Other <b>{other}</b></button></li>'
            )

        parts: List[str] = [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            '<meta name="color-scheme" content="light dark">',
            f"<title>{_html.escape(self.project_name)} conformance report</title>",
            f"<script>{self._THEME_BOOT}</script>",
            f'<style>{self._CSS}{self._PG_CSS}</style></head><body><div class="wrap">',
            '<header class="top"><div class="brand">',
            f"<h1>{_html.escape(self.project_name)} "
            '<span class="tag">SHACL 1.2 Rules</span></h1>',
            '<p class="sub">Shape Rule Language conformance report</p></div>',
            '<div class="top-right"><dl class="meta">'
            f"<div><dt>Version</dt><dd>{ver}</dd></div>"
            f"<div><dt>Generated</dt><dd>{gen}</dd></div></dl>"
            '<button id="theme" class="theme-btn" type="button" aria-label="Toggle theme">'
            f"{self._SUN}{self._MOON}</button></div></header>",
            # Hero: pass-rate + proportional bar + filterable legend.
            '<section class="hero"><div class="hero-rate">'
            f'<div class="rate{rate_cls}">{pct_str}%</div>'
            f'<div class="rate-sub">{passed} / {total} tests passed{fail_note}</div></div>'
            '<div class="hero-bar">'
            f'<div class="bar" role="img" aria-label="{passed} passed, {failed} failed, '
            f'{other} other of {total}">{"".join(segs)}</div>'
            f'<ul class="legend">{"".join(legend)}</ul></div></section>',
            # Interactive SRL playground (client-side engine via CDN ES module).
            self._playground_html(),
            # Sticky toolbar: search + outcome filters + expand/collapse.
            '<div class="toolbar"><div class="search">'
            f"{self._SEARCH_ICON}"
            '<label class="vh" for="q">Search tests</label>'
            '<input id="q" type="search" placeholder="Search tests…" autocomplete="off">'
            "</div>"
            '<div class="filters" role="group" aria-label="Filter by outcome">'
            f'<button class="chip" type="button" data-filter="all" aria-pressed="true">'
            f'All <span class="chip-n">{total}</span></button>'
            f'<button class="chip chip-pass" type="button" data-filter="passed" '
            f'aria-pressed="false">Passed <span class="chip-n">{passed}</span></button>'
            f'<button class="chip chip-fail" type="button" data-filter="failed" '
            f'aria-pressed="false">Failed <span class="chip-n">{failed}</span></button>'
            f'<button class="chip chip-other" type="button" data-filter="other" '
            f'aria-pressed="false">Other <span class="chip-n">{other}</span></button></div>'
            '<div class="bulk">'
            '<button class="txtbtn" type="button" data-bulk="expand">Expand all</button>'
            '<button class="txtbtn" type="button" data-bulk="collapse">Collapse all</button>'
            "</div></div>",
            "<main>",
        ]

        by_type: dict = {}
        for r in self.results:
            by_type.setdefault(r.test.test_type, []).append(r)

        for cat_name, types in CATEGORY_ORDER:
            cat_results = [r for tt in types for r in by_type.get(tt, [])]
            if not cat_results:
                continue
            is_ext = types == [TestType.TARGETING_EVAL]
            n = len(cat_results)
            p = sum(1 for r in cat_results if r.outcome == TestOutcome.PASSED)
            not_passed = n - p
            badge = (
                f'<span class="cat-badge bad">{not_passed} not passed</span>'
                if not_passed
                else '<span class="cat-badge ok">all passing</span>'
            )
            parts.append(f'<section class="cat{" ext" if is_ext else ""}">')
            parts.append(
                '<div class="cat-head">'
                f"<h2>{_html.escape(cat_name)}</h2>"
                f'<span class="cat-count">{p} / {n} passed</span>{badge}</div>'
            )
            if is_ext:
                parts.append(
                    '<p class="note">Opt-in extension &mdash; not part of the '
                    "W3C SHACL 1.2 specification.</p>"
                )
            parts.append('<div class="tbl">')
            for r in cat_results:
                parts.append(self._row_html(r))
            parts.append("</div></section>")

        parts.append('<p id="empty" class="empty" hidden>No tests match your search.</p>')
        parts.append("</main>")
        parts.append(
            '<footer class="foot">Generated by the shacl-rules W3C conformance runner '
            f"&middot; {gen}</footer>"
        )
        parts.append(f"<script>{self._JS}</script>")
        parts.append(f'<script type="module">{self._PG_JS}</script>')
        parts.append("</div></body></html>")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))


def find_manifest(test_suite_path: Path) -> Optional[Path]:
    """Find the main manifest file in the test suite."""
    # Try different possible locations
    possible_paths = [
        test_suite_path / "tests" / "rules" / "manifest-rules.ttl",
        test_suite_path / "manifest-rules.ttl",
        test_suite_path / "rules" / "manifest-rules.ttl",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def collect_tests(test_suite_path: Path, include_extensions: bool) -> List[TestEntry]:
    """Parse the official manifest and, optionally, the FOR-IN extension manifest."""
    manifest_path = find_manifest(test_suite_path)
    if not manifest_path:
        raise FileNotFoundError(f"Could not find manifest-rules.ttl in {test_suite_path}")
    tests = TestManifestParser(manifest_path).parse()

    if include_extensions:
        ext_manifest = test_suite_path / "tests" / "rules-extensions" / "manifest.ttl"
        if ext_manifest.exists():
            tests.extend(TestManifestParser(ext_manifest).parse())
        else:
            print(
                f"Warning: --include-extensions set but {ext_manifest} not found; "
                "running spec tests only",
                file=sys.stderr,
            )
    return tests


def main():
    parser = argparse.ArgumentParser(
        description="Run SHACL Rules tests and generate EARL implementation report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_shacl_rules_tests.py -o report.ttl
    python run_shacl_rules_tests.py -o report.ttl --test-type syntax
    python run_shacl_rules_tests.py -o report.ttl --test-suite-path ./shacl12-test-suite
        """,
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output path for the EARL report (Turtle format)",
    )

    parser.add_argument(
        "--test-suite-path",
        type=Path,
        default=Path("shacl12-test-suite"),
        help="Path to the SHACL 1.2 test suite directory",
    )

    parser.add_argument(
        "--include-extensions",
        action="store_true",
        help="Also run the opt-in FOR-IN targeting tests (rules-extensions/manifest.ttl)",
    )

    parser.add_argument(
        "--test-type",
        type=str,
        choices=["syntax", "wellformed", "stratification", "eval", "targeting", "all"],
        default="all",
        help="Filter tests by type (default: all)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--project-name",
        type=str,
        default="shacl-rules",
        help="Project name for the EARL report",
    )

    parser.add_argument(
        "--project-homepage",
        type=str,
        default="https://github.com/simonstey/py-srl",
        help="Project homepage URL for the EARL report",
    )

    parser.add_argument(
        "--developer-name",
        type=str,
        default="Simon Steyskal",
        help="Developer name for the EARL report",
    )

    args = parser.parse_args()

    # Parse manifest(s)
    print("Parsing test manifest...")
    try:
        tests = collect_tests(args.test_suite_path, args.include_extensions)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Please specify the correct path with --test-suite-path", file=sys.stderr)
        sys.exit(1)

    manifest_path = find_manifest(args.test_suite_path)  # for the runner base path

    if args.verbose:
        print(f"Using manifest: {manifest_path}")
        print(f"Found {len(tests)} tests")

    # Filter tests by type if specified
    if args.test_type != "all":
        type_filter_map = {
            "syntax": [TestType.POSITIVE_SYNTAX, TestType.NEGATIVE_SYNTAX],
            "wellformed": [TestType.POSITIVE_WELLFORMEDNESS, TestType.NEGATIVE_WELLFORMEDNESS],
            "stratification": [TestType.POSITIVE_STRATIFICATION, TestType.NEGATIVE_STRATIFICATION],
            "eval": [TestType.EVAL],
            "targeting": [TestType.TARGETING_EVAL],
        }
        allowed_types = type_filter_map.get(args.test_type, [])
        tests = [t for t in tests if t.test_type in allowed_types]

        if args.verbose:
            print(f"Filtered to {len(tests)} {args.test_type} tests")

    if not tests:
        print("No tests found matching the filter criteria", file=sys.stderr)
        sys.exit(1)

    # Create test runner
    test_runner = SHACLRulesTestRunner(manifest_path.parent)

    # Create EARL report generator
    report = EARLReportGenerator(
        project_name=args.project_name,
        project_homepage=args.project_homepage,
        developer_name=args.developer_name,
    )

    md_report = MarkdownReportGenerator(project_name=args.project_name)
    html_report = HtmlReportGenerator(project_name=args.project_name)
    all_results: List[TestResult] = []

    # Run tests
    print(f"Running {len(tests)} tests...")
    passed = 0
    failed = 0
    cant_tell = 0

    for i, test in enumerate(tests, 1):
        if args.verbose:
            print(f"  [{i}/{len(tests)}] {test.name}...", end=" ", flush=True)

        result = test_runner.run_test(test)
        report.add_result(result)
        all_results.append(result)

        if result.outcome == TestOutcome.PASSED:
            passed += 1
            if args.verbose:
                print("PASSED")
        elif result.outcome == TestOutcome.FAILED:
            failed += 1
            if args.verbose:
                print(f"FAILED: {result.message}")
        else:
            cant_tell += 1
            if args.verbose:
                print(f"CANT_TELL: {result.message}")

    # Write report
    report.serialize(args.output)
    print(f"\nEARL report written to: {args.output}")

    md_path = args.output.with_suffix(".md")
    html_path = args.output.with_suffix(".html")
    md_report.add_results(all_results, runner=test_runner)
    html_report.add_results(all_results, runner=test_runner)
    md_report.serialize(md_path)
    html_report.serialize(html_path)
    print(f"Markdown report written to: {md_path}")
    print(f"HTML report written to: {html_path}")

    # Print summary
    print("\nTest Results Summary:")
    print(f"  Passed:    {passed}")
    print(f"  Failed:    {failed}")
    print(f"  Untested:  {cant_tell}")
    print(f"  Total:     {len(tests)}")

    # Exit with error code if any tests failed
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
