"""
AST Node definitions for SHACL 1.2 Rules (Shape Rule Language).

Based on Section 3: Shape Rules Abstract Syntax from the W3C specification.
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

    Variables are used in triple patterns (body) and expressions.
    From spec: "A variable represents a possible RDF term in a triple pattern.
    Variables are also used in expressions."
    """

    name: str

    def __str__(self) -> str:
        return f"?{self.name}"


# Union type for RDF terms
RDFTerm = Union[IRI, Literal, BlankNode, Variable]


# ============================================================================
# Property Paths
# ============================================================================


@dataclass(frozen=True)
class InversePath:
    """Inverse property path (^property).

    From production [49]: PathEltOrInverse ::= PathElt | '^' PathElt
    """

    path: Union[IRI, "PropertyPath"]

    def __str__(self) -> str:
        return f"^{self.path}"


@dataclass(frozen=True)
class PathSequence:
    """Sequence property path (path1/path2).

    From production [48]: PathSequence ::= PathEltOrInverse ( '/' PathEltOrInverse )*
    """

    elements: List[Union[IRI, "PropertyPath"]]

    def __str__(self) -> str:
        return "/".join(str(e) for e in self.elements)


@dataclass(frozen=True)
class PathAlternative:
    """Alternative property path (path1|path2).

    From production [47]: Path ::= PathSequence ( '|' PathSequence )*
    Note: The current grammar only has single PathSequence, but spec allows alternatives.
    """

    alternatives: List[Union[IRI, "PropertyPath"]]

    def __str__(self) -> str:
        return "|".join(str(a) for a in self.alternatives)


# Union type for property paths
PropertyPath = Union[IRI, InversePath, PathSequence, PathAlternative]


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
    """
    Binary operation expression.

    Part of the expression hierarchy from productions [76]-[83].
    """

    operator: BinaryOperator
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class UnaryOp:
    """
    Unary operation expression.

    From production [84]: UnaryExpression
    """

    operator: UnaryOperator
    operand: "Expression"


@dataclass(frozen=True)
class FunctionCall:
    """
    Function call expression.

    From production [31]: FunctionCall ::= iri ArgList
    """

    function: IRI
    arguments: List["Expression"]


@dataclass(frozen=True)
class BuiltInCall:
    """
    Built-in SPARQL function call.

    From production [90]: BuiltInCall (STR, LANG, DATATYPE, BOUND, etc.)
    """

    function_name: str
    arguments: List["Expression"]


