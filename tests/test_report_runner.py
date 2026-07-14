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


def test_collect_tests_includes_extensions_only_when_asked():
    suite = SUITE
    spec_only = R.collect_tests(suite, include_extensions=False)
    with_ext = R.collect_tests(suite, include_extensions=True)
    spec_names = {t.name for t in spec_only}
    ext_names = {t.name for t in with_ext}
    assert "targeting-adult-01" not in spec_names
    assert "targeting-adult-01" in ext_names
    assert len(with_ext) == len(spec_only) + 3


def test_markdown_report_contains_summary_and_categories(tmp_path):
    runner = R.SHACLRulesTestRunner(EXT_MANIFEST.parent)
    tests = R.TestManifestParser(EXT_MANIFEST).parse()
    results = [runner.run_test(t) for t in tests]
    gen = R.MarkdownReportGenerator()
    gen.add_results(results, runner=runner)
    out = tmp_path / "report.md"
    gen.serialize(out)
    text = out.read_text(encoding="utf-8")
    assert "# " in text  # has a title
    assert "Targeting extension" in text  # extension section rendered
    assert "targeting-adult-01" in text  # test name in a row
    assert "<details>" in text  # collapsible source
    assert "✅" in text or "❌" in text  # outcome badge


def test_html_report_is_self_contained(tmp_path):
    runner = R.SHACLRulesTestRunner(EXT_MANIFEST.parent)
    tests = R.TestManifestParser(EXT_MANIFEST).parse()
    results = [runner.run_test(t) for t in tests]
    gen = R.HtmlReportGenerator()
    gen.add_results(results, runner=runner)
    out = tmp_path / "report.html"
    gen.serialize(out)
    html = out.read_text(encoding="utf-8")
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "<style>" in html  # inline CSS, self-contained
    assert "targeting-adult-01" in html
    assert "<details>" in html
    assert "http" not in html.split("<style>")[1].split("</style>")[0]  # no external CSS URL
