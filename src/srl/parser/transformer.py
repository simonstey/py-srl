"""
Lark transformer converting the parse tree to AST nodes.

Maps the Lark parse tree (grammar.lark) to the AST nodes in srl.ast.nodes,
following the Shape Rules abstract syntax and the 2026-07 grammar restructuring.
"""

import uuid
from typing import Dict

from lark import Transformer, Token

from ..ast.nodes import (
    RuleSet,
    Prologue,
    Rule,
    TargetedRule,
    RuleHead,
    RuleBody,
    DataBlock,
    Variable,
    IRI,
    Literal,
    BlankNode,
    TripleTerm,
    InversePath,
    PathSequence,
    TriplePattern,
    TripleTemplate,
    ConditionExpression,
    NegationElement,
    Assignment,
    TransitiveDeclaration,
    SymmetricDeclaration,
    InverseDeclaration,
    Declaration,
    BinaryOp,
    UnaryOp,
    FunctionCall,
    BuiltInCall,
    BinaryOperator,
    UnaryOperator,
)

RDF_TYPE = IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

STANDARD_PREFIXES: Dict[str, str] = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "sh": "http://www.w3.org/ns/shacl#",
    "srl": "http://www.w3.org/ns/shacl-rules#",
    "sparql": "http://www.w3.org/ns/sparql#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}


