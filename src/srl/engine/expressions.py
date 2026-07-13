"""
Expression evaluation for SHACL 1.2 Rules.

Implements Section 5.2 of the specification: expression evaluation,
built-in functions, operators, and effective boolean values.
"""

import math
import re
import urllib.parse
import uuid
from datetime import date, datetime, timezone
from typing import Optional, Union

from rdflib import BNode
from rdflib import Literal as RDFLiteral
from rdflib import Namespace, URIRef
from rdflib.term import Node as RDFNode

try:  # RDF-star triple term (rdflib >= 7)
    from rdflib.term import Triple as RDFTripleTerm  # type: ignore
except Exception:  # pragma: no cover
    RDFTripleTerm = None

from ..ast.nodes import (
    IRI,
    BinaryOp,
    BinaryOperator,
    BlankNode,
    BuiltInCall,
    Expression,
    FunctionCall,
    Literal,
    UnaryOp,
    UnaryOperator,
    Variable,
)
from .solutions import SolutionMapping, substitute_term

# XSD namespace for datatype operations
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")


class EvaluationError(Exception):
    """Error during expression evaluation."""

    pass


def eval_expr(expr: Expression, mu: SolutionMapping, active_graph=None) -> Optional[RDFNode]:
    """
    Evaluate an expression given a solution mapping.

    From Section 5.2:
    "The function eval(expr, μ, G) evaluates an expression expr with respect
    to a solution mapping μ and an RDF graph G."

    Args:
        expr: Expression to evaluate
        mu: Solution mapping for variable bindings
        active_graph: Optional RDF graph for graph-dependent operations

    Returns:
        RDF term result, or None if evaluation produces an error
    """
    try:
        if isinstance(expr, Variable):
            # Dereference variable
            if expr.name in mu:
                return mu[expr.name]
            else:
                raise EvaluationError(f"Unbound variable: {expr.name}")

        elif isinstance(expr, (IRI, Literal, BlankNode)):
            # Constant term
            return substitute_term(expr, mu)

        elif isinstance(expr, BinaryOp):
            return eval_binary_op(expr, mu, active_graph)

        elif isinstance(expr, UnaryOp):
            return eval_unary_op(expr, mu, active_graph)

        elif isinstance(expr, BuiltInCall):
            return eval_builtin(expr, mu, active_graph)

        elif isinstance(expr, FunctionCall):
            return eval_function_call(expr, mu, active_graph)

        else:
            raise EvaluationError(f"Unknown expression type: {type(expr)}")

    except EvaluationError:
        # Propagate evaluation errors as None (SPARQL semantics)
        return None


def _ebv_or_error(term: Optional[RDFNode]) -> Optional[bool]:
    """Three-valued EBV for the logical connectives: ``None`` denotes an error
    (an unevaluable operand), otherwise the effective boolean value. Callers use
    ``is True`` / ``is False`` so an error never counts as either truth value."""
    if term is None:
        return None
    return effective_boolean_value(term)


def effective_boolean_value(term: Optional[RDFNode]) -> bool:
    """
    Compute the effective boolean value (EBV) of an RDF term.

    From SPARQL specification:
    - Boolean: use its value
    - String: false if empty, true otherwise
    - Numeric: false if zero or NaN, true otherwise
    - Otherwise: error (returns False here)
    """
    if term is None:
        return False

    if isinstance(term, RDFLiteral):
        # Boolean literal
        if term.datatype == XSD.boolean:
            # Value might be Python bool or string
            if isinstance(term.value, bool):
                return term.value
            else:
                return str(term.value).lower() in ("true", "1")

        # Numeric types (including datatypes derived from a numeric type, e.g.
        # xsd:int, xsd:long, xsd:positiveInteger): false iff zero or NaN.
        if is_numeric(term):
            try:
                num_val = float(term.value)
                return num_val != 0.0 and not (num_val != num_val)  # not NaN
            except Exception:
                return False

        # Simple (plain or xsd:string) literal: false iff empty.
        if term.datatype == XSD.string or term.datatype is None:
            return len(str(term)) > 0

    # For other types (IRIs, blank nodes, ill-typed literals), EBV is an error.
    return False


# ===========================================================================
# Binary operators
# ===========================================================================


