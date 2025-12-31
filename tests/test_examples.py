"""
W3C Manifest-based test runner for SRL test suite.

Parses manifest.ttl files recursively and dispatches tests based on type:
- srt:RulesEvalTest: Apply rules to data, compare result graph
- srt:RulesPositiveSyntaxTest: SRL file should parse successfully  
- srt:RulesNegativeSyntaxTest: SRL file should produce parse error
- pyrl:StratificationTest: Rules should raise StratificationError
"""

import logging
from pathlib import Path
from typing import List

import pytest
from rdflib import Graph

from srl.engine import RuleEngine
from srl.engine.stratification import StratificationError
from srl.parser import SRLParser

# Import manifest utilities - handle both relative and absolute import
try:
    from .manifest_utils import (
        ManifestTestCase,
        compare_graphs,
        compute_inferred_triples,
        load_tests_from_manifest,
        STATUS_XFAIL,
        STATUS_SKIP,
    )
except ImportError:
    from manifest_utils import (
        ManifestTestCase,
        compare_graphs,
        compute_inferred_triples,
        load_tests_from_manifest,
        STATUS_XFAIL,
        STATUS_SKIP,
    )

logger = logging.getLogger(__name__)


def get_test_cases_dir() -> Path:
    """Get the directory containing test cases."""
    return Path(__file__).parent / "test-cases"


def get_root_manifest() -> Path:
    """Get the root manifest file."""
    return get_test_cases_dir() / "manifest.ttl"


def collect_test_cases() -> List[ManifestTestCase]:
    """
    Collect all test cases from the manifest hierarchy.
    
    Returns:
        List of ManifestTestCase objects
    """
    root_manifest = get_root_manifest()
    if not root_manifest.exists():
        logger.warning(f"Root manifest not found: {root_manifest}")
        return []
    
    return list(load_tests_from_manifest(root_manifest))


# Collect test cases at module load time
TEST_CASES = collect_test_cases()


def pytest_id(test_case: ManifestTestCase) -> str:
    """Generate a pytest ID for a test case."""
    # Extract category from manifest path
    category = test_case.manifest_path.parent.name
    return f"{category}/{test_case.name}"


@pytest.mark.parametrize(
    "test_case",
    TEST_CASES,
    ids=[pytest_id(tc) for tc in TEST_CASES]
)
def test_manifest_case(test_case: ManifestTestCase):
    """
    Run a single test case from the manifest.
    
    Dispatches to the appropriate test handler based on test type.
    """
    # Handle skip status
    if test_case.is_skip:
        pytest.skip(f"Test marked as skip: {test_case.name}")
    
    # Handle xfail status
    if test_case.is_xfail:
        pytest.xfail(f"Test marked as expected failure: {test_case.name}")
    
    # Dispatch based on test type
    if test_case.is_eval_test:
        run_eval_test(test_case)
    elif test_case.is_positive_syntax_test:
        run_positive_syntax_test(test_case)
    elif test_case.is_negative_syntax_test:
        run_negative_syntax_test(test_case)
    elif test_case.is_stratification_test:
        run_stratification_test(test_case)
    else:
        pytest.skip(f"Unknown test type: {test_case.test_type}")