class SRLTransformer(Transformer):
    """Transform a Lark parse tree into an SRL AST."""

    def __init__(self, extensions: bool = False):
        super().__init__()
        self._prefixes: Dict[str, str] = dict(STANDARD_PREFIXES)
        self.extensions = extensions

    # ------------------------------------------------------------------
    # Top-level structure
    # ------------------------------------------------------------------

    def rule_set(self, items):
        """[1] RuleSet ::= (Prologue1 | Rule | Data)*"""
        prologue = Prologue()
        rules = []
        data_blocks = []
        declarations = []
        targeted_rules = []

        for item in items:
            if isinstance(item, tuple):
                self._apply_prologue_decl(prologue, item)
            elif isinstance(item, TargetedRule):
                targeted_rules.append(item)
            elif isinstance(item, Rule):
                rules.append(item)
            elif isinstance(item, DataBlock):
                data_blocks.append(item)
            elif isinstance(item, (TransitiveDeclaration, SymmetricDeclaration, InverseDeclaration)):
                declarations.append(item)

        return RuleSet(
            prologue=prologue,
            rules=rules,
            data_blocks=data_blocks,
            declarations=declarations,
            targeted_rules=targeted_rules,
        )

    @staticmethod
    def _apply_prologue_decl(prologue: Prologue, item) -> None:
        decl_type, value = item
        if decl_type == "base":
            prologue.base = value
        elif decl_type == "prefix":
            prefix, iri = value
            prologue.prefixes[prefix] = iri
        elif decl_type == "version":
            prologue.version = value
        elif decl_type == "imports":
            prologue.imports.append(value)

    def prologue1(self, items):
        """[5] Prologue1 ::= BaseDecl | PrefixDecl | VersionDecl | ImportsDecl"""
        return items[0]

    def base_decl(self, items):
        return ("base", items[0])

    def prefix_decl(self, items):
        prefix_token = str(items[0]).rstrip(":")
        iri = items[1]
        iri_str = iri.value if isinstance(iri, IRI) else str(iri)
        self._prefixes[prefix_token] = iri_str
        return ("prefix", (prefix_token, IRI(iri_str)))

    def version_decl(self, items):
        return ("version", items[0])

    def version_specifier(self, items):
        # STRING_LITERAL1 | STRING_LITERAL2 token -> stripped string value.
        token = str(items[0])
        return token[1:-1]

    def imports_decl(self, items):
        return ("imports", items[0])

    # ------------------------------------------------------------------
    # Rules and declarations
    # ------------------------------------------------------------------

    def rule(self, items):
        """[11] Rule ::= Rule1 | Rule2 | Declaration"""
        return items[0] if items else None

    def declaration(self, items):
        return items[0] if items else None

    def transitive_decl(self, items):
        return TransitiveDeclaration(predicate=items[0])

    def symmetric_decl(self, items):
        """[27] '(' iri ')' 'SYMMETRIC' (postfix)"""
        return SymmetricDeclaration(predicate=items[0])

    def inverse_decl(self, items):
        return InverseDeclaration(predicate1=items[0], predicate2=items[1])

    def for_clause(self, items):
        """Extension: 'FOR' Var 'IN' iri -> (marker, Variable, IRI)."""
        return ("for", items[0], items[1])

    @staticmethod
    def _is_for_clause(item) -> bool:
        return isinstance(item, tuple) and len(item) == 3 and item[0] == "for"

    def _extract_for_clause(self, items):
        """Split an optional for-clause tuple out of the item list.

        Returns (for_clause_or_None, remaining_items).
        """
        for_clause = None
        rest = []
        for item in items:
            if for_clause is None and self._is_for_clause(item):
                for_clause = item
            else:
                rest.append(item)
        return for_clause, rest

    def _wrap_targeted(self, rule: Rule, for_clause):
        """Wrap ``rule`` in a TargetedRule using the parsed for-clause."""
        _, focus_var, shape = for_clause
        return TargetedRule(
            rule=rule,
            focus_var=focus_var,
            shape=shape,
            direction="rule-to-shape",
        )

    def rule1(self, items):
        """[12] Rule1 ::= 'RULE' iri? for_clause? HeadTemplate 'WHERE' BodyPattern"""
        for_clause, rest = self._extract_for_clause(items)
        # Remaining items are [iri?, head, body].
        if len(rest) == 3:
            rule_iri, head, body = rest
        else:
            rule_iri, (head, body) = None, rest
        rule = Rule(head=head, body=body, iri=rule_iri)
        if for_clause is not None:
            return self._wrap_targeted(rule, for_clause)
        return rule

    def rule2(self, items):
        """[13] Rule2 ::= 'IF' BodyPattern 'THEN' iri? for_clause? HeadTemplate"""
        for_clause, rest = self._extract_for_clause(items)
        # Remaining items are [body, iri?, head].
        if len(rest) == 3:
            body, rule_iri, head = rest
        else:
            body, head = rest
            rule_iri = None
        rule = Rule(head=head, body=body, iri=rule_iri)
        if for_clause is not None:
            return self._wrap_targeted(rule, for_clause)
        return rule

    def head_template(self, items):
        """[15] HeadTemplate ::= '{' TriplesBlockTemplate? '}'"""
        templates = items[0] if items else []
        return RuleHead(templates=templates)

    def body_pattern(self, items):
        """[16] BodyPattern ::= '{' BodyTriplesBlock? (BodyNotTriples '.'? BodyTriplesBlock?)* '}'"""
        return RuleBody(elements=self._flatten(items))

    def data(self, items):
        """[14] Data ::= 'DATA' '{' DataTriplesBlock? '}'"""
        triples = items[0] if items else []
        return DataBlock(triples=triples)

    @staticmethod
    def _flatten(items):
        out = []
        for item in items:
            if item is None:
                continue
            if isinstance(item, list):
                out.extend(item)
            else:
                out.append(item)
        return out

    # ------------------------------------------------------------------
    # Body elements
    # ------------------------------------------------------------------

    def body_not_triples(self, items):
        return items[0]

    def body_basic_not_triples(self, items):
        return items[0]

    def body_basic(self, items):
        """[24] BodyBasic -> flat list of triple patterns + filters"""
        return self._flatten(items)

    def filter(self, items):
        return ConditionExpression(expression=items[0])

    def constraint(self, items):
        return items[0]

    def negation(self, items):
        """[23] Negation ::= 'NOT' '{' BodyBasic '}'"""
        body_patterns = items[0] if items else []
        return NegationElement(body_patterns=body_patterns)

    def assignment(self, items):
        """[26] Assignment ::= 'SET' '(' Var ':=' Expression ')'"""
        # Drop the ASSIGN_OP (':=') token if the lexer kept it in the tree.
        parts = [i for i in items if not (isinstance(i, Token) and i.type == "ASSIGN_OP")]
        var, expr = parts
        return Assignment(variable=var, expression=expr)

    # ------------------------------------------------------------------
    # Data family (ground triples: no variables, no paths)
    # ------------------------------------------------------------------

    def data_triples_block(self, items):
        return self._flatten_triples(items, TripleTemplate)

    def triples_same_subject_data(self, items):
        subject = items[0]
        property_list = items[1] if len(items) > 1 else []
        return [TripleTemplate(subject=subject, predicate=p, object=o) for p, o in property_list]

    def property_list_not_empty_data(self, items):
        return self._pairs(items)

    def verb_data(self, items):
        """[32] VerbData ::= iri | 'a'"""
        if items and isinstance(items[0], Token) and items[0].type == "TYPE_A":
            return RDF_TYPE
        return items[0]

    def object_list_data(self, items):
        return list(items)

    def object_data(self, items):
        return items[0]

    def graph_node_data(self, items):
        return items[0]

    def rdf_term_data(self, items):
        return self._nil_or_first(items)

    def triple_term_data(self, items):
        subj, verb, obj = items
        return TripleTerm(subject=subj, predicate=verb, object=obj)

    def triple_term_subject_data(self, items):
        return items[0]

    def triple_term_object_data(self, items):
        return items[0]

    # ------------------------------------------------------------------
    # Template family (rule heads: variables, no paths)
    # ------------------------------------------------------------------

    def triples_block_template(self, items):
        return self._flatten_triples(items, TripleTemplate)

    def triples_same_subject_template(self, items):
        subject = items[0]
        property_list = items[1] if len(items) > 1 else []
        return [TripleTemplate(subject=subject, predicate=p, object=o) for p, o in property_list]

    def property_list_not_empty_template(self, items):
        return self._pairs(items)

    def object_list_template(self, items):
        return list(items)

    def object_template(self, items):
        return items[0]

    def graph_node_template(self, items):
        return items[0]

    # ------------------------------------------------------------------
    # Pattern family (rule bodies: variables AND paths)
    # ------------------------------------------------------------------

    def body_triples_block(self, items):
        return items[0] if items else []

    def triples_block_pattern(self, items):
        return self._flatten_triples(items, TriplePattern)

    def triples_same_subject_pattern(self, items):
        subject = items[0]
        property_list = items[1] if len(items) > 1 else []
        return [TriplePattern(subject=subject, predicate=p, object=o) for p, o in property_list]

    def property_list_not_empty_pattern(self, items):
        return self._pairs(items)

    def object_list_pattern(self, items):
        return list(items)

    def object_pattern(self, items):
        return items[0]

    def graph_node_pattern(self, items):
        return items[0]

    def verb(self, items):
        """[86] Verb ::= VarOrIri | 'a'"""
        if items and isinstance(items[0], Token) and items[0].type == "TYPE_A":
            return RDF_TYPE
        return items[0]

    def verb_path(self, items):
        return items[0] if items else None

    def verb_simple(self, items):
        return items[0] if items else None

    # ------------------------------------------------------------------
    # Triple terms (shared template/pattern positions)
    # ------------------------------------------------------------------

    def triple_term(self, items):
        subj, verb, obj = items
        return TripleTerm(subject=subj, predicate=verb, object=obj)

    def triple_term_subject(self, items):
        return items[0]

    def triple_term_object(self, items):
        return items[0]

    def expr_triple_term(self, items):
        subj, verb, obj = items
        return TripleTerm(subject=subj, predicate=verb, object=obj)

    def expr_triple_term_subject(self, items):
        return items[0]

    def expr_triple_term_object(self, items):
        return items[0]

    # ------------------------------------------------------------------
    # Property paths
    # ------------------------------------------------------------------

    def path(self, items):
        return items[0]

    def path_sequence(self, items):
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        return PathSequence(elements=list(items))

    def path_elt_or_inverse(self, items):
        if len(items) == 2:
            first = items[0]
            if isinstance(first, Token) and str(first) == "^":
                return InversePath(path=items[1])
        return items[0]

    def path_elt(self, items):
        """[91] PathElt ::= iri | 'a' | '(' Path ')'"""
        if items and isinstance(items[0], Token) and items[0].type == "TYPE_A":
            return RDF_TYPE
        return items[0]

    # ------------------------------------------------------------------
    # Terms
    # ------------------------------------------------------------------

    def var_or_rdf_term(self, items):
        return self._nil_or_first(items)

    def var_or_iri(self, items):
        return items[0]

    def var(self, items):
        token = items[0]
        return Variable(name=str(token)[1:])  # strip ? or $

    def iri(self, items):
        if isinstance(items[0], IRI):
            return items[0]
        if isinstance(items[0], Token):
            token = str(items[0])
            if token.startswith("<") and token.endswith(">"):
                return IRI(token[1:-1])
            if ":" in token:
                prefix, local = token.split(":", 1)
                if prefix in self._prefixes:
                    return IRI(self._prefixes[prefix] + local)
            return IRI(token)
        return items[0]

    def prefixed_name(self, items):
        token = str(items[0])
        if ":" in token:
            prefix, local = token.split(":", 1)
            if prefix in self._prefixes:
                return IRI(self._prefixes[prefix] + local)
            return IRI(f"{prefix}:{local}")
        return IRI(token)

    def rdf_literal(self, items):
        value = items[0]
        if len(items) > 1:
            modifier = items[1]
            if isinstance(modifier, str) and modifier.startswith("@"):
                return Literal(value=value, language=modifier[1:])
            if isinstance(modifier, IRI):
                return Literal(value=value, datatype=modifier)
        return Literal(value=value)

    def string(self, items):
        token = str(items[0])
        if token.startswith('"""') or token.startswith("'''"):
            return token[3:-3]
        return token[1:-1]

    def numeric_literal(self, items):
        return items[0]

    def numeric_literal_unsigned(self, items):
        return self._numeric(str(items[0]))

    def numeric_literal_positive(self, items):
        return self._numeric(str(items[0]))

    def numeric_literal_negative(self, items):
        return self._numeric(str(items[0]))

    @staticmethod
    def _numeric(value: str) -> Literal:
        if "e" in value.lower():
            dt = "http://www.w3.org/2001/XMLSchema#double"
        elif "." in value:
            dt = "http://www.w3.org/2001/XMLSchema#decimal"
        else:
            dt = "http://www.w3.org/2001/XMLSchema#integer"
        return Literal(value=value, datatype=IRI(dt))

    def boolean_literal(self, items):
        value = str(items[0]).lower() if items else "true"
        return Literal(value=value, datatype=IRI("http://www.w3.org/2001/XMLSchema#boolean"))

    def blank_node(self, items):
        token = str(items[0])
        if token.startswith("_:"):
            return BlankNode(label=token[2:])
        return BlankNode(label=f"anon_{uuid.uuid4().hex[:8]}")

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def expression(self, items):
        return items[0]

    def conditional_or_expression(self, items):
        return self._left_assoc_named(items, BinaryOperator.OR)

    def conditional_and_expression(self, items):
        return self._left_assoc_named(items, BinaryOperator.AND)

    @staticmethod
    def _left_assoc_named(items, op):
        if len(items) == 1:
            return items[0]
        result = items[0]
        i = 1
        while i < len(items):
            result = BinaryOp(operator=op, left=result, right=items[i + 1])
            i += 2
        return result

    def value_logical(self, items):
        return items[0]

    def relational_expression(self, items):
        if len(items) == 1:
            return items[0]
        left = items[0]
        if len(items) == 3:
            op_token = str(items[1])
            right = items[2]
            if op_token.upper() == "IN":
                exprs = right if isinstance(right, list) else [right]
                return BuiltInCall(function_name="IN", arguments=[left, *exprs])
            op_map = {
                "=": BinaryOperator.EQ,
                "!=": BinaryOperator.NE,
                "<": BinaryOperator.LT,
                ">": BinaryOperator.GT,
                "<=": BinaryOperator.LE,
                ">=": BinaryOperator.GE,
            }
            operator = op_map.get(op_token)
            if operator is None:
                return left
            return BinaryOp(operator=operator, left=left, right=right)
        if len(items) == 4:
            not_kw = str(items[1]).upper()
            in_kw = str(items[2]).upper()
            expr_list = items[3]
            if not_kw == "NOT" and in_kw == "IN":
                exprs = expr_list if isinstance(expr_list, list) else [expr_list]
                in_call = BuiltInCall(function_name="IN", arguments=[left, *exprs])
                return UnaryOp(operator=UnaryOperator.NOT, operand=in_call)
        return left

    def numeric_expression(self, items):
        return items[0]

    def additive_expression(self, items):
        if len(items) == 1:
            return items[0]
        result = items[0]
        i = 1
        while i + 1 < len(items):
            op_token = str(items[i])
            right = items[i + 1]
            operator = BinaryOperator.ADD if op_token == "+" else BinaryOperator.SUB
            result = BinaryOp(operator=operator, left=result, right=right)
            i += 2
        return result

    def multiplicative_expression(self, items):
        if len(items) == 1:
            return items[0]
        result = items[0]
        i = 1
        while i + 1 < len(items):
            op_token = str(items[i])
            right = items[i + 1]
            operator = BinaryOperator.MUL if op_token == "*" else BinaryOperator.DIV
            result = BinaryOp(operator=operator, left=result, right=right)
            i += 2
        return result

    def unary_expression(self, items):
        if len(items) == 1:
            return items[0]
        op_token = str(items[0])
        operand = items[1]
        op_map = {
            "!": UnaryOperator.NOT,
            "+": UnaryOperator.PLUS,
            "-": UnaryOperator.MINUS,
        }
        return UnaryOp(operator=op_map.get(op_token), operand=operand)

    def primary_expression(self, items):
        return items[0]

    def bracketted_expression(self, items):
        return items[0]

    def built_in_call(self, items):
        return items[0]

    def iri_or_function(self, items):
        """[116] iriOrFunction ::= iri ArgList?"""
        function_iri = items[0]
        if len(items) > 1:
            args = items[1] if isinstance(items[1], list) else [items[1]]
            return FunctionCall(function=function_iri, arguments=args)
        return function_iri

    def function_call(self, items):
        """[20] FunctionCall ::= iri ArgList"""
        function_iri = items[0]
        args = items[1] if len(items) > 1 else []
        return FunctionCall(function=function_iri, arguments=args)

    def arg_list(self, items):
        if len(items) == 1 and isinstance(items[0], Token) and items[0].type == "NIL":
            return []
        return list(items) if items else []

    def expression_list(self, items):
        if len(items) == 1 and isinstance(items[0], Token) and items[0].type == "NIL":
            return []
        return list(items) if items else []

    # ------------------------------------------------------------------
    # Built-in function builders (spec [121] only)
    # ------------------------------------------------------------------

    def _bic(self, name, items):
        return BuiltInCall(function_name=name, arguments=list(items))

    def builtin_str(self, items):
        return self._bic("STR", items)

    def builtin_lang(self, items):
        return self._bic("LANG", items)

    def builtin_langmatches(self, items):
        return self._bic("LANGMATCHES", items)

    def builtin_langdir(self, items):
        return self._bic("LANGDIR", items)

    def builtin_datatype(self, items):
        return self._bic("DATATYPE", items)

    def builtin_iri(self, items):
        return self._bic("IRI", items)

    def builtin_uri(self, items):
        return self._bic("URI", items)

    def builtin_bnode(self, items):
        # BNODE ( expr ) | BNODE NIL  ->  drop NIL token to an empty arg list.
        args = [i for i in items if not (isinstance(i, Token) and i.type == "NIL")]
        return self._bic("BNODE", args)

    def builtin_abs(self, items):
        return self._bic("ABS", items)

    def builtin_ceil(self, items):
        return self._bic("CEIL", items)

    def builtin_floor(self, items):
        return self._bic("FLOOR", items)

    def builtin_round(self, items):
        return self._bic("ROUND", items)

    def builtin_concat(self, items):
        if len(items) == 1 and isinstance(items[0], list):
            items = items[0]
        return self._bic("CONCAT", items)

    def builtin_substr(self, items):
        return self._bic("SUBSTR", items)

    def builtin_strlen(self, items):
        return self._bic("STRLEN", items)

    def builtin_replace(self, items):
        return self._bic("REPLACE", items)

    def builtin_ucase(self, items):
        return self._bic("UCASE", items)

    def builtin_lcase(self, items):
        return self._bic("LCASE", items)

    def builtin_encode_for_uri(self, items):
        return self._bic("ENCODE_FOR_URI", items)

    def builtin_contains(self, items):
        return self._bic("CONTAINS", items)

    def builtin_strstarts(self, items):
        return self._bic("STRSTARTS", items)

    def builtin_strends(self, items):
        return self._bic("STRENDS", items)

    def builtin_strbefore(self, items):
        return self._bic("STRBEFORE", items)

    def builtin_strafter(self, items):
        return self._bic("STRAFTER", items)

    def builtin_year(self, items):
        return self._bic("YEAR", items)

    def builtin_month(self, items):
        return self._bic("MONTH", items)

    def builtin_day(self, items):
        return self._bic("DAY", items)

    def builtin_hours(self, items):
        return self._bic("HOURS", items)

    def builtin_minutes(self, items):
        return self._bic("MINUTES", items)

    def builtin_seconds(self, items):
        return self._bic("SECONDS", items)

    def builtin_timezone(self, items):
        return self._bic("TIMEZONE", items)

    def builtin_tz(self, items):
        return self._bic("TZ", items)

    def builtin_now(self, items):
        return self._bic("NOW", [])

    def builtin_uuid(self, items):
        return self._bic("UUID", [])

    def builtin_struuid(self, items):
        return self._bic("STRUUID", [])

    def builtin_if(self, items):
        return self._bic("IF", items)

    def builtin_strlang(self, items):
        return self._bic("STRLANG", items)

    def builtin_strlangdir(self, items):
        return self._bic("STRLANGDIR", items)

    def builtin_strdt(self, items):
        return self._bic("STRDT", items)

    def builtin_sameterm(self, items):
        return self._bic("sameTerm", items)

    def builtin_isiri(self, items):
        return self._bic("isIRI", items)

    def builtin_isuri(self, items):
        return self._bic("isURI", items)

    def builtin_isblank(self, items):
        return self._bic("isBLANK", items)

    def builtin_isliteral(self, items):
        return self._bic("isLITERAL", items)

    def builtin_isnumeric(self, items):
        return self._bic("isNUMERIC", items)

    def builtin_haslang(self, items):
        return self._bic("hasLANG", items)

    def builtin_haslangdir(self, items):
        return self._bic("hasLANGDIR", items)

    def builtin_regex(self, items):
        return self._bic("REGEX", items)

    def builtin_istriple(self, items):
        return self._bic("isTRIPLE", items)

    def builtin_triple(self, items):
        return self._bic("TRIPLE", items)

    def builtin_subject(self, items):
        return self._bic("SUBJECT", items)

    def builtin_predicate(self, items):
        return self._bic("PREDICATE", items)

    def builtin_object(self, items):
        return self._bic("OBJECT", items)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nil_or_first(items):
        if items and isinstance(items[0], Token) and items[0].type == "NIL":
            return IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#nil")
        return items[0]

    @staticmethod
    def _pairs(items):
        """Turn [verb, objlist, verb, objlist, ...] into (predicate, object) pairs."""
        pairs = []
        i = 0
        while i < len(items):
            verb = items[i]
            i += 1
            if i < len(items):
                objects = items[i]
                i += 1
                if isinstance(objects, list):
                    for obj in objects:
                        pairs.append((verb, obj))
                else:
                    pairs.append((verb, objects))
        return pairs

    @staticmethod
    def _flatten_triples(items, kind):
        triples = []
        for item in items:
            if isinstance(item, list):
                triples.extend(item)
            elif isinstance(item, kind):
                triples.append(item)
        return triples

    # ------------------------------------------------------------------
    # Terminal pass-throughs
    # ------------------------------------------------------------------

    def IRIREF(self, token):
        return IRI(str(token)[1:-1])

    def TRUE(self, token):
        return token

    def FALSE(self, token):
        return token
