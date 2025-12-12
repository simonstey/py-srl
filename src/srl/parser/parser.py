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


class SRLParser:
    """
    Parser for the Shape Rule Language (SRL).
    
    Uses Lark parser with EBNF grammar from Section 6 of the specification.
    """
    
    def __init__(self):
        """Initialize the parser with the SRL grammar."""
        grammar_path = Path(__file__).parent / "grammar.lark"
        
        try:
            with open(grammar_path, 'r', encoding='utf-8') as f:
                grammar = f.read()
        except FileNotFoundError:
            raise ParseError(f"Grammar file not found: {grammar_path}")
        
        try:
            self.parser = Lark(
                grammar,
                start='rule_set',
                parser='lalr',  # LALR(1) parser for efficiency
                transformer=SRLTransformer(),
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
        except UnexpectedInput as e:
            line = e.line
            column = e.column
            expected = ', '.join(e.expected) if hasattr(e, 'expected') else 'unknown'
            raise ParseError(
                f"Unexpected input at line {line}, column {column}. "
                f"Expected: {expected}"
            ) from e
        except UnexpectedToken as e:
            raise ParseError(
                f"Unexpected token '{e.token}' at line {e.line}, column {e.column}"
            ) from e
        except UnexpectedCharacters as e:
            raise ParseError(
                f"Unexpected character at line {e.line}, column {e.column}"
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
