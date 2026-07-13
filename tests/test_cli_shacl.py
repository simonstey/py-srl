from click.testing import CliRunner
from srl.cli.main import cli


def test_srl_shacl_evaluates(tmp_path):
    (tmp_path / "r.srl").write_text(
        "PREFIX ex: <http://example.org/>\n"
        "RULE ex:r FOR ?this IN ex:AdultShape { ?this ex:status ex:adult } WHERE { ?this ex:age ?a }",
        encoding="utf-8")
    (tmp_path / "d.ttl").write_text(
        "@prefix ex: <http://example.org/> .\nex:Alice a ex:Person ; ex:age 30 .\n", encoding="utf-8")
    (tmp_path / "s.ttl").write_text(
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\n@prefix ex: <http://example.org/> .\n"
        "ex:AdultShape a sh:NodeShape ; sh:targetClass ex:Person ;\n"
        "  sh:property [ sh:path ex:age ; sh:minInclusive 18 ] .\n", encoding="utf-8")
    out = tmp_path / "out.ttl"
    res = CliRunner().invoke(cli, ["shacl", str(tmp_path/"r.srl"), str(tmp_path/"d.ttl"),
                                   "--shapes", str(tmp_path/"s.ttl"), "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert "status" in out.read_text(encoding="utf-8")
