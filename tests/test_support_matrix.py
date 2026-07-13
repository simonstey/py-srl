# tests/test_support_matrix.py
from pathlib import Path
from srl.shapes import model


def test_support_matrix_lists_all_supported():
    doc = Path("docs/shacl-core-support-matrix.md").read_text(encoding="utf-8")
    supported = model._TARGET_PREDS | model._NODE_CONSTRAINTS | model._PROP_CONSTRAINTS
    missing = [name for name in supported if f"sh:{name}" not in doc]
    assert not missing, f"support matrix missing: {missing}"