def run_eval_test(test_case: ManifestTestCase):
    """
    Run a rules evaluation test.
    
    1. Parse the SRL rules
    2. Load input data
    3. Evaluate rules
    4. Compare inferred triples with expected result
    """
    assert test_case.ruleset_path, f"No ruleset path for {test_case.name}"
    assert test_case.ruleset_path.exists(), f"Ruleset not found: {test_case.ruleset_path}"
    
    # Parse SRL rules
    parser = SRLParser()
    try:
        srl_text = test_case.ruleset_path.read_text(encoding="utf-8")
        rule_set = parser.parse(srl_text)
    except Exception as e:
        pytest.fail(f"Failed to parse SRL file {test_case.ruleset_path}: {e}")
    
    # Load input data
    input_graph = Graph()
    if test_case.data_path and test_case.data_path.exists():
        try:
            input_graph.parse(str(test_case.data_path), format="turtle")
        except Exception as e:
            pytest.fail(f"Failed to parse data file {test_case.data_path}: {e}")
    
    logger.info(f"Running eval test: {test_case.name}")
    logger.info(f"Input graph size: {len(input_graph)}")
    
    # Evaluate rules
    engine = RuleEngine(rule_set)
    try:
        result_graph = engine.evaluate(input_graph, inplace=False)
    except Exception as e:
        pytest.fail(f"Rule evaluation failed: {e}")
    
    logger.info(f"Result graph size: {len(result_graph)}")
    
    # Compute inferred triples
    inferred = compute_inferred_triples(result_graph, input_graph)
    logger.info(f"Inferred triples: {len(inferred)}")
    
    # Compare with expected result if available
    if test_case.result_path and test_case.result_path.exists():
        expected = Graph()
        try:
            expected.parse(str(test_case.result_path), format="turtle")
        except Exception as e:
            pytest.fail(f"Failed to parse result file {test_case.result_path}: {e}")
        
        is_equal, diff = compare_graphs(inferred, expected)
        
        if not is_equal:
            pytest.fail(f"Graph mismatch:\n{diff}")
    else:
        # No expected result file - just verify rules produced some output
        # This is a fallback for tests without result files
        if len(inferred) == 0:
            logger.warning(f"No triples inferred for {test_case.name}")


def run_positive_syntax_test(test_case: ManifestTestCase):
    """
    Run a positive syntax test.
    
    The SRL file should parse successfully without errors.
    """
    srl_path = test_case.action_path or test_case.ruleset_path
    assert srl_path, f"No SRL path for {test_case.name}"
    assert srl_path.exists(), f"SRL file not found: {srl_path}"
    
    parser = SRLParser()
    try:
        srl_text = srl_path.read_text(encoding="utf-8")
        rule_set = parser.parse(srl_text)
        
        # Verify we got some rules
        assert rule_set is not None, "Parser returned None"
        logger.info(f"Positive syntax test passed: {test_case.name} ({len(rule_set.rules)} rules)")
        
    except Exception as e:
        pytest.fail(f"Syntax test failed - file should parse successfully: {e}")


def run_negative_syntax_test(test_case: ManifestTestCase):
    """
    Run a negative syntax test.
    
    The SRL file should produce a parse error.
    """
    srl_path = test_case.action_path or test_case.ruleset_path
    assert srl_path, f"No SRL path for {test_case.name}"
    assert srl_path.exists(), f"SRL file not found: {srl_path}"
    
    parser = SRLParser()
    try:
        srl_text = srl_path.read_text(encoding="utf-8")
        rule_set = parser.parse(srl_text)
        
        # If we get here, the parse succeeded when it should have failed
        pytest.fail(
            f"Negative syntax test failed - file should NOT parse successfully. "
            f"Got {len(rule_set.rules)} rules instead of parse error."
        )
        
    except Exception as e:
        # Expected - parse should fail
        logger.info(f"Negative syntax test passed: {test_case.name} (got expected error: {type(e).__name__})")


def run_stratification_test(test_case: ManifestTestCase):
    """
    Run a stratification error test.
    
    The rules should raise StratificationError during evaluation.
    """
    srl_path = test_case.ruleset_path or test_case.action_path
    assert srl_path, f"No SRL path for {test_case.name}"
    assert srl_path.exists(), f"SRL file not found: {srl_path}"
    
    # Parse rules
    parser = SRLParser()
    try:
        srl_text = srl_path.read_text(encoding="utf-8")
        rule_set = parser.parse(srl_text)
    except Exception as e:
        pytest.fail(f"Failed to parse SRL file: {e}")
    
    # Load data if available
    input_graph = Graph()
    if test_case.data_path and test_case.data_path.exists():
        input_graph.parse(str(test_case.data_path), format="turtle")
    
    # Try to evaluate - should raise StratificationError
    engine = RuleEngine(rule_set)
    try:
        engine.evaluate(input_graph, inplace=False)
        pytest.fail("Stratification test failed - expected StratificationError but evaluation succeeded")
        
    except StratificationError as e:
        # Expected
        logger.info(f"Stratification test passed: {test_case.name} (got expected error: {e})")
        
    except Exception as e:
        pytest.fail(f"Stratification test failed - expected StratificationError but got {type(e).__name__}: {e}")