def eval_binary_op(expr: BinaryOp, mu: SolutionMapping, active_graph=None) -> Optional[RDFNode]:
    """Evaluate binary operation."""
    left_val = eval_expr(expr.left, mu, active_graph)

    # Logical connectives use SPARQL three-valued logic: an error operand is
    # NOT simply false. A value of None here denotes an error.
    #   true  || X     = true
    #   false || X     = X's EBV, but false||error = error
    #   false && X     = false
    #   true  && X     = X's EBV, but true&&error  = error
    if expr.operator == BinaryOperator.OR:
        if _ebv_or_error(left_val) is True:
            return RDFLiteral(True)
        right_val = eval_expr(expr.right, mu, active_graph)
        if _ebv_or_error(right_val) is True:
            return RDFLiteral(True)
        # Both sides false-or-error: error if either operand errored.
        if left_val is None or right_val is None:
            return None
        return RDFLiteral(False)

    elif expr.operator == BinaryOperator.AND:
        if _ebv_or_error(left_val) is False:
            return RDFLiteral(False)
        right_val = eval_expr(expr.right, mu, active_graph)
        if _ebv_or_error(right_val) is False:
            return RDFLiteral(False)
        # Both sides true-or-error: error if either operand errored.
        if left_val is None or right_val is None:
            return None
        return RDFLiteral(True)

    # For other operators, evaluate both sides
    right_val = eval_expr(expr.right, mu, active_graph)

    if left_val is None or right_val is None:
        return None

    # Comparison operators
    if expr.operator == BinaryOperator.EQ:
        result = rdf_equal(left_val, right_val)
        return RDFLiteral(result, datatype=XSD.boolean)
    elif expr.operator == BinaryOperator.NE:
        result = not rdf_equal(left_val, right_val)
        return RDFLiteral(result, datatype=XSD.boolean)
    elif expr.operator == BinaryOperator.LT:
        result = rdf_compare(left_val, right_val) < 0
        return RDFLiteral(result, datatype=XSD.boolean)
    elif expr.operator == BinaryOperator.LE:
        result = rdf_compare(left_val, right_val) <= 0
        return RDFLiteral(result, datatype=XSD.boolean)
    elif expr.operator == BinaryOperator.GT:
        result = rdf_compare(left_val, right_val) > 0
        return RDFLiteral(result, datatype=XSD.boolean)
    elif expr.operator == BinaryOperator.GE:
        result = rdf_compare(left_val, right_val) >= 0
        return RDFLiteral(result, datatype=XSD.boolean)

    # Arithmetic operators
    elif expr.operator == BinaryOperator.ADD:
        return numeric_add(left_val, right_val)
    elif expr.operator == BinaryOperator.SUB:
        return numeric_subtract(left_val, right_val)
    elif expr.operator == BinaryOperator.MUL:
        return numeric_multiply(left_val, right_val)
    elif expr.operator == BinaryOperator.DIV:
        return numeric_divide(left_val, right_val)

    else:
        raise EvaluationError(f"Unknown binary operator: {expr.operator}")


def eval_unary_op(expr: UnaryOp, mu: SolutionMapping, active_graph=None) -> Optional[RDFNode]:
    """Evaluate unary operation."""
    operand = eval_expr(expr.operand, mu, active_graph)

    if operand is None:
        return None

    if expr.operator == UnaryOperator.NOT:
        result = not effective_boolean_value(operand)
        return RDFLiteral(result)

    elif expr.operator == UnaryOperator.PLUS:
        # Unary plus - return as-is for numeric values
        if isinstance(operand, RDFLiteral) and is_numeric(operand):
            return operand
        return None

    elif expr.operator == UnaryOperator.MINUS:
        # Unary minus - negate numeric value
        return numeric_negate(operand)

    else:
        raise EvaluationError(f"Unknown unary operator: {expr.operator}")


# ===========================================================================
# Built-in functions (Section 5.2)
# ===========================================================================


def eval_builtin(call: BuiltInCall, mu: SolutionMapping, active_graph=None) -> Optional[RDFNode]:
    """Evaluate a built-in function call."""
    func_name = call.function_name.upper()

    # Functional forms (IF, IN) evaluate their arguments lazily/variadically;
    # handle them before the eager-argument dispatch below.
    if func_name == "IF":
        if len(call.arguments) == 3:
            cond = eval_expr(call.arguments[0], mu, active_graph)
            if cond is None:
                return None  # error condition -> error
            if effective_boolean_value(cond):
                return eval_expr(call.arguments[1], mu, active_graph)
            return eval_expr(call.arguments[2], mu, active_graph)
        return None

    if func_name == "IN":
        # From RelationalExpression: IN checks membership.
        if len(call.arguments) < 1:
            return RDFLiteral(False)
        test_val = eval_expr(call.arguments[0], mu, active_graph)
        for i in range(1, len(call.arguments)):
            candidate = eval_expr(call.arguments[i], mu, active_graph)
            if rdf_equal(test_val, candidate):
                return RDFLiteral(True)
        return RDFLiteral(False)

    handler = _BUILTIN_DISPATCH.get(func_name)
    if handler is None:
        raise EvaluationError(f"Unknown built-in function: {func_name}")

    # Eagerly evaluate arguments; a handler receives the list of evaluated args.
    args = [eval_expr(arg_expr, mu, active_graph) for arg_expr in call.arguments]
    return handler(args)


