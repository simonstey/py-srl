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

    def _compare_inferred(
        self, test: TestEntry, inferred_graph: Graph, expected_graph: Graph
    ) -> TestResult:
        """Compare inferred triples to the expected graph by RDF isomorphism."""
        if isomorphic(inferred_graph, expected_graph):
            return TestResult(test=test, outcome=TestOutcome.PASSED)
        expected_count = len(expected_graph)
        actual_count = len(inferred_graph)
        msg = f"Graph mismatch: expected {expected_count} inferred triples, got {actual_count}"
        missing = [t for t in expected_graph if t not in inferred_graph]
        extra = [t for t in inferred_graph if t not in expected_graph]
        if missing:
            msg += f"; missing: {len(missing)}"
        if extra:
            msg += f"; extra: {len(extra)}"
        return TestResult(test=test, outcome=TestOutcome.FAILED, message=msg)

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


class HtmlReportGenerator:
    """Renders a self-contained (inline-CSS) HTML conformance report."""

    _CSS = """
    body { font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }
    h1 { font-size: 1.5rem; } h2 { margin-top: 2rem; border-bottom: 1px solid #ddd; }
    .cards { display: flex; gap: 1rem; margin: 1rem 0; }
    .card { padding: 1rem 1.5rem; border-radius: 8px; background: #f4f4f5; }
    .card .n { font-size: 1.8rem; font-weight: 700; }
    table { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
    th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; }
    code { font-family: ui-monospace, monospace; }
    .pill { padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
    .passed { background: #dcfce7; color: #166534; }
    .failed { background: #fee2e2; color: #991b1b; }
    .other  { background: #fef9c3; color: #854d0e; }
    details { margin: 0.3rem 0; } pre { background: #f8f8f8; padding: 0.6rem; overflow-x: auto; }
    .ext { color: #7c3aed; }
    """

    def __init__(self, project_name: str = "shacl-rules", project_version: str = None):
        self.project_name = project_name
        self.project_version = project_version or SRL_VERSION
        self.results: List[TestResult] = []
        self.runner: Optional["SHACLRulesTestRunner"] = None

    def add_results(self, results: List[TestResult], runner: "SHACLRulesTestRunner" = None):
        self.results = results
        self.runner = runner

    def _pill(self, outcome: TestOutcome) -> str:
        cls = {TestOutcome.PASSED: "passed", TestOutcome.FAILED: "failed"}.get(outcome, "other")
        return f'<span class="pill {cls}">{OUTCOME_BADGE.get(outcome, "?")} {outcome.value}</span>'

    def serialize(self, output_path: Path):
        passed = sum(1 for r in self.results if r.outcome == TestOutcome.PASSED)
        failed = sum(1 for r in self.results if r.outcome == TestOutcome.FAILED)
        other = len(self.results) - passed - failed
        parts = [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            f"<title>{self.project_name} conformance report</title>",
            f"<style>{self._CSS}</style></head><body>",
            f"<h1>{self.project_name} — SHACL 1.2 Rules conformance report</h1>",
            f"<p><b>Version:</b> {_html.escape(self.project_version)} &nbsp; "
            f"<b>Generated:</b> {datetime.now(timezone.utc).date().isoformat()}</p>",
            '<div class="cards">',
            f'<div class="card"><div class="n">{passed}</div>✅ Passed</div>',
            f'<div class="card"><div class="n">{failed}</div>❌ Failed</div>',
            f'<div class="card"><div class="n">{other}</div>⚠️ Other</div>',
            f'<div class="card"><div class="n">{len(self.results)}</div>Total</div>',
            "</div>",
        ]
        by_type = {}
        for r in self.results:
            by_type.setdefault(r.test.test_type, []).append(r)
        for cat_name, types in CATEGORY_ORDER:
            cat_results = [r for tt in types for r in by_type.get(tt, [])]
            if not cat_results:
                continue
            cls = ' class="ext"' if types == [TestType.TARGETING_EVAL] else ""
            parts.append(f"<h2{cls}>{_html.escape(cat_name)}</h2>")
            parts.append("<table><tr><th>Test</th><th>Outcome</th><th>Message</th></tr>")
            for r in cat_results:
                parts.append(
                    f"<tr><td><code>{_html.escape(r.test.name)}</code></td>"
                    f"<td>{self._pill(r.outcome)}</td>"
                    f"<td>{_html.escape(r.message or '')}</td></tr>"
                )
            parts.append("</table>")
            if self.runner is not None:
                for r in cat_results:
                    snippets = collect_source_snippets(self.runner, r.test)
                    if not snippets:
                        continue
                    parts.append(
                        f"<details><summary><code>{_html.escape(r.test.name)}</code> "
                        "source</summary>"
                    )
                    for label, text in snippets:
                        parts.append(f"<b>{label}:</b><pre>{_html.escape(text.rstrip())}</pre>")
                    parts.append("</details>")
        parts.append("</body></html>")
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