# Expression can be a term, variable, operation, or function call
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
    A triple pattern is a 3-tuple where each element is either a variable or an RDF term.

    From spec: "A triple pattern is 3-tuple where each element is either a variable,
    or an RDF term (which might be a triple term). The second element of the tuple
    must be an IRI. Triple patterns appear in the body of a rule."

    Position 1: subject
    Position 2: predicate (must be IRI or Variable)
    Position 3: object
    """

    subject: RDFTerm
    predicate: Union[IRI, Variable]
    object: RDFTerm

    def __str__(self) -> str:
        return f"{self.subject} {self.predicate} {self.object} ."


@dataclass(frozen=True)
class TripleTemplate:
    """
    A triple template is a 3-tuple where each element is either a variable or an RDF term.

    From spec: "A triple template is 3-tuple where each element is either a variable
    or an RDF term (which might be a triple term). The second element of the tuple
    must be an IRI or a variable. Triple templates appear in the head of a rule."

    Position 1: subject
    Position 2: predicate (must be IRI or Variable)
    Position 3: object
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
    A condition expression (FILTER) that evaluates to true or false.

    From spec: "A condition expression is a function, or functional form,
    that evaluates to true or false. Condition expressions appear in the body of a rule."

    From production [29]: Filter ::= 'FILTER' Constraint
    """

    expression: Expression

    def __str__(self) -> str:
        return f"FILTER ({self.expression})"


@dataclass(frozen=True)
class NegationElement:
    """
    A negation element (NOT { ... }).

    From spec: "A negation element is ..@@.. . Negation elements appear in the body of a rule."

    From production [19]: Negation ::= 'NOT' '{' BodyBasic '}'
    """

    body_patterns: List[Union[TriplePattern, ConditionExpression]]

    def __str__(self) -> str:
        patterns_str = " ".join(str(p) for p in self.body_patterns)
        return f"NOT {{ {patterns_str} }}"


@dataclass(frozen=True)
class Assignment:
    """
    An assignment (BIND expression).

    From spec: "An assignment is a pair of a variable, called the assignment variable,
    and an expression, called the assignment expression. Assignments appear in the body of a rule."

    From production [26]: Assignment ::= 'BIND' '(' Expression 'AS' Var ')'
    """

    variable: Variable  # assignment variable
    expression: Expression  # assignment expression

    def __str__(self) -> str:
        return f"BIND ({self.expression} AS {self.variable})"


@dataclass(frozen=True)
class AggregationElement:
    """
    An aggregation element.

    From spec: "An aggregation element is ..@@.. . Aggregation elements appear in the body of a rule."

    Note: Specification is incomplete for aggregation. Placeholder for future implementation.
    """

    pass


@dataclass(frozen=True)
class Annotation:
    """RDF-star annotation on a triple.

    From productions [60]-[61]:
    Annotation ::= ( Reifier | AnnotationBlock )*
    AnnotationBlock ::= '{|' PropertyListNotEmpty '|}'
    """

    properties: List[tuple[Union[IRI, Variable], RDFTerm]]

    def __str__(self) -> str:
        props = "; ".join(f"{p} {o}" for p, o in self.properties)
        return f"{{| {props} |}}"


# Union type for rule body elements
RuleBodyElement = Union[
    TriplePattern,
    ConditionExpression,
    NegationElement,
    Assignment,
    AggregationElement,
]


# ============================================================================
# Rules and Rule Sets
# ============================================================================


@dataclass(frozen=True)
class RuleHead:
    """
    A rule head is a sequence of triple templates.

    From spec: "A rule head is a sequence where each element of the sequence is a triple template."
    """

    templates: List[TripleTemplate]

    def __str__(self) -> str:
        return " ".join(str(t) for t in self.templates)


@dataclass(frozen=True)
class RuleBody:
    """
    A rule body is a sequence of rule body elements.

    From spec: "A rule body is a sequence of rule body elements."
    """

    elements: List[RuleBodyElement]

    def __str__(self) -> str:
        return " ".join(str(e) for e in self.elements)


@dataclass
class Rule:
    """
    A rule is a pair of a rule head and a rule body.

    From spec: "A rule is a pair of a rule head (often just 'head') and
    a rule body (often just 'body')."

    The rule can be written in three forms:
    - RULE head WHERE body
    - IF body THEN head
    - head :- body
    """

    head: RuleHead
    body: RuleBody

    # Stratification metadata (computed during analysis)
    layer: Optional[int] = None
    depends_on: List["Rule"] = field(default_factory=list)

    def __str__(self) -> str:
        return f"RULE {{ {self.head} }} WHERE {{ {self.body} }}"

    def __hash__(self) -> int:
        return id(self)


@dataclass(frozen=True)
class DataBlock:
    """
    A data block is a set of triples.

    From spec: "A data block is a set of triples. These form extra facts
    that are included in the inference process."

    From production [13]: Data ::= 'DATA' TriplesTemplateBlock
    """

    triples: List[TripleTemplate]

    def __str__(self) -> str:
        triples_str = " ".join(str(t) for t in self.triples)
        return f"DATA {{ {triples_str} }}"


# ============================================================================
# Declarations (TRANSITIVE, SYMMETRIC, INVERSE)
# ============================================================================


@dataclass(frozen=True)
class TransitiveDeclaration:
    """Declaration that a predicate is transitive.

    From production [12]: 'TRANSITIVE' '(' iri ')'
    """

    predicate: IRI

    def __str__(self) -> str:
        return f"TRANSITIVE({self.predicate})"


@dataclass(frozen=True)
class SymmetricDeclaration:
    """Declaration that a predicate is symmetric.

    From production [12]: 'SYMMETRIC' '(' iri ')'
    """

    predicate: IRI

    def __str__(self) -> str:
        return f"SYMMETRIC({self.predicate})"


@dataclass(frozen=True)
class InverseDeclaration:
    """Declaration that two predicates are inverses of each other.

    From production [12]: 'INVERSE' '(' iri ',' iri ')'
    """

    predicate1: IRI
    predicate2: IRI

    def __str__(self) -> str:
        return f"INVERSE({self.predicate1}, {self.predicate2})"


# Union type for declarations
Declaration = Union[TransitiveDeclaration, SymmetricDeclaration, InverseDeclaration]


@dataclass
class Prologue:
    """
    Prologue declarations (BASE, PREFIX, VERSION, IMPORTS).

    From production [2]: Prologue ::= ( BaseDecl | PrefixDecl | VersionDecl | ImportsDecl )*
    """

    base: Optional[IRI] = None
    prefixes: dict[str, IRI] = field(default_factory=dict)
    version: Optional[str] = None
    imports: List[IRI] = field(default_factory=list)


@dataclass
class RuleSet:
    """
    A rule set is a collection of zero or more rules and zero or more data blocks.

    From spec: "A rule set is a collection of zero or more rules and
    a collection of zero or more data blocks."

    From production [1]: RuleSet ::= ( Prologue ( Rule | Data ) )*
    """

    prologue: Prologue
    rules: List[Rule]
    data_blocks: List[DataBlock]
    declarations: List["Declaration"] = field(default_factory=list)

    # Stratification metadata (computed during analysis)
    layers: Optional[List[List[Rule]]] = None

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
# Well-formedness Validation
# ============================================================================


class WellFormednessError(Exception):
    """Raised when a rule or rule set violates well-formedness conditions."""

    pass


def validate_rule_well_formedness(rule: Rule) -> None:
    """
    Validate that a rule meets all well-formedness conditions from Section 3.2.

    Conditions:
    1. Every variable in head templates appears in body patterns or assignments
    2. Every variable in expressions appears earlier in the body
    3. Each assignment variable is used only once
    4. Assignment variables don't appear in triple patterns after assignment
    5. Variables in assignment expressions appear before the assignment

    Raises:
        WellFormednessError: If any condition is violated
    """
    # Collect all variables from head
    head_vars = set()
    for template in rule.head.templates:
        if isinstance(template.subject, Variable):
            head_vars.add(template.subject)
        if isinstance(template.predicate, Variable):
            head_vars.add(template.predicate)
        if isinstance(template.object, Variable):
            head_vars.add(template.object)

    # Track variables defined in body (from triple patterns and assignments)
    defined_vars = set()
    assignment_vars = set()

    # Process body elements in order
    for i, element in enumerate(rule.body.elements):
        if isinstance(element, TriplePattern):
            # Variables in triple pattern become defined
            if isinstance(element.subject, Variable):
                defined_vars.add(element.subject)
            if isinstance(element.predicate, Variable):
                defined_vars.add(element.predicate)
            if isinstance(element.object, Variable):
                defined_vars.add(element.object)

            # Check condition 4: assignment variable shouldn't appear here after assignment
            for var in [element.subject, element.predicate, element.object]:
                if isinstance(var, Variable) and var in assignment_vars:
                    raise WellFormednessError(f"Assignment variable {var} appears in triple pattern at position {i}")

        elif isinstance(element, Assignment):
            # Check condition 3: assignment variable used only once
            if element.variable in assignment_vars:
                raise WellFormednessError(f"Assignment variable {element.variable} is assigned multiple times")

            # Check condition 5: variables in assignment expression must be defined
            expr_vars = _extract_variables_from_expression(element.expression)
            undefined = expr_vars - defined_vars - assignment_vars
            if undefined:
                raise WellFormednessError(f"Variables {undefined} in assignment expression are not yet defined")

            # Mark assignment variable as defined
            assignment_vars.add(element.variable)
            defined_vars.add(element.variable)

        elif isinstance(element, ConditionExpression):
            # Check condition 2: variables in filter must be defined
            expr_vars = _extract_variables_from_expression(element.expression)
            undefined = expr_vars - defined_vars
            if undefined:
                raise WellFormednessError(
                    f"Variables {undefined} in filter expression are not yet defined at position {i}"
                )

    # Check condition 1: all head variables must be defined in body
    undefined_head = head_vars - defined_vars
    if undefined_head:
        raise WellFormednessError(f"Variables {undefined_head} in rule head are not defined in body")


def _extract_variables_from_expression(expr: Expression) -> set[Variable]:
    """Extract all variables from an expression recursively."""
    if isinstance(expr, Variable):
        return {expr}
    elif isinstance(expr, (IRI, Literal, BlankNode)):
        return set()
    elif isinstance(expr, BinaryOp):
        return _extract_variables_from_expression(expr.left) | _extract_variables_from_expression(expr.right)
    elif isinstance(expr, UnaryOp):
        return _extract_variables_from_expression(expr.operand)
    elif isinstance(expr, (FunctionCall, BuiltInCall)):
        result = set()
        for arg in expr.arguments:
            result |= _extract_variables_from_expression(arg)
        return result
    return set()