def eval_function_call(
    call: FunctionCall, mu: SolutionMapping, active_graph=None
) -> Optional[RDFNode]:
    """
    Evaluate a custom function call.

    This is a placeholder - custom functions would need to be registered
    with the evaluation context.
    """
    # For now, raise an error
    raise EvaluationError(f"Custom function calls not yet supported: {call.function}")


# ===========================================================================
# Built-in function implementations
# ===========================================================================


def builtin_str(args) -> Optional[RDFNode]:
    """STR(term) - convert to string."""
    if len(args) != 1 or args[0] is None:
        return None
    term = args[0]
    if isinstance(term, URIRef):
        return RDFLiteral(str(term))
    elif isinstance(term, RDFLiteral):
        return RDFLiteral(str(term))
    elif isinstance(term, BNode):
        return RDFLiteral(str(term))
    return None


def builtin_lang(args) -> Optional[RDFNode]:
    """LANG(literal) - get language tag."""
    if len(args) != 1 or args[0] is None:
        return None
    term = args[0]
    if isinstance(term, RDFLiteral) and term.language:
        return RDFLiteral(term.language)
    return RDFLiteral("")


def builtin_langmatches(args) -> Optional[RDFNode]:
    """LANGMATCHES(lang-tag, lang-range) - match language tag."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    tag = str(args[0]).lower()
    range_val = str(args[1]).lower()

    if range_val == "*":
        return RDFLiteral(len(tag) > 0)

    # RFC 4647 basic filtering: the range matches the tag, or a prefix of the
    # tag ending on a subtag boundary ('-'). So 'en' matches 'en' and 'en-US'
    # but not 'english'.
    matches = tag == range_val or tag.startswith(range_val + "-")
    return RDFLiteral(matches)


def builtin_datatype(args) -> Optional[RDFNode]:
    """DATATYPE(literal) - get datatype IRI."""
    if len(args) != 1 or args[0] is None:
        return None
    term = args[0]
    if isinstance(term, RDFLiteral):
        if term.datatype:
            return term.datatype
        elif term.language:
            return RDF.langString
        else:
            return XSD.string
    return None


def builtin_iri(args) -> Optional[RDFNode]:
    """IRI(string) - construct IRI from string."""
    if len(args) != 1 or args[0] is None:
        return None

    if isinstance(args[0], URIRef):
        return args[0]
    elif isinstance(args[0], RDFLiteral):
        try:
            return URIRef(str(args[0]))
        except:
            return None
    return None


def builtin_bnode(args) -> Optional[RDFNode]:
    """BNODE() or BNODE(string) - create blank node."""
    if len(args) == 0:
        return BNode()
    elif len(args) == 1 and args[0] is not None:
        label = str(args[0])
        return BNode(label)
    return None


def builtin_strdt(args) -> Optional[RDFNode]:
    """STRDT(lex, datatype) - construct typed literal."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    lex = str(args[0])
    datatype = args[1]

    if isinstance(datatype, URIRef):
        return RDFLiteral(lex, datatype=datatype)
    return None


def builtin_strlang(args) -> Optional[RDFNode]:
    """STRLANG(lex, lang) - construct language-tagged literal."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    lex = str(args[0])
    lang = str(args[1])

    return RDFLiteral(lex, lang=lang)


def builtin_uuid(args) -> Optional[RDFNode]:
    """UUID() - generate UUID IRI."""
    return URIRef(f"urn:uuid:{uuid.uuid4()}")


def builtin_struuid(args) -> Optional[RDFNode]:
    """STRUUID() - generate UUID string."""
    return RDFLiteral(str(uuid.uuid4()))


def builtin_strlen(args) -> Optional[RDFNode]:
    """STRLEN(string) - string length."""
    if len(args) != 1 or args[0] is None:
        return None

    s = str(args[0])
    return RDFLiteral(len(s), datatype=XSD.integer)


def _string_literal_like(source, text: str) -> RDFNode:
    """Build a string literal carrying the source literal's language tag or
    xsd:string datatype, per SPARQL string-function return semantics."""
    if isinstance(source, RDFLiteral):
        if source.language:
            return RDFLiteral(text, lang=source.language)
        if source.datatype == XSD.string:
            return RDFLiteral(text, datatype=XSD.string)
    return RDFLiteral(text)


def builtin_substr(args) -> Optional[RDFNode]:
    """SUBSTR(string, start[, length]) - substring (preserves lang/datatype)."""
    if len(args) < 2 or args[0] is None or args[1] is None:
        return None

    s = str(args[0])
    start = int(str(args[1])) - 1  # 1-indexed in SPARQL

    if len(args) >= 3 and args[2] is not None:
        length = int(str(args[2]))
        result = s[start : start + length]
    else:
        result = s[start:]
    return _string_literal_like(args[0], result)


def builtin_ucase(args) -> Optional[RDFNode]:
    """UCASE(string) - uppercase (preserves lang/datatype)."""
    if len(args) != 1 or args[0] is None:
        return None
    return _string_literal_like(args[0], str(args[0]).upper())


def builtin_lcase(args) -> Optional[RDFNode]:
    """LCASE(string) - lowercase (preserves lang/datatype)."""
    if len(args) != 1 or args[0] is None:
        return None
    return _string_literal_like(args[0], str(args[0]).lower())


def builtin_strstarts(args) -> Optional[RDFNode]:
    """STRSTARTS(string, prefix) - test if string starts with prefix."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    s = str(args[0])
    prefix = str(args[1])
    return RDFLiteral(s.startswith(prefix))


