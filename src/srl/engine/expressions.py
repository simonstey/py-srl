"""
Expression evaluation for SHACL 1.2 Rules.

Implements Section 5.2 of the specification: expression evaluation,
built-in functions, operators, and effective boolean values.
"""

from typing import Any, Union, Optional
from decimal import Decimal
from datetime import datetime
import re

from rdflib import Literal as RDFLiteral, URIRef, BNode, Namespace
from rdflib.term import Node as RDFNode

from ..ast.nodes import (
    Expression, BinaryOp, UnaryOp, FunctionCall, BuiltInCall,
    BinaryOperator, UnaryOperator,
    Variable, IRI, Literal, BlankNode,
)
from .solutions import SolutionMapping, substitute_term


# XSD namespace for datatype operations
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")


class EvaluationError(Exception):
    """Error during expression evaluation."""
    pass


def eval_expr(
    expr: Expression,
    mu: SolutionMapping,
    active_graph=None
) -> Optional[RDFNode]:
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
                return str(term.value).lower() in ('true', '1')
        
        # String literal
        if term.datatype == XSD.string or term.datatype is None:
            return len(str(term)) > 0
        
        # Numeric types
        if term.datatype in (XSD.integer, XSD.decimal, XSD.double, XSD.float):
            try:
                num_val = float(term.value)
                return num_val != 0.0 and not (num_val != num_val)  # not NaN
            except:
                return False
    
    # For other types, return False
    return False


# ===========================================================================
# Binary operators
# ===========================================================================

def eval_binary_op(
    expr: BinaryOp,
    mu: SolutionMapping,
    active_graph=None
) -> Optional[RDFNode]:
    """Evaluate binary operation."""
    left_val = eval_expr(expr.left, mu, active_graph)
    
    # Short-circuit evaluation for logical operators
    if expr.operator == BinaryOperator.OR:
        if effective_boolean_value(left_val):
            return RDFLiteral(True)
        right_val = eval_expr(expr.right, mu, active_graph)
        result = effective_boolean_value(right_val)
        return RDFLiteral(result)
    
    elif expr.operator == BinaryOperator.AND:
        if not effective_boolean_value(left_val):
            return RDFLiteral(False)
        right_val = eval_expr(expr.right, mu, active_graph)
        result = effective_boolean_value(right_val)
        return RDFLiteral(result)
    
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


def eval_unary_op(
    expr: UnaryOp,
    mu: SolutionMapping,
    active_graph=None
) -> Optional[RDFNode]:
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

