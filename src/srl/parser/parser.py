"""
Main parser class for SHACL 1.2 Rules (Shape Rule Language).
"""

from pathlib import Path

from lark import Lark, UnexpectedInput, UnexpectedToken, UnexpectedCharacters

from .transformer import SRLTransformer
from ..ast import RuleSet


class ParseError(Exception):
    """Raised when parsing fails."""
    pass


class ExtensionError(Exception):
    """Raised when an opt-in extension feature is used without enabling it."""
    pass


def _build_extended_grammar(base_grammar: str, ext_grammar: str) -> str:
    """Combine the base grammar with the opt-in extension productions.

    The extension file redefines ``rule1``/``rule2`` (to accept an optional
    ``FOR Var IN iri`` focus clause) and adds a ``for_clause`` production. Lark
    forbids duplicate rule definitions, so the base ``rule1:``/``rule2:`` lines
    are replaced in place with the extension versions and ``for_clause`` is
    appended. The base grammar file itself is never modified.
    """
    ext_productions: dict[str, str] = {}
    extra_lines: list[str] = []
    for line in ext_grammar.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        name = stripped.split(":", 1)[0].strip()
        if name in ("rule1", "rule2"):
            ext_productions[name] = stripped
        else:
            extra_lines.append(stripped)

    out_lines = []
    for line in base_grammar.splitlines():
        name = line.split(":", 1)[0].strip()
        if name in ext_productions:
            out_lines.append(ext_productions.pop(name))
        else:
            out_lines.append(line)

    # Any ext production that had no base counterpart is appended as well.
    out_lines.extend(ext_productions.values())
    out_lines.extend(extra_lines)
    return "\n".join(out_lines)


class SRLParser:
    """
    Parser for the Shape Rule Language (SRL).

    Uses Lark parser with EBNF grammar from Section 6 of the specification.

    When ``extensions=True`` the parser additionally accepts the opt-in
    rule-to-shape targeting clause ``RULE iri? FOR Var IN iri { ... } WHERE
    { ... }`` (and the ``IF ... THEN`` analogue), building ``TargetedRule``
    nodes. This is NOT part of the SRL spec; the default (flag-off) grammar
    stays byte-for-byte spec-conformant.
    """

    def __init__(self, extensions: bool = False):
        """Initialize the parser with the SRL grammar.

        Args:
            extensions: Enable the opt-in ``FOR ?v IN <shape>`` targeting clause.
        """
        self.extensions = extensions
        base_dir = Path(__file__).parent
        grammar_path = base_dir / "grammar.lark"

        try:
            with open(grammar_path, 'r', encoding='utf-8') as f:
                grammar = f.read()
        except FileNotFoundError:
            raise ParseError(f"Grammar file not found: {grammar_path}")

        if extensions:
            ext_path = base_dir / "grammar-ext.lark"
            try:
                with open(ext_path, 'r', encoding='utf-8') as f:
                    ext_grammar = f.read()
            except FileNotFoundError:
                raise ParseError(f"Extension grammar file not found: {ext_path}")
            grammar = _build_extended_grammar(grammar, ext_grammar)

        try:
            self.parser = Lark(
                grammar,
                start='rule_set',
                parser='lalr',  # LALR(1) parser for efficiency
                transformer=SRLTransformer(extensions=extensions),
            )
        except Exception as e:
            raise ParseError(f"Failed to initialize parser: {e}")
    
    def parse(self, text: str) -> RuleSet:
        """
        Parse SRL text into an AST RuleSet.
        
        Args:
            text: SRL source code
            
        Returns:
            RuleSet AST node
            
        Raises:
            ParseError: If parsing fails
        """
        try:
            return self.parser.parse(text)
        except UnexpectedToken as e:
            raise ParseError(
                f"Unexpected token '{e.token}' at line {e.line}, column {e.column}"
            ) from e
        except UnexpectedCharacters as e:
            raise ParseError(
                f"Unexpected character at line {e.line}, column {e.column}"
            ) from e
        except UnexpectedInput as e:
            line = e.line
            column = e.column
            expected = ', '.join(e.expected) if hasattr(e, 'expected') else 'unknown'
            raise ParseError(
                f"Unexpected input at line {line}, column {column}. "
                f"Expected: {expected}"
            ) from e
        except Exception as e:
            raise ParseError(f"Parse error: {e}") from e
    
    def parse_file(self, filepath: str) -> RuleSet:
        """
        Parse an SRL file into an AST RuleSet.
        
        Args:
            filepath: Path to SRL file
            
        Returns:
            RuleSet AST node
            
        Raises:
            ParseError: If parsing fails
            FileNotFoundError: If file doesn't exist
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {filepath}")
        except Exception as e:
            raise ParseError(f"Failed to read file: {e}")
        
        return self.parse(text)