def builtin_strends(args) -> Optional[RDFNode]:
    """STRENDS(string, suffix) - test if string ends with suffix."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    s = str(args[0])
    suffix = str(args[1])
    return RDFLiteral(s.endswith(suffix))


def builtin_contains(args) -> Optional[RDFNode]:
    """CONTAINS(string, substring) - test if string contains substring."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    s = str(args[0])
    substring = str(args[1])
    return RDFLiteral(substring in s)


def builtin_strbefore(args) -> Optional[RDFNode]:
    """STRBEFORE(string, substring) - part before first occurrence."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    s = str(args[0])
    substring = str(args[1])

    idx = s.find(substring)
    if idx >= 0:
        return _string_literal_like(args[0], s[:idx])
    else:
        return RDFLiteral("")


def builtin_strafter(args) -> Optional[RDFNode]:
    """STRAFTER(string, substring) - part after first occurrence."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None

    s = str(args[0])
    substring = str(args[1])

    idx = s.find(substring)
    if idx >= 0:
        return _string_literal_like(args[0], s[idx + len(substring) :])
    else:
        return RDFLiteral("")


def builtin_encode_for_uri(args) -> Optional[RDFNode]:
    """ENCODE_FOR_URI(string) - percent-encode for URI."""
    if len(args) != 1 or args[0] is None:
        return None

    s = str(args[0])
    return RDFLiteral(urllib.parse.quote(s, safe=""))


def builtin_concat(args) -> Optional[RDFNode]:
    """CONCAT(string...) - concatenate strings.

    Per SPARQL: if all arguments share a common language tag, the result keeps
    it; if all are xsd:string, the result is xsd:string; otherwise a plain
    literal.
    """
    if any(arg is None for arg in args):
        return None

    result = "".join(str(arg) for arg in args)
    if not args:
        return RDFLiteral(result)

    langs = {a.language for a in args if isinstance(a, RDFLiteral)}
    non_literal = any(not isinstance(a, RDFLiteral) for a in args)
    if not non_literal and len(langs) == 1 and next(iter(langs)):
        return RDFLiteral(result, lang=next(iter(langs)))
    dts = {a.datatype for a in args if isinstance(a, RDFLiteral)}
    if not non_literal and langs == {None} and dts == {XSD.string}:
        return RDFLiteral(result, datatype=XSD.string)
    return RDFLiteral(result)


def _regex_flags(flags: str) -> int:
    """Translate SPARQL REGEX/REPLACE flag characters to Python ``re`` flags."""
    result = 0
    if "i" in flags:
        result |= re.IGNORECASE
    if "m" in flags:
        result |= re.MULTILINE
    if "s" in flags:
        result |= re.DOTALL
    return result


def builtin_replace(args) -> Optional[RDFNode]:
    """REPLACE(string, pattern, replacement[, flags]) - regex replace."""
    if len(args) < 3 or any(arg is None for arg in args[:3]):
        return None

    s = str(args[0])
    pattern = str(args[1])
    replacement = str(args[2])
    flags = str(args[3]) if len(args) >= 4 and args[3] is not None else ""

    try:
        result = re.sub(pattern, replacement, s, flags=_regex_flags(flags))
        return _string_literal_like(args[0], result)
    except:
        return None


def builtin_abs(args) -> Optional[RDFNode]:
    """ABS(numeric) - absolute value."""
    if len(args) != 1 or args[0] is None:
        return None

    if isinstance(args[0], RDFLiteral) and is_numeric(args[0]):
        val = numeric_value(args[0])
        result = abs(val)
        return RDFLiteral(result, datatype=args[0].datatype)
    return None


