"""
Import resolution for SHACL 1.2 Rules (spec section #process-imports).

Produces a *resolved rule set* from a rule set by recursively reading every
rule set named in its imports and merging their rules and data blocks, tracking
visited URLs to avoid cycles.
"""

from pathlib import Path
from typing import Callable, List, Optional, Set
from urllib.parse import urlparse
from urllib.request import url2pathname, urlopen

from ..ast.nodes import IRI, Prologue, RuleSet


def _default_loader(url: str) -> str:
    """Read the SRL text for an import URL (file path, file:// or http(s)://)."""
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        with urlopen(url) as resp:  # noqa: S310 - intentional network fetch
            return resp.read().decode("utf-8")
    if parsed.scheme == "file":
        # url2pathname handles platform-specific mapping, incl. Windows drive
        # letters (file:///C:/... -> C:\...).
        return Path(url2pathname(parsed.path)).read_text(encoding="utf-8")
    # Bare path.
    return Path(url).read_text(encoding="utf-8")


def resolve_imports(
    rule_set: RuleSet,
    *,
    base_location: Optional[str] = None,
    loader: Optional[Callable[[str], str]] = None,
) -> RuleSet:
    """
    Resolve the imports of ``rule_set`` into a single combined rule set.

    Args:
        rule_set: the rule set whose imports to resolve.
        base_location: the location of ``rule_set`` (added to the visited set so
            a rule set does not re-import itself).
        loader: callable mapping an import URL to SRL text. Defaults to reading
            local files / http(s) URLs. Injectable for tests and offline use.

    Returns:
        A resolved rule set (``is_resolved`` is True) combining this rule set and
        all transitively imported rule sets. The merged prologue keeps this rule
        set's base/prefixes/version but drops imports.
    """
    from ..parser import SRLParser  # local import to avoid a cycle

    load = loader or _default_loader
    parser = SRLParser()

    combined_rules = list(rule_set.rules)
    combined_data = list(rule_set.data_blocks)
    combined_decls = list(rule_set.declarations)

    visited: Set[str] = set()
    if base_location:
        visited.add(base_location)

    def _recurse(imports: List[IRI]) -> None:
        for imp in imports:
            url = imp.value if isinstance(imp, IRI) else str(imp)
            if url in visited:
                continue
            visited.add(url)
            text = load(url)
            imported = parser.parse(text)
            combined_rules.extend(imported.rules)
            combined_data.extend(imported.data_blocks)
            combined_decls.extend(imported.declarations)
            _recurse(imported.prologue.imports)

    _recurse(rule_set.prologue.imports)

    merged_prologue = Prologue(
        base=rule_set.prologue.base,
        prefixes=dict(rule_set.prologue.prefixes),
        version=rule_set.prologue.version,
        imports=[],  # resolved away
    )
    return RuleSet(
        prologue=merged_prologue,
        rules=combined_rules,
        data_blocks=combined_data,
        declarations=combined_decls,
    )
