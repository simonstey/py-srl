"""
AST Node definitions for SHACL 1.2 Rules (Shape Rule Language).

Based on the "Shape Rules Abstract Syntax" and grammar of the W3C SHACL 1.2
Rules specification (gh-pages, 2026-07-07 restructuring).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union


# ============================================================================
# RDF Terms and Basic Types
# ============================================================================


@dataclass(frozen=True)
class IRI:
    """An IRI (Internationalized Resource Identifier)."""

    value: str

    def __str__(self) -> str:
        return f"<{self.value}>"


@dataclass(frozen=True)
class Literal:
    """An RDF Literal with optional language tag or datatype."""

    value: str
    language: Optional[str] = None
    datatype: Optional[IRI] = None

    def __str__(self) -> str:
        if self.language:
            return f'"{self.value}"@{self.language}'
        elif self.datatype:
            return f'"{self.value}"^^{self.datatype}'
        return f'"{self.value}"'


@dataclass(frozen=True)
class BlankNode:
    """An RDF blank node."""

    label: str

    def __str__(self) -> str:
        return f"_:{self.label}"


@dataclass(frozen=True, eq=True)
class Variable:
    """
    A variable representing a possible RDF term in a triple pattern.

    From spec: "A variable represents a possible RDF term in a triple pattern.
    Variables are also used in expressions."
    """

    name: str

    def __str__(self) -> str:
        return f"?{self.name}"


@dataclass(frozen=True)
class TripleTerm:
    """
    An RDF 1.2 triple term ``<<( s p o )>>``.

    From the abstract syntax: an element of a triple template or triple pattern
    "might be a triple term". Triple terms may nest in the object position.
    Grammar productions [83]-[85] (TripleTerm / TripleTermSubject / Object) and
    [47]-[49] (the variable-free TripleTermData used inside DATA blocks).

    The second (predicate) element must be an IRI or a Variable.
    """

    subject: "RDFTerm"
    predicate: Union[IRI, Variable]
    object: "RDFTerm"

    def __str__(self) -> str:
        return f"<<( {self.subject} {self.predicate} {self.object} )>>"


# Union type for RDF terms (includes triple terms, per the abstract syntax).
RDFTerm = Union[IRI, Literal, BlankNode, Variable, TripleTerm]


# ============================================================================
# Property Paths (body patterns only)
# ============================================================================


@dataclass(frozen=True)
class InversePath:
    """Inverse property path (``^property``). Grammar [90]."""

    path: Union[IRI, "PropertyPath"]

    def __str__(self) -> str:
        return f"^{self.path}"


@dataclass(frozen=True)
class PathSequence:
    """Sequence property path (``path1/path2``). Grammar [89]."""

    elements: List[Union[IRI, "PropertyPath"]]

    def __str__(self) -> str:
        return "/".join(str(e) for e in self.elements)


PropertyPath = Union[IRI, InversePath, PathSequence]


# ============================================================================
# Expressions
# ============================================================================


class BinaryOperator(Enum):
    """Binary operators for expressions."""

    # Logical
    OR = "||"
    AND = "&&"
    # Relational
    EQ = "="
    NE = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="
    IN = "IN"
    NOT_IN = "NOT IN"
    # Arithmetic
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


class UnaryOperator(Enum):
    """Unary operators for expressions."""

    NOT = "!"
    PLUS = "+"
    MINUS = "-"


@dataclass(frozen=True)
class BinaryOp:
    """Binary operation expression. Grammar [107]-[113]."""

    operator: BinaryOperator
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class UnaryOp:
    """Unary operation expression. Grammar [114]."""

    operator: UnaryOperator
    operand: "Expression"


@dataclass(frozen=True)
class FunctionCall:
    """Function call expression. Grammar [20] FunctionCall / [116] iriOrFunction."""

    function: IRI
    arguments: List["Expression"]


@dataclass(frozen=True)
class BuiltInCall:
    """Built-in function call. Grammar [121] BuiltInCall."""

    function_name: str
    arguments: List["Expression"]


# Expression can be a term, variable, operation, or function call.
Expression = Union[
    RDFTerm,
    BinaryOp,
    UnaryOp,
    FunctionCall,
    BuiltInCall,
]


# ============================================================================
# Triple Patterns and Templates
# ============================================================================


@dataclass(frozen=True)
class TriplePattern:
    """
    A triple pattern is a 3-tuple where each element is a variable or an RDF
    term (which might be a triple term). The predicate (position 2) is an IRI,
    a Variable, or a property path (paths appear only in rule bodies).

    Appears in rule bodies. Grammar family [64]-[91].
    """

    subject: RDFTerm
    predicate: Union[IRI, Variable, PropertyPath]
    object: RDFTerm

    def __str__(self) -> str:
        return f"{self.subject} {self.predicate} {self.object} ."


@dataclass(frozen=True)
class TripleTemplate:
    """
    A triple template is a 3-tuple where each element is a variable or an RDF
    term (which might be a triple term). The predicate (position 2) is an IRI
    or a Variable. Templates have NO property paths.

    Appears in rule heads and (variable-free) in data blocks. Grammar [50]-[63].
    """

    subject: RDFTerm
    predicate: Union[IRI, Variable]
    object: RDFTerm

    def __str__(self) -> str:
        return f"{self.subject} {self.predicate} {self.object} ."


# ============================================================================
# Rule Body Elements
# ============================================================================


@dataclass(frozen=True)
class ConditionExpression:
    """
    A filter element: an expression used to restrict variable values.

    Grammar [18] Filter ::= 'FILTER' Constraint.
    """

    expression: Expression

    def __str__(self) -> str:
        return f"FILTER ({self.expression})"


@dataclass(frozen=True)
class NegationElement:
    """
    A negation element (``NOT { ... }``). Its *negation element body* is a
    sequence of triple pattern elements and filter elements (BodyBasic).

    Grammar [23] Negation ::= 'NOT' '{' BodyBasic '}'.
    """

    body_patterns: List[Union[TriplePattern, ConditionExpression]]

    def __str__(self) -> str:
        patterns_str = " ".join(str(p) for p in self.body_patterns)
        return f"NOT {{ {patterns_str} }}"


@dataclass(frozen=True)
class Assignment:
    """
    An assignment element: a pair of an *assignment variable* and an
    *assignment expression*.

    Grammar [26] Assignment ::= 'SET' '(' Var ':=' Expression ')'.
    """

    variable: Variable  # assignment variable
    expression: Expression  # assignment expression

    def __str__(self) -> str:
        return f"SET ({self.variable} := {self.expression})"


@dataclass(frozen=True)
class Annotation:
    """RDF-star annotation on a triple. Grammar AnnotationBlock ``{| ... |}``."""

    properties: List[tuple]

    def __str__(self) -> str:
        props = "; ".join(f"{p} {o}" for p, o in self.properties)
        return f"{{| {props} |}}"


# Union type for rule body elements (the four spec rule-element kinds).
RuleBodyElement = Union[
    TriplePattern,
    ConditionExpression,
    NegationElement,
    Assignment,
]


# ============================================================================
# Rules and Rule Sets
# ============================================================================


@dataclass(frozen=True)
class RuleHead:
    """A rule head is a sequence of triple templates."""

    templates: List[TripleTemplate]

    def __str__(self) -> str:
        return " ".join(str(t) for t in self.templates)


@dataclass(frozen=True)
class RuleBody:
    """A rule body is a sequence of rule body elements."""

    elements: List[RuleBodyElement]

    def __str__(self) -> str:
        return " ".join(str(e) for e in self.elements)


def _term_contains_blank_node(term: object) -> bool:
    """Recursively test whether an RDF term is/contains a blank node."""
    if isinstance(term, BlankNode):
        return True
    if isinstance(term, TripleTerm):
        return (
            _term_contains_blank_node(term.subject)
            or _term_contains_blank_node(term.predicate)
            or _term_contains_blank_node(term.object)
        )
    return False


@dataclass
class Rule:
    """
    A rule is a pair of a rule head and a rule body, optionally identified by
    a URI. Written either ``RULE iri? { head } WHERE { body }`` (Rule1) or
    ``IF { body } THEN { head }`` (Rule2).
    """

    head: RuleHead
    body: RuleBody
    iri: Optional[IRI] = None  # optional rule identifier (Rule1 only)

    # Stratification metadata (computed during analysis)
    layer: Optional[int] = None
    depends_on: List["Rule"] = field(default_factory=list)

    def has_assignment(self) -> bool:
        """True if the body contains an assignment element."""
        return any(isinstance(e, Assignment) for e in self.body.elements)

    def head_has_blank_node(self) -> bool:
        """True if any head triple template contains a blank node."""
        for t in self.head.templates:
            if (
                _term_contains_blank_node(t.subject)
                or _term_contains_blank_node(t.predicate)
                or _term_contains_blank_node(t.object)
            ):
                return True
        return False

    def is_run_once(self) -> bool:
        """
        A run-once rule uses an assignment element OR produces a blank node in
        the rule head; such rules are evaluated exactly once per stratum.
        """
        return self.has_assignment() or self.head_has_blank_node()

    def __str__(self) -> str:
        prefix = f"RULE {self.iri} " if self.iri else "RULE "
        return f"{prefix}{{ {self.head} }} WHERE {{ {self.body} }}"

    def __hash__(self) -> int:
        return id(self)


@dataclass(frozen=True)
class DataBlock:
    """
    A data block is a set of ground triples (no variables, no paths) added to
    the inference graph as additional facts.

    Grammar [14] Data ::= 'DATA' '{' DataTriplesBlock? '}'.
    """

    triples: List[TripleTemplate]

    def __str__(self) -> str:
        triples_str = " ".join(str(t) for t in self.triples)
        return f"DATA {{ {triples_str} }}"


# ============================================================================
# Declarations (TRANSITIVE, SYMMETRIC, INVERSE)  -- grammar [27]
# ============================================================================


@dataclass(frozen=True)
class TransitiveDeclaration:
    """``TRANSITIVE( iri )``."""

    predicate: IRI

    def __str__(self) -> str:
        return f"TRANSITIVE({self.predicate})"


@dataclass(frozen=True)
class SymmetricDeclaration:
    """``( iri ) SYMMETRIC`` (postfix form)."""

    predicate: IRI

    def __str__(self) -> str:
        return f"({self.predicate}) SYMMETRIC"


@dataclass(frozen=True)
class InverseDeclaration:
    """``INVERSE( iri, iri )``."""

    predicate1: IRI
    predicate2: IRI

    def __str__(self) -> str:
        return f"INVERSE({self.predicate1}, {self.predicate2})"


Declaration = Union[TransitiveDeclaration, SymmetricDeclaration, InverseDeclaration]


@dataclass
class Prologue:
    """
    Prologue declarations (BASE, PREFIX, VERSION, IMPORTS).

    Grammar [4]-[5]. May be interspersed between rules/data blocks.
    """

    base: Optional[IRI] = None
    prefixes: dict = field(default_factory=dict)
    version: Optional[str] = None
    imports: List[IRI] = field(default_factory=list)


@dataclass
class RuleSet:
    """
    A rule set is a collection of zero or more rules, zero or more data blocks,
    and zero or more rule imports. A *resolved rule set* is a rule set whose
    imports have been resolved away (``is_resolved`` is True).

    Grammar [1] RuleSet.
    """

    prologue: Prologue
    rules: List[Rule]
    data_blocks: List[DataBlock]
    declarations: List["Declaration"] = field(default_factory=list)

    # Stratification metadata (computed during analysis)
    layers: Optional[List[List[Rule]]] = None

    @property
    def imports(self) -> List[IRI]:
        """Rule imports (a first-class rule-set collection, stored on the prologue)."""
        return self.prologue.imports

    @property
    def is_resolved(self) -> bool:
        """A resolved rule set has no imports."""
        return not self.prologue.imports

    def __str__(self) -> str:
        parts = []
        if self.prologue.base:
            parts.append(f"BASE {self.prologue.base}")
        for prefix, iri in self.prologue.prefixes.items():
            parts.append(f"PREFIX {prefix}: {iri}")
        for data in self.data_blocks:
            parts.append(str(data))
        for rule in self.rules:
            parts.append(str(rule))
        return "\n".join(parts)


# ============================================================================
# Well-formedness Validation  (spec section #wellformed)
# ============================================================================


class WellFormednessError(Exception):
    """Raised when a rule or rule set violates well-formedness conditions."""

    pass


def _variables_in_term(term: object) -> set:
    """Collect variables occurring in an RDF term (including triple terms)."""
    if isinstance(term, Variable):
        return {term}
    if isinstance(term, TripleTerm):
        return (
            _variables_in_term(term.subject)
            | _variables_in_term(term.predicate)
            | _variables_in_term(term.object)
        )
    return set()


def _variables_in_pattern(pattern: Union[TriplePattern, TripleTemplate]) -> set:
    """Collect variables occurring in a triple pattern/template (all positions)."""
    result: set = set()
    result |= _variables_in_term(pattern.subject)
    if isinstance(pattern.predicate, Variable):
        result.add(pattern.predicate)
    result |= _variables_in_term(pattern.object)
    return result


def _extract_variables_from_expression(expr: Expression) -> set:
    """Extract all variables from an expression recursively."""
    if isinstance(expr, Variable):
        return {expr}
    if isinstance(expr, TripleTerm):
        return _variables_in_term(expr)
    if isinstance(expr, (IRI, Literal, BlankNode)):
        return set()
    if isinstance(expr, BinaryOp):
        return _extract_variables_from_expression(expr.left) | _extract_variables_from_expression(
            expr.right
        )
    if isinstance(expr, UnaryOp):
        return _extract_variables_from_expression(expr.operand)
    if isinstance(expr, (FunctionCall, BuiltInCall)):
        result: set = set()
        for arg in expr.arguments:
            result |= _extract_variables_from_expression(arg)
        return result
    return set()


def _check_well_formed_sequence(elements: List[RuleBodyElement], v0: set) -> set:
    """
    Verify a sequence of rule elements is a *well-formed sequence* given the
    initial variable set ``v0``, and return ``V_all`` (v0 plus every variable
    defined by the sequence).

    Implements the conditions from spec section #wellformed:
      * filter element:     every variable it mentions is in V_{i-1}
      * assignment element: expression variables are in V_{i-1}, and the
                            assignment variable is NOT in V_{i-1}
      * negation element:   its body is a well-formed sequence given V_{i-1}

    where V_{i-1} = v0 ∪ (variables defined by elements strictly before i).
    """
    v_prev = set(v0)  # V_{i-1}

    for element in elements:
        if isinstance(element, TriplePattern):
            # vars_i = variables occurring in the triple pattern element.
            v_prev = v_prev | _variables_in_pattern(element)

        elif isinstance(element, ConditionExpression):
            expr_vars = _extract_variables_from_expression(element.expression)
            undefined = expr_vars - v_prev
            if undefined:
                names = ", ".join(sorted(str(v) for v in undefined))
                raise WellFormednessError(
                    f"Filter references variable(s) not yet defined: {names}"
                )
            # A filter defines no variables (vars_i = empty).

        elif isinstance(element, Assignment):
            expr_vars = _extract_variables_from_expression(element.expression)
            undefined = expr_vars - v_prev
            if undefined:
                names = ", ".join(sorted(str(v) for v in undefined))
                raise WellFormednessError(
                    f"Assignment expression references variable(s) not yet defined: {names}"
                )
            if element.variable in v_prev:
                raise WellFormednessError(
                    f"Assignment variable {element.variable} is already defined "
                    f"earlier in the body (assignments must introduce a new variable)"
                )
            # vars_i = { assignment variable }.
            v_prev = v_prev | {element.variable}

        elif isinstance(element, NegationElement):
            # The negation element body must itself be well-formed given V_{i-1}.
            _check_well_formed_sequence(list(element.body_patterns), v_prev)
            # A negation element defines no variables in the outer scope.

    return v_prev


def validate_rule_well_formedness(rule: Rule) -> None:
    """
    Validate that a rule is a *well-formed rule* per spec section #wellformed:

      * the rule body is a well-formed sequence given V_0 = ∅, and
      * every variable in a head triple template is an element of V_all.

    Raises:
        WellFormednessError: if any condition is violated.
    """
    v_all = _check_well_formed_sequence(list(rule.body.elements), set())

    head_vars: set = set()
    for template in rule.head.templates:
        head_vars |= _variables_in_pattern(template)

    undefined_head = head_vars - v_all
    if undefined_head:
        names = ", ".join(sorted(str(v) for v in undefined_head))
        raise WellFormednessError(
            f"Head template variable(s) not defined in body: {names}"
        )


def validate_rule_set_well_formedness(rule_set: RuleSet) -> None:
    """A rule set is well-formed iff all of its rules are well-formed rules."""
    for rule in rule_set.rules:
        validate_rule_well_formedness(rule)