def _round_like(args, fn) -> Optional[RDFNode]:
    """Shared ROUND/CEIL/FLOOR body: apply fn, preserving the argument's
    numeric datatype (per XPath fn:round/ceiling/floor return types)."""
    if len(args) != 1 or args[0] is None:
        return None
    if isinstance(args[0], RDFLiteral) and is_numeric(args[0]):
        val = numeric_value(args[0])
        result = fn(val)
        dt = args[0].datatype or XSD.integer
        if dt in (XSD.integer,) or (
            isinstance(val, int) and dt not in (XSD.decimal, XSD.double, XSD.float)
        ):
            return RDFLiteral(int(result), datatype=dt if dt else XSD.integer)
        # decimal/double/float keep their type.
        return RDFLiteral(type(val)(result), datatype=dt)
    return None


def _round_half_up(val):
    """SPARQL/XPath fn:round: round half toward positive infinity."""
    return math.floor(val + 0.5)


def builtin_round(args) -> Optional[RDFNode]:
    """ROUND(numeric) - round half up, preserving numeric datatype."""
    return _round_like(args, _round_half_up)


def builtin_ceil(args) -> Optional[RDFNode]:
    """CEIL(numeric) - ceiling, preserving numeric datatype."""
    return _round_like(args, math.ceil)


def builtin_floor(args) -> Optional[RDFNode]:
    """FLOOR(numeric) - floor, preserving numeric datatype."""
    return _round_like(args, math.floor)


def builtin_now(args) -> Optional[RDFNode]:
    """NOW() - current datetime."""
    now = datetime.now(timezone.utc)
    return RDFLiteral(now.isoformat(), datatype=XSD.dateTime)


def _parse_datetime(arg):
    """Parse an xsd:dateTime/date literal into a datetime, or None on error."""
    if arg is None:
        return None
    # rdflib may already expose a datetime/date via .toPython().
    if isinstance(arg, RDFLiteral):
        py = arg.toPython()
        if isinstance(py, (datetime, date)):
            return py
    s = str(arg)
    # Normalise a trailing 'Z' to +00:00 for fromisoformat.
    iso = s[:-1] + "+00:00" if s.endswith("Z") else s
    for parse in (datetime.fromisoformat,):
        try:
            return parse(iso)
        except Exception:
            pass
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def builtin_year(args) -> Optional[RDFNode]:
    """YEAR(datetime) - extract year."""
    dt = _parse_datetime(args[0] if args else None)
    return RDFLiteral(dt.year, datatype=XSD.integer) if dt else None


def builtin_month(args) -> Optional[RDFNode]:
    """MONTH(datetime) - extract month."""
    dt = _parse_datetime(args[0] if args else None)
    return RDFLiteral(dt.month, datatype=XSD.integer) if dt else None


def builtin_day(args) -> Optional[RDFNode]:
    """DAY(datetime) - extract day."""
    dt = _parse_datetime(args[0] if args else None)
    return RDFLiteral(dt.day, datatype=XSD.integer) if dt else None


def builtin_hours(args) -> Optional[RDFNode]:
    """HOURS(datetime) - extract hours."""
    dt = _parse_datetime(args[0] if args else None)
    return (
        RDFLiteral(getattr(dt, "hour", None), datatype=XSD.integer)
        if dt is not None and hasattr(dt, "hour")
        else None
    )


def builtin_minutes(args) -> Optional[RDFNode]:
    """MINUTES(datetime) - extract minutes."""
    dt = _parse_datetime(args[0] if args else None)
    return (
        RDFLiteral(dt.minute, datatype=XSD.integer)
        if dt is not None and hasattr(dt, "minute")
        else None
    )


def builtin_seconds(args) -> Optional[RDFNode]:
    """SECONDS(datetime) - extract seconds (as xsd:decimal, including fraction)."""
    dt = _parse_datetime(args[0] if args else None)
    if dt is None or not hasattr(dt, "second"):
        return None
    secs = dt.second + (dt.microsecond / 1_000_000 if dt.microsecond else 0)
    return RDFLiteral(str(secs), datatype=XSD.decimal)