def eval_builtin(
    call: BuiltInCall,
    mu: SolutionMapping,
    active_graph=None
) -> Optional[RDFNode]:
    """Evaluate a built-in function call."""
    func_name = call.function_name.upper()
    
    # Evaluate arguments
    args = []
    for arg_expr in call.arguments:
        arg_val = eval_expr(arg_expr, mu, active_graph)
        args.append(arg_val)
    
    # Dispatch to specific built-in
    if func_name == "STR":
        return builtin_str(args)
    elif func_name == "LANG":
        return builtin_lang(args)
    elif func_name == "LANGMATCHES":
        return builtin_langmatches(args)
    elif func_name == "DATATYPE":
        return builtin_datatype(args)
    elif func_name == "BOUND":
        # Special: BOUND doesn't evaluate its argument
        if len(call.arguments) == 1 and isinstance(call.arguments[0], Variable):
            var = call.arguments[0]
            return RDFLiteral(var.name in mu)
        return RDFLiteral(False)
    elif func_name == "IRI" or func_name == "URI":
        return builtin_iri(args)
    elif func_name == "BNODE":
        return builtin_bnode(args)
    elif func_name == "STRDT":
        return builtin_strdt(args)
    elif func_name == "STRLANG":
        return builtin_strlang(args)
    elif func_name == "UUID":
        return builtin_uuid(args)
    elif func_name == "STRUUID":
        return builtin_struuid(args)
    elif func_name == "STRLEN":
        return builtin_strlen(args)
    elif func_name == "SUBSTR":
        return builtin_substr(args)
    elif func_name == "UCASE":
        return builtin_ucase(args)
    elif func_name == "LCASE":
        return builtin_lcase(args)
    elif func_name == "STRSTARTS":
        return builtin_strstarts(args)
    elif func_name == "STRENDS":
        return builtin_strends(args)
    elif func_name == "CONTAINS":
        return builtin_contains(args)
    elif func_name == "STRBEFORE":
        return builtin_strbefore(args)
    elif func_name == "STRAFTER":
        return builtin_strafter(args)
    elif func_name == "ENCODE_FOR_URI":
        return builtin_encode_for_uri(args)
    elif func_name == "CONCAT":
        return builtin_concat(args)
    elif func_name == "REPLACE":
        return builtin_replace(args)
    elif func_name == "ABS":
        return builtin_abs(args)
    elif func_name == "ROUND":
        return builtin_round(args)
    elif func_name == "CEIL":
        return builtin_ceil(args)
    elif func_name == "FLOOR":
        return builtin_floor(args)
    elif func_name == "RAND":
        return builtin_rand(args)
    elif func_name == "NOW":
        return builtin_now(args)
    elif func_name == "YEAR":
        return builtin_year(args)
    elif func_name == "MONTH":
        return builtin_month(args)
    elif func_name == "DAY":
        return builtin_day(args)
    elif func_name == "HOURS":
        return builtin_hours(args)
    elif func_name == "MINUTES":
        return builtin_minutes(args)
    elif func_name == "SECONDS":
        return builtin_seconds(args)
    elif func_name == "TIMEZONE":
        return builtin_timezone(args)
    elif func_name == "TZ":
        return builtin_tz(args)
    elif func_name == "MD5":
        return builtin_md5(args)
    elif func_name == "SHA1":
        return builtin_sha1(args)
    elif func_name == "SHA256":
        return builtin_sha256(args)
    elif func_name == "SHA384":
        return builtin_sha384(args)
    elif func_name == "SHA512":
        return builtin_sha512(args)
    elif func_name == "ISIRI" or func_name == "ISURI":
        return builtin_isiri(args)
    elif func_name == "ISBLANK":
        return builtin_isblank(args)
    elif func_name == "ISLITERAL":
        return builtin_isliteral(args)
    elif func_name == "ISNUMERIC":
        return builtin_isnumeric(args)
    elif func_name == "REGEX":
        return builtin_regex(args)
    elif func_name == "IF":
        # Special: IF has conditional evaluation
        if len(call.arguments) == 3:
            cond = eval_expr(call.arguments[0], mu, active_graph)
            if effective_boolean_value(cond):
                return eval_expr(call.arguments[1], mu, active_graph)
            else:
                return eval_expr(call.arguments[2], mu, active_graph)
        return None
    elif func_name == "COALESCE":
        # Special: COALESCE returns first non-error value
        for arg_expr in call.arguments:
            val = eval_expr(arg_expr, mu, active_graph)
            if val is not None:
                return val
        return None
    elif func_name == "IN":
        # Special: IN checks membership
        if len(call.arguments) < 1:
            return RDFLiteral(False)
        test_val = eval_expr(call.arguments[0], mu, active_graph)
        for i in range(1, len(call.arguments)):
            candidate = eval_expr(call.arguments[i], mu, active_graph)
            if rdf_equal(test_val, candidate):
                return RDFLiteral(True)
        return RDFLiteral(False)
    else:
        # Unknown built-in function
        raise EvaluationError(f"Unknown built-in function: {func_name}")


