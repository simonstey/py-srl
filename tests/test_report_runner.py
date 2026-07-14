import sys
from pathlib import Path

# The runner lives in tests/ and is imported by module name.
sys.path.insert(0, str(Path(__file__).parent))
import run_shacl_rules_tests as R

SUITE = Path(__file__).parent / "shacl12-test-suite"
EXT_MANIFEST = SUITE / "tests" / "rules-extensions" / "manifest.ttl"


def test_targeting_type_exists():
    assert R.TestType.TARGETING_EVAL.value == "RulesTargetingEvalTest"


def test_manifest_parses_targeting_entries():
    tests = R.TestManifestParser(EXT_MANIFEST).parse()
    targeting = [t for t in tests if t.test_type == R.TestType.TARGETING_EVAL]
    assert len(targeting) == 3
    adult = next(t for t in targeting if t.name == "targeting-adult-01")
    assert adult.action_ruleset is not None
    assert adult.action_data is not None
    assert adult.action_shapes is not None
    assert adult.result is not None


def test_targeting_eval_tests_pass():
    runner = R.SHACLRulesTestRunner(EXT_MANIFEST.parent)
    tests = R.TestManifestParser(EXT_MANIFEST).parse()
    for t in tests:
        if t.test_type == R.TestType.TARGETING_EVAL:
            result = runner.run_test(t)
            assert result.outcome == R.TestOutcome.PASSED, f"{t.name}: {result.message}"