def builtin_timezone(args) -> Optional[RDFNode]:
    """TIMEZONE(datetime) - timezone as an xsd:dayTimeDuration."""
    dt = _parse_datetime(args[0] if args else None)
    if dt is None or getattr(dt, "tzinfo", None) is None:
        return None
    offset = dt.utcoffset()
    if offset is None:
        return None
    total = int(offset.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if total == 0:
        dur = "PT0S"
    else:
        dur = (
            f"{sign}PT"
            + (f"{hours}H" if hours else "")
            + (f"{minutes}M" if minutes else "")
            + (f"{seconds}S" if seconds else "")
        )
    return RDFLiteral(dur, datatype=URIRef(str(XSD) + "dayTimeDuration"))


def builtin_tz(args) -> Optional[RDFNode]:
    """TZ(datetime) - timezone as a simple string ('Z', '+01:00', '' if none)."""
    dt = _parse_datetime(args[0] if args else None)
    if dt is None or not hasattr(dt, "second"):
        return None
    tz = getattr(dt, "tzinfo", None)
    if tz is None:
        return RDFLiteral("")
    offset = dt.utcoffset()
    if offset is None or offset.total_seconds() == 0:
        return RDFLiteral("Z")
    total = int(offset.total_seconds())
    sign = "-" if total < 0 else "+"
    total = abs(total)
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    return RDFLiteral(f"{sign}{hours:02d}:{minutes:02d}")


def _type_test(args, predicate) -> RDFNode:
    """Shared body for the term-testing built-ins (isIRI/isBLANK/isLITERAL/
    isNUMERIC): false for a missing/unbound single argument, else predicate."""
    if len(args) != 1 or args[0] is None:
        return RDFLiteral(False)
    return RDFLiteral(predicate(args[0]))


def builtin_isiri(args) -> Optional[RDFNode]:
    """ISIRI(term) - test if term is IRI."""
    return _type_test(args, lambda t: isinstance(t, URIRef))


def builtin_isblank(args) -> Optional[RDFNode]:
    """ISBLANK(term) - test if term is blank node."""
    return _type_test(args, lambda t: isinstance(t, BNode))


def builtin_isliteral(args) -> Optional[RDFNode]:
    """ISLITERAL(term) - test if term is literal."""
    return _type_test(args, lambda t: isinstance(t, RDFLiteral))


def builtin_isnumeric(args) -> Optional[RDFNode]:
    """ISNUMERIC(term) - test if term is numeric literal."""
    return _type_test(args, lambda t: isinstance(t, RDFLiteral) and is_numeric(t))


def builtin_regex(args) -> Optional[RDFNode]:
    """REGEX(text, pattern[, flags]) - regex test."""
    if len(args) < 2 or args[0] is None or args[1] is None:
        return None

    text = str(args[0])
    pattern = str(args[1])
    flags = str(args[2]) if len(args) >= 3 and args[2] is not None else ""

    try:
        match = re.search(pattern, text, flags=_regex_flags(flags))
        return RDFLiteral(match is not None)
    except:
        return None


# ===========================================================================
# Directional language / language-tag built-ins (RDF 1.2)
# ===========================================================================


def _literal_direction(term) -> Optional[str]:
    """Return the base direction ('ltr'/'rtl') of a dir-language literal, if any."""
    # rdflib may expose the direction as an attribute on the literal.
    return getattr(term, "direction", None) if isinstance(term, RDFLiteral) else None


def builtin_langdir(args) -> Optional[RDFNode]:
    """LANGDIR(literal) - base direction of a directional language literal."""
    if len(args) != 1 or args[0] is None:
        return None
    direction = _literal_direction(args[0])
    return RDFLiteral(direction if direction else "")


def builtin_strlangdir(args) -> Optional[RDFNode]:
    """STRLANGDIR(lex, lang, dir) - construct a directional language literal."""
    if len(args) != 3 or any(a is None for a in args):
        return None
    lex, lang, direction = str(args[0]), str(args[1]), str(args[2])
    try:
        return RDFLiteral(lex, lang=lang, direction=direction)  # rdflib >= 7
    except TypeError:
        # Older rdflib without direction support: fall back to language literal.
        return RDFLiteral(lex, lang=lang)


def builtin_haslang(args) -> Optional[RDFNode]:
    """hasLANG(literal) - true if the literal has a (non-empty) language tag."""
    if len(args) != 1 or args[0] is None:
        return None
    return RDFLiteral(isinstance(args[0], RDFLiteral) and bool(args[0].language))


def builtin_haslangdir(args) -> Optional[RDFNode]:
    """hasLANGDIR(literal) - true if the literal has a base direction."""
    if len(args) != 1 or args[0] is None:
        return None
    return RDFLiteral(bool(_literal_direction(args[0])))


def builtin_sameterm(args) -> Optional[RDFNode]:
    """sameTerm(a, b) - RDF term identity (not value equality)."""
    if len(args) != 2 or args[0] is None or args[1] is None:
        return None
    a, b = args[0], args[1]
    # Term identity: same Python/RDF term, including datatype and language.
    if isinstance(a, RDFLiteral) and isinstance(b, RDFLiteral):
        same = str(a) == str(b) and a.datatype == b.datatype and a.language == b.language
        return RDFLiteral(same)
    return RDFLiteral(a == b and type(a) == type(b))


# ===========================================================================
# RDF-star triple-term built-ins
# ===========================================================================


def _as_triple_parts(term):
    """Return (s, p, o) if term is a triple term, else None."""
    if RDFTripleTerm is not None and isinstance(term, RDFTripleTerm):
        return term[0], term[1], term[2]
    if isinstance(term, tuple) and len(term) == 3:
        return term
    return None


def builtin_istriple(args) -> Optional[RDFNode]:
    """isTRIPLE(term) - true if term is a triple term."""
    if len(args) != 1 or args[0] is None:
        return RDFLiteral(False)
    return RDFLiteral(_as_triple_parts(args[0]) is not None)


def builtin_triple(args) -> Optional[RDFNode]:
    """TRIPLE(s, p, o) - construct a triple term."""
    if len(args) != 3 or any(a is None for a in args):
        return None
    s, p, o = args
    if RDFTripleTerm is not None:
        return RDFTripleTerm((s, p, o))
    return (s, p, o)


def builtin_triple_subject(args) -> Optional[RDFNode]:
    """SUBJECT(triple) - subject of a triple term."""
    if len(args) != 1 or args[0] is None:
        return None
    parts = _as_triple_parts(args[0])
    return parts[0] if parts else None


def builtin_triple_predicate(args) -> Optional[RDFNode]:
    """PREDICATE(triple) - predicate of a triple term."""
    if len(args) != 1 or args[0] is None:
        return None
    parts = _as_triple_parts(args[0])
    return parts[1] if parts else None


def builtin_triple_object(args) -> Optional[RDFNode]:
    """OBJECT(triple) - object of a triple term."""
    if len(args) != 1 or args[0] is None:
        return None
    parts = _as_triple_parts(args[0])
    return parts[2] if parts else None


# ===========================================================================
# Helper functions
# ===========================================================================

_NUMERIC_DATATYPES = frozenset(
    (
        XSD.integer,
        XSD.decimal,
        XSD.double,
        XSD.float,
        XSD.int,
        XSD.long,
        XSD.short,
        XSD.byte,
        XSD.nonNegativeInteger,
        XSD.positiveInteger,
        XSD.unsignedLong,
        XSD.unsignedInt,
        XSD.unsignedShort,
        XSD.unsignedByte,
        XSD.nonPositiveInteger,
        XSD.negativeInteger,
    )
)


def is_numeric(term: RDFLiteral) -> bool:
    """Check if a literal is numeric."""
    if not isinstance(term, RDFLiteral):
        return False
    return term.datatype in _NUMERIC_DATATYPES


def numeric_value(term: RDFLiteral) -> Union[int, float]:
    """Extract numeric value from literal."""
    if term.datatype in (XSD.double, XSD.float):
        return float(term.value)
    elif term.datatype == XSD.decimal:
        return float(term.value)  # Could use Decimal for precision
    else:
        return int(term.value)


def rdf_equal(term1: RDFNode, term2: RDFNode) -> bool:
    """
    Test RDF term equality following SPARQL semantics.
    """
    # Same term
    if term1 == term2:
        return True

    # Both literals with compatible types
    if isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral):
        # Numeric comparison
        if is_numeric(term1) and is_numeric(term2):
            try:
                return numeric_value(term1) == numeric_value(term2)
            except:
                return False

        # Language-tagged literals: equal only if both lexical form AND
        # language tag match. A lang-tagged literal is never value-equal to a
        # plain/typed string.
        lang1 = term1.language
        lang2 = term2.language
        if lang1 or lang2:
            return lang1 == lang2 and str(term1) == str(term2)

        # Simple/typed string comparison (no language tags involved).
        if term1.datatype == term2.datatype or (
            term1.datatype in (None, XSD.string) and term2.datatype in (None, XSD.string)
        ):
            return str(term1) == str(term2)

    return False