def eval_function_call(
    call: FunctionCall,
    mu: SolutionMapping,
    active_graph=None
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
    
    # Simple prefix matching (simplified from RFC 4647)
    return RDFLiteral(tag.startswith(range_val))


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
    import uuid
    return URIRef(f"urn:uuid:{uuid.uuid4()}")


def builtin_struuid(args) -> Optional[RDFNode]:
    """STRUUID() - generate UUID string."""
    import uuid
    return RDFLiteral(str(uuid.uuid4()))


def builtin_strlen(args) -> Optional[RDFNode]:
    """STRLEN(string) - string length."""
    if len(args) != 1 or args[0] is None:
        return None
    
    s = str(args[0])
    return RDFLiteral(len(s), datatype=XSD.integer)


def builtin_substr(args) -> Optional[RDFNode]:
    """SUBSTR(string, start[, length]) - substring."""
    if len(args) < 2 or args[0] is None or args[1] is None:
        return None
    
    s = str(args[0])
    start = int(str(args[1])) - 1  # 1-indexed in SPARQL
    
    if len(args) >= 3 and args[2] is not None:
        length = int(str(args[2]))
        return RDFLiteral(s[start:start+length])
    else:
        return RDFLiteral(s[start:])


def builtin_ucase(args) -> Optional[RDFNode]:
    """UCASE(string) - uppercase."""
    if len(args) != 1 or args[0] is None:
        return None
    return RDFLiteral(str(args[0]).upper())


def builtin_lcase(args) -> Optional[RDFNode]:
    """LCASE(string) - lowercase."""
    if len(args) != 1 or args[0] is None:
        return None
    return RDFLiteral(str(args[0]).lower())


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
        return RDFLiteral(s[:idx])
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
        return RDFLiteral(s[idx+len(substring):])
    else:
        return RDFLiteral("")


def builtin_encode_for_uri(args) -> Optional[RDFNode]:
    """ENCODE_FOR_URI(string) - percent-encode for URI."""
    if len(args) != 1 or args[0] is None:
        return None
    
    import urllib.parse
    s = str(args[0])
    return RDFLiteral(urllib.parse.quote(s, safe=''))


def builtin_concat(args) -> Optional[RDFNode]:
    """CONCAT(string...) - concatenate strings."""
    if any(arg is None for arg in args):
        return None
    
    result = "".join(str(arg) for arg in args)
    return RDFLiteral(result)


def builtin_replace(args) -> Optional[RDFNode]:
    """REPLACE(string, pattern, replacement[, flags]) - regex replace."""
    if len(args) < 3 or any(arg is None for arg in args[:3]):
        return None
    
    s = str(args[0])
    pattern = str(args[1])
    replacement = str(args[2])
    flags = str(args[3]) if len(args) >= 4 and args[3] is not None else ""
    
    regex_flags = 0
    if 'i' in flags:
        regex_flags |= re.IGNORECASE
    if 'm' in flags:
        regex_flags |= re.MULTILINE
    if 's' in flags:
        regex_flags |= re.DOTALL
    
    try:
        result = re.sub(pattern, replacement, s, flags=regex_flags)
        return RDFLiteral(result)
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


def builtin_round(args) -> Optional[RDFNode]:
    """ROUND(numeric) - round to nearest integer."""
    if len(args) != 1 or args[0] is None:
        return None
    
    if isinstance(args[0], RDFLiteral) and is_numeric(args[0]):
        val = numeric_value(args[0])
        result = round(val)
        return RDFLiteral(int(result), datatype=XSD.integer)
    return None


def builtin_ceil(args) -> Optional[RDFNode]:
    """CEIL(numeric) - ceiling (round up)."""
    if len(args) != 1 or args[0] is None:
        return None
    
    if isinstance(args[0], RDFLiteral) and is_numeric(args[0]):
        import math
        val = numeric_value(args[0])
        result = math.ceil(val)
        return RDFLiteral(int(result), datatype=XSD.integer)
    return None


def builtin_floor(args) -> Optional[RDFNode]:
    """FLOOR(numeric) - floor (round down)."""
    if len(args) != 1 or args[0] is None:
        return None
    
    if isinstance(args[0], RDFLiteral) and is_numeric(args[0]):
        import math
        val = numeric_value(args[0])
        result = math.floor(val)
        return RDFLiteral(int(result), datatype=XSD.integer)
    return None


def builtin_rand(args) -> Optional[RDFNode]:
    """RAND() - random number between 0 and 1."""
    import random
    return RDFLiteral(random.random(), datatype=XSD.double)


def builtin_now(args) -> Optional[RDFNode]:
    """NOW() - current datetime."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return RDFLiteral(now.isoformat(), datatype=XSD.dateTime)


def builtin_year(args) -> Optional[RDFNode]:
    """YEAR(datetime) - extract year."""
    # Simplified implementation
    if len(args) != 1 or args[0] is None:
        return None
    # TODO: Parse datetime and extract year
    return None


def builtin_month(args) -> Optional[RDFNode]:
    """MONTH(datetime) - extract month."""
    # Simplified implementation
    return None


def builtin_day(args) -> Optional[RDFNode]:
    """DAY(datetime) - extract day."""
    # Simplified implementation
    return None


def builtin_hours(args) -> Optional[RDFNode]:
    """HOURS(datetime) - extract hours."""
    # Simplified implementation
    return None


def builtin_minutes(args) -> Optional[RDFNode]:
    """MINUTES(datetime) - extract minutes."""
    # Simplified implementation
    return None


def builtin_seconds(args) -> Optional[RDFNode]:
    """SECONDS(datetime) - extract seconds."""
    # Simplified implementation
    return None


def builtin_timezone(args) -> Optional[RDFNode]:
    """TIMEZONE(datetime) - extract timezone."""
    # Simplified implementation
    return None


def builtin_tz(args) -> Optional[RDFNode]:
    """TZ(datetime) - timezone as string."""
    # Simplified implementation
    return None


def builtin_md5(args) -> Optional[RDFNode]:
    """MD5(string) - MD5 hash."""
    if len(args) != 1 or args[0] is None:
        return None
    
    import hashlib
    s = str(args[0])
    result = hashlib.md5(s.encode()).hexdigest()
    return RDFLiteral(result)


def builtin_sha1(args) -> Optional[RDFNode]:
    """SHA1(string) - SHA1 hash."""
    if len(args) != 1 or args[0] is None:
        return None
    
    import hashlib
    s = str(args[0])
    result = hashlib.sha1(s.encode()).hexdigest()
    return RDFLiteral(result)


def builtin_sha256(args) -> Optional[RDFNode]:
    """SHA256(string) - SHA256 hash."""
    if len(args) != 1 or args[0] is None:
        return None
    
    import hashlib
    s = str(args[0])
    result = hashlib.sha256(s.encode()).hexdigest()
    return RDFLiteral(result)


def builtin_sha384(args) -> Optional[RDFNode]:
    """SHA384(string) - SHA384 hash."""
    if len(args) != 1 or args[0] is None:
        return None
    
    import hashlib
    s = str(args[0])
    result = hashlib.sha384(s.encode()).hexdigest()
    return RDFLiteral(result)


def builtin_sha512(args) -> Optional[RDFNode]:
    """SHA512(string) - SHA512 hash."""
    if len(args) != 1 or args[0] is None:
        return None
    
    import hashlib
    s = str(args[0])
    result = hashlib.sha512(s.encode()).hexdigest()
    return RDFLiteral(result)


def builtin_isiri(args) -> Optional[RDFNode]:
    """ISIRI(term) - test if term is IRI."""
    if len(args) != 1 or args[0] is None:
        return RDFLiteral(False)
    return RDFLiteral(isinstance(args[0], URIRef))


def builtin_isblank(args) -> Optional[RDFNode]:
    """ISBLANK(term) - test if term is blank node."""
    if len(args) != 1 or args[0] is None:
        return RDFLiteral(False)
    return RDFLiteral(isinstance(args[0], BNode))


def builtin_isliteral(args) -> Optional[RDFNode]:
    """ISLITERAL(term) - test if term is literal."""
    if len(args) != 1 or args[0] is None:
        return RDFLiteral(False)
    return RDFLiteral(isinstance(args[0], RDFLiteral))


def builtin_isnumeric(args) -> Optional[RDFNode]:
    """ISNUMERIC(term) - test if term is numeric literal."""
    if len(args) != 1 or args[0] is None:
        return RDFLiteral(False)
    return RDFLiteral(isinstance(args[0], RDFLiteral) and is_numeric(args[0]))


def builtin_regex(args) -> Optional[RDFNode]:
    """REGEX(text, pattern[, flags]) - regex test."""
    if len(args) < 2 or args[0] is None or args[1] is None:
        return None
    
    text = str(args[0])
    pattern = str(args[1])
    flags = str(args[2]) if len(args) >= 3 and args[2] is not None else ""
    
    regex_flags = 0
    if 'i' in flags:
        regex_flags |= re.IGNORECASE
    if 'm' in flags:
        regex_flags |= re.MULTILINE
    if 's' in flags:
        regex_flags |= re.DOTALL
    
    try:
        match = re.search(pattern, text, flags=regex_flags)
        return RDFLiteral(match is not None)
    except:
        return None


# ===========================================================================
# Helper functions
# ===========================================================================

def is_numeric(term: RDFLiteral) -> bool:
    """Check if a literal is numeric."""
    if not isinstance(term, RDFLiteral):
        return False
    
    return term.datatype in (
        XSD.integer, XSD.decimal, XSD.double, XSD.float,
        XSD.int, XSD.long, XSD.short, XSD.byte,
        XSD.nonNegativeInteger, XSD.positiveInteger,
        XSD.unsignedLong, XSD.unsignedInt, XSD.unsignedShort, XSD.unsignedByte,
        XSD.nonPositiveInteger, XSD.negativeInteger,
    )


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
        
        # String comparison
        if (term1.datatype == term2.datatype or 
            (term1.datatype in (None, XSD.string) and term2.datatype in (None, XSD.string))):
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


def numeric_add(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Add two numeric literals."""
    if not (isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral)):
        return None
    if not (is_numeric(term1) and is_numeric(term2)):
        return None
    
    val1 = numeric_value(term1)
    val2 = numeric_value(term2)
    result = val1 + val2
    
    # Result datatype promotion
    if term1.datatype == XSD.double or term2.datatype == XSD.double:
        return RDFLiteral(result, datatype=XSD.double)
    elif term1.datatype == XSD.float or term2.datatype == XSD.float:
        return RDFLiteral(result, datatype=XSD.float)
    elif term1.datatype == XSD.decimal or term2.datatype == XSD.decimal:
        return RDFLiteral(result, datatype=XSD.decimal)
    else:
        return RDFLiteral(int(result), datatype=XSD.integer)