def rdf_compare(term1: RDFNode, term2: RDFNode) -> int:
    """
    Compare two RDF terms (for <, <=, >, >= operators).
    Returns: -1 if term1 < term2, 0 if equal, 1 if term1 > term2
    """
    # Numeric comparison
    if isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral):
        if is_numeric(term1) and is_numeric(term2):
            val1 = numeric_value(term1)
            val2 = numeric_value(term2)
            if val1 < val2:
                return -1
            elif val1 > val2:
                return 1
            else:
                return 0

        # String comparison
        str1 = str(term1)
        str2 = str(term2)
        if str1 < str2:
            return -1
        elif str1 > str2:
            return 1
        else:
            return 0

    # Compare as strings
    str1 = str(term1)
    str2 = str(term2)
    if str1 < str2:
        return -1
    elif str1 > str2:
        return 1
    else:
        return 0


def _promote_datatype(dt1: Optional[URIRef], dt2: Optional[URIRef]) -> URIRef:
    """XPath numeric type promotion for +, -, * : the widest of the two operand
    datatypes, in the order double > float > decimal > integer."""
    if dt1 == XSD.double or dt2 == XSD.double:
        return XSD.double
    if dt1 == XSD.float or dt2 == XSD.float:
        return XSD.float
    if dt1 == XSD.decimal or dt2 == XSD.decimal:
        return XSD.decimal
    return XSD.integer


def _numeric_binop(term1: RDFNode, term2: RDFNode, op) -> Optional[RDFNode]:
    """Apply an arithmetic op to two numeric literals, promoting the result
    datatype per XPath rules. Returns None unless both operands are numeric."""
    if not (isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral)):
        return None
    if not (is_numeric(term1) and is_numeric(term2)):
        return None

    result = op(numeric_value(term1), numeric_value(term2))
    dt = _promote_datatype(term1.datatype, term2.datatype)
    if dt == XSD.integer:
        return RDFLiteral(int(result), datatype=XSD.integer)
    return RDFLiteral(result, datatype=dt)


def numeric_add(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Add two numeric literals."""
    return _numeric_binop(term1, term2, lambda a, b: a + b)


def numeric_subtract(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Subtract two numeric literals."""
    return _numeric_binop(term1, term2, lambda a, b: a - b)


def numeric_multiply(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Multiply two numeric literals."""
    return _numeric_binop(term1, term2, lambda a, b: a * b)


def numeric_divide(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Divide two numeric literals. Division always yields decimal or double,
    and division by zero is an error (None)."""
    if not (isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral)):
        return None
    if not (is_numeric(term1) and is_numeric(term2)):
        return None

    val2 = numeric_value(term2)
    if val2 == 0:
        return None  # Division by zero

    result = numeric_value(term1) / val2
    if term1.datatype == XSD.double or term2.datatype == XSD.double:
        return RDFLiteral(result, datatype=XSD.double)
    return RDFLiteral(result, datatype=XSD.decimal)


# ===========================================================================
# Built-in dispatch table (spec [121] set + IN/IF handled specially above)
# ===========================================================================
# Maps the upper-cased function name to its eager-argument handler. Aliases
# (URI→IRI, ISURI→ISIRI) point at the same function.
_BUILTIN_DISPATCH = {
    "STR": builtin_str,
    "LANG": builtin_lang,
    "LANGMATCHES": builtin_langmatches,
    "LANGDIR": builtin_langdir,
    "DATATYPE": builtin_datatype,
    "IRI": builtin_iri,
    "URI": builtin_iri,
    "BNODE": builtin_bnode,
    "STRDT": builtin_strdt,
    "STRLANG": builtin_strlang,
    "STRLANGDIR": builtin_strlangdir,
    "UUID": builtin_uuid,
    "STRUUID": builtin_struuid,
    "STRLEN": builtin_strlen,
    "SUBSTR": builtin_substr,
    "UCASE": builtin_ucase,
    "LCASE": builtin_lcase,
    "STRSTARTS": builtin_strstarts,
    "STRENDS": builtin_strends,
    "CONTAINS": builtin_contains,
    "STRBEFORE": builtin_strbefore,
    "STRAFTER": builtin_strafter,
    "ENCODE_FOR_URI": builtin_encode_for_uri,
    "CONCAT": builtin_concat,
    "REPLACE": builtin_replace,
    "ABS": builtin_abs,
    "ROUND": builtin_round,
    "CEIL": builtin_ceil,
    "FLOOR": builtin_floor,
    "NOW": builtin_now,
    "YEAR": builtin_year,
    "MONTH": builtin_month,
    "DAY": builtin_day,
    "HOURS": builtin_hours,
    "MINUTES": builtin_minutes,
    "SECONDS": builtin_seconds,
    "TIMEZONE": builtin_timezone,
    "TZ": builtin_tz,
    "SAMETERM": builtin_sameterm,
    "ISIRI": builtin_isiri,
    "ISURI": builtin_isiri,
    "ISBLANK": builtin_isblank,
    "ISLITERAL": builtin_isliteral,
    "ISNUMERIC": builtin_isnumeric,
    "HASLANG": builtin_haslang,
    "HASLANGDIR": builtin_haslangdir,
    "REGEX": builtin_regex,
    "ISTRIPLE": builtin_istriple,
    "TRIPLE": builtin_triple,
    "SUBJECT": builtin_triple_subject,
    "PREDICATE": builtin_triple_predicate,
    "OBJECT": builtin_triple_object,
}


def numeric_negate(term: RDFNode) -> Optional[RDFNode]:
    """Negate a numeric literal."""
    if not isinstance(term, RDFLiteral) or not is_numeric(term):
        return None

    val = numeric_value(term)
    result = -val

    return RDFLiteral(result, datatype=term.datatype)