def numeric_subtract(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Subtract two numeric literals."""
    if not (isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral)):
        return None
    if not (is_numeric(term1) and is_numeric(term2)):
        return None
    
    val1 = numeric_value(term1)
    val2 = numeric_value(term2)
    result = val1 - val2
    
    if term1.datatype == XSD.double or term2.datatype == XSD.double:
        return RDFLiteral(result, datatype=XSD.double)
    elif term1.datatype == XSD.float or term2.datatype == XSD.float:
        return RDFLiteral(result, datatype=XSD.float)
    elif term1.datatype == XSD.decimal or term2.datatype == XSD.decimal:
        return RDFLiteral(result, datatype=XSD.decimal)
    else:
        return RDFLiteral(int(result), datatype=XSD.integer)


def numeric_multiply(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Multiply two numeric literals."""
    if not (isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral)):
        return None
    if not (is_numeric(term1) and is_numeric(term2)):
        return None
    
    val1 = numeric_value(term1)
    val2 = numeric_value(term2)
    result = val1 * val2
    
    if term1.datatype == XSD.double or term2.datatype == XSD.double:
        return RDFLiteral(result, datatype=XSD.double)
    elif term1.datatype == XSD.float or term2.datatype == XSD.float:
        return RDFLiteral(result, datatype=XSD.float)
    elif term1.datatype == XSD.decimal or term2.datatype == XSD.decimal:
        return RDFLiteral(result, datatype=XSD.decimal)
    else:
        return RDFLiteral(int(result), datatype=XSD.integer)


def numeric_divide(term1: RDFNode, term2: RDFNode) -> Optional[RDFNode]:
    """Divide two numeric literals."""
    if not (isinstance(term1, RDFLiteral) and isinstance(term2, RDFLiteral)):
        return None
    if not (is_numeric(term1) and is_numeric(term2)):
        return None
    
    val1 = numeric_value(term1)
    val2 = numeric_value(term2)
    
    if val2 == 0:
        return None  # Division by zero
    
    result = val1 / val2
    
    # Division always produces decimal or double
    if term1.datatype == XSD.double or term2.datatype == XSD.double:
        return RDFLiteral(result, datatype=XSD.double)
    else:
        return RDFLiteral(result, datatype=XSD.decimal)


def numeric_negate(term: RDFNode) -> Optional[RDFNode]:
    """Negate a numeric literal."""
    if not isinstance(term, RDFLiteral) or not is_numeric(term):
        return None
    
    val = numeric_value(term)
    result = -val
    
    return RDFLiteral(result, datatype=term.datatype)
