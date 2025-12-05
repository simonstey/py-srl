"""
Lark transformer to convert parse tree to AST nodes.

This transformer implements the mapping from Lark parse trees to
the AST nodes defined in srl.ast.nodes, following the abstract syntax
from Section 3 of the SHACL 1.2 Rules specification.
"""

from lark import Transformer, Token
from typing import Dict

from ..ast.nodes import (
    # Core structures
    RuleSet,
    Prologue,
    Rule,
    RuleHead,
    RuleBody,
    DataBlock,
    # RDF Terms
    Variable,
    IRI,
    Literal,
    BlankNode,
    # Property Paths
    InversePath,
    PathSequence,
    PathAlternative,
    # Body elements
    TriplePattern,
    TripleTemplate,
    ConditionExpression,
    NegationElement,
    Assignment,
    Annotation,
    # Declarations
    TransitiveDeclaration,
    SymmetricDeclaration,
    InverseDeclaration,
    # Expressions
    BinaryOp,
    UnaryOp,
    FunctionCall,
    BuiltInCall,
    BinaryOperator,
    UnaryOperator,
)


# Standard well-known prefixes
STANDARD_PREFIXES: Dict[str, str] = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "sh": "http://www.w3.org/ns/shacl#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}


class SRLTransformer(Transformer):
    """
    Transform Lark parse tree into SRL AST.

    Methods are named after grammar rules and are called automatically
    by Lark when transforming the parse tree.
    """

    def __init__(self):
        """Initialize transformer with prefix tracking."""
        super().__init__()
        # Start with standard well-known prefixes
        self._prefixes: Dict[str, str] = dict(STANDARD_PREFIXES)

    # ========================================================================
    # Top-level structures
    # ========================================================================

    def rule_set(self, items):
        """[1] RuleSet ::= ( Prologue ( Rule | Data ) )*"""
        prologue = Prologue()
        rules = []
        data_blocks = []
        declarations = []

        for item in items:
            if isinstance(item, Prologue):
                prologue = item
            elif isinstance(item, Rule):
                rules.append(item)
            elif isinstance(item, DataBlock):
                data_blocks.append(item)
            elif isinstance(item, (TransitiveDeclaration, SymmetricDeclaration, InverseDeclaration)):
                declarations.append(item)

        return RuleSet(prologue=prologue, rules=rules, data_blocks=data_blocks, declarations=declarations)

    def prologue(self, items):
        """[2] Prologue ::= ( BaseDecl | PrefixDecl | VersionDecl | ImportsDecl )*"""
        prologue = Prologue()

        for item in items:
            if isinstance(item, tuple):
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

        return prologue

    def base_decl(self, items):
        """[3] BaseDecl ::= 'BASE' IRIREF"""
        return ("base", items[0])

    def prefix_decl(self, items):
        """[4] PrefixDecl ::= 'PREFIX' PNAME_NS IRIREF"""
        # items[0] is PNAME_NS (e.g., 'ex:'), items[1] is IRIREF (already IRI object)
        prefix_token = str(items[0]).rstrip(":")
        iri = items[1]
        iri_str = iri.value if isinstance(iri, IRI) else str(iri)

        # Store prefix in transformer state for later resolution
        self._prefixes[prefix_token] = iri_str

        return ("prefix", (prefix_token, IRI(iri_str)))

    def version_decl(self, items):
        """[5] VersionDecl ::= 'VERSION' VersionSpecifier"""
        return ("version", items[0])

    def imports_decl(self, items):
        """[7] ImportsDecl ::= 'IMPORTS' iri"""
        return ("imports", items[0])

    # ========================================================================
    # Rules
    # ========================================================================

    def rule(self, items):
        """[8] Rule ::= Rule1 | Rule2 | Rule3 | Declaration"""
        # Return the transformed rule or declaration
        return items[0] if items else None

    def declaration(self, items):
        """[12] Declaration ::= transitive_decl | symmetric_decl | inverse_decl"""
        # Just pass through the specific declaration type
        return items[0] if items else None

    def transitive_decl(self, items):
        """Handle TRANSITIVE declaration explicitly."""
        return TransitiveDeclaration(predicate=items[0])

    def symmetric_decl(self, items):
        """Handle SYMMETRIC declaration explicitly."""
        return SymmetricDeclaration(predicate=items[0])

    def inverse_decl(self, items):
        """Handle INVERSE declaration explicitly."""
        return InverseDeclaration(predicate1=items[0], predicate2=items[1])

    def rule1(self, items):
        """[9] Rule1 ::= 'RULE' HeadTemplate 'WHERE' BodyPattern"""
        head = items[0]
        body = items[1]
        return Rule(head=head, body=body)

    def rule2(self, items):
        """[10] Rule2 ::= 'IF' BodyPattern 'THEN' HeadTemplate"""
        body = items[0]
        head = items[1]
        return Rule(head=head, body=body)

    def rule3(self, items):
        """[11] Rule3 ::= HeadTemplate ':-' BodyPattern"""
        head = items[0]
        body = items[1]
        return Rule(head=head, body=body)

    def head_template(self, items):
        """[14] HeadTemplate ::= TriplesTemplateBlock"""
        templates = items[0] if items else []
        return RuleHead(templates=templates)

    def body_pattern(self, items):
        """[15] BodyPattern ::= '{' BodyPattern1 '}'"""
        elements = items[0] if items else []
        return RuleBody(elements=elements)

    def body_pattern1(self, items):
        """[16] BodyPattern1 ::= BodyTriplesBlock? ( BodyNotTriples BodyTriplesBlock? )*"""
        elements = []
        for item in items:
            if isinstance(item, list):
                elements.extend(item)
            else:
                elements.append(item)
        return elements

    def data(self, items):
        """[13] Data ::= 'DATA' TriplesTemplateBlock"""
        triples = items[0] if items else []
        return DataBlock(triples=triples)

    # ========================================================================
    # Body elements
    # ========================================================================

    def body_not_triples(self, items):
        """[17] BodyNotTriples ::= Filter | Negation | Assignment"""
        # Just return the single element
        return items[0]

    def filter(self, items):
        """[29] Filter ::= 'FILTER' Constraint"""
        expr = items[0]
        return ConditionExpression(expression=expr)

    def constraint(self, items):
        """[30] Constraint ::= BrackettedExpression | BuiltInCall | FunctionCall"""
        # Just return the expression
        return items[0]

    def negation(self, items):
        """[19] Negation ::= 'NOT' '{' BodyBasic '}'"""
        body_patterns = items[0] if items else []
        return NegationElement(body_patterns=body_patterns)

    def assignment(self, items):
        """[26] Assignment ::= 'BIND' '(' Expression 'AS' Var ')'"""
        expr = items[0]
        var = items[1]
        return Assignment(variable=var, expression=expr)

    def body_triples_block(self, items):
        """[18] BodyTriplesBlock ::= TriplesBlock"""
        # Returns list of triple patterns
        return items[0] if items else []

    def triples_block(self, items):
        """[23] TriplesBlock ::= TriplesSameSubjectPath ( '.' TriplesBlock? )?"""
        patterns = []
        for item in items:
            if isinstance(item, list):
                patterns.extend(item)
            elif isinstance(item, TriplePattern):
                patterns.append(item)
        return patterns

    def triples_template_block(self, items):
        """[21] TriplesTemplateBlock ::= '{' TriplesTemplate? '}'"""
        return items[0] if items else []

    def triples_template(self, items):
        """[22] TriplesTemplate ::= TriplesSameSubject ( '.' TriplesTemplate? )?"""
        templates = []
        for item in items:
            if isinstance(item, list):
                templates.extend(item)
            elif isinstance(item, TripleTemplate):
                templates.append(item)
        return templates

    # ========================================================================
    # Triple patterns and templates
    # ========================================================================

    def triples_same_subject(self, items):
        """[34] TriplesSameSubject ::= VarOrTerm PropertyListNotEmpty | ..."""
        # Simplified: assumes subject + property-object pairs
        subject = items[0]
        property_list = items[1] if len(items) > 1 else []

        templates = []
        for pred, obj in property_list:
            templates.append(TripleTemplate(subject=subject, predicate=pred, object=obj))

        return templates

    def triples_same_subject_path(self, items):
        """[40] TriplesSameSubjectPath ::= VarOrTerm PropertyListPathNotEmpty | ..."""
        # Simplified: assumes subject + property-object pairs
        subject = items[0]
        property_list = items[1] if len(items) > 1 else []

        patterns = []
        for pred, obj in property_list:
            patterns.append(TriplePattern(subject=subject, predicate=pred, object=obj))

        return patterns

    def property_list_not_empty(self, items):
        """[36] PropertyListNotEmpty ::= Verb ObjectList ( ';' ( Verb ObjectList )? )*"""
        # Returns list of (predicate, object) pairs
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

    def property_list_path_not_empty(self, items):
        """[42] PropertyListPathNotEmpty ::= ( VerbPath | VerbSimple ) ObjectListPath ..."""
        # Similar to property_list_not_empty
        return self.property_list_not_empty(items)

    def object_list(self, items):
        """[38] ObjectList ::= Object ( ',' Object )*"""
        return items

    def object_list_path(self, items):
        """[45] ObjectListPath ::= ObjectPath ( ',' ObjectPath )*"""
        return items

    def verb(self, items):
        """[37] Verb ::= VarOrIri | 'a'"""
        if len(items) == 1 and isinstance(items[0], str) and items[0] == "a":
            return IRI("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        return items[0]

    def verb_path(self, items):
        """[43] VerbPath ::= Path"""
        return items[0] if items else None

    def verb_simple(self, items):
        """[44] VerbSimple ::= Var"""
        return items[0] if items else None

    def object(self, items):
        """[39] Object ::= GraphNode Annotation"""
        # Return just the graph node, ignore annotation for now
        return items[0] if items else None

    def object_path(self, items):
        """[46] ObjectPath ::= GraphNodePath AnnotationPath"""
        # Return just the graph node, ignore annotation for now
        return items[0] if items else None

    def graph_node(self, items):
        """[52] GraphNode ::= VarOrTerm | TriplesNode"""
        return items[0] if items else None

    def graph_node_path(self, items):
        """[53] GraphNodePath ::= VarOrTerm | TriplesNodePath"""
        return items[0] if items else None

    def annotation(self, items):
        """[60] Annotation ::= ( Reifier | AnnotationBlock )*"""
        if not items:
            return None
        # Collect all annotation properties
        properties = []
        for item in items:
            if isinstance(item, list):
                properties.extend(item)
        if properties:
            return Annotation(properties=properties)
        return None

    def annotation_path(self, items):
        """[58] AnnotationPath ::= ( Reifier | AnnotationBlockPath )*"""
        if not items:
            return None
        # Collect all annotation properties
        properties = []
        for item in items:
            if isinstance(item, list):
                properties.extend(item)
        if properties:
            return Annotation(properties=properties)
        return None

    def annotation_block(self, items):
        """[61] AnnotationBlock ::= '{|' PropertyListNotEmpty '|}'"""
        # items[0] is the property list - list of (predicate, object) tuples
        return items[0] if items else []

    def annotation_block_path(self, items):
        """[59] AnnotationBlockPath ::= '{|' PropertyListPathNotEmpty '|}'"""
        # items[0] is the property list - list of (predicate, object) tuples
        return items[0] if items else []

    def path(self, items):
        """[47] Path ::= PathSequence ( '|' PathSequence )*"""
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        # Multiple path sequences = alternative paths
        return PathAlternative(alternatives=items)

    def path_sequence(self, items):
        """[48] PathSequence ::= PathEltOrInverse ( '/' PathEltOrInverse )*"""
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        # Multiple elements = sequence path
        return PathSequence(elements=items)

    def path_elt_or_inverse(self, items):
        """[49] PathEltOrInverse ::= PathElt | '^' PathElt"""
        if not items:
            return None
        # Check if this is an inverse path (starts with ^)
        if len(items) == 2:
            # First item might be the ^ token
            first = items[0]
            if isinstance(first, Token) and str(first) == "^":
                return InversePath(path=items[1])
        # Not inverse, return the path element
        return items[0]

    def path_elt(self, items):
        """[50] PathElt ::= PathPrimary PathMod?"""
        return items[0] if items else None

    def path_primary(self, items):
        """[51] PathPrimary ::= iri | 'a' | ..."""
        return items[0] if items else None

    def prefixed_name(self, items):
        """[100] PrefixedName ::= PNAME_LN | PNAME_NS"""
        token = str(items[0])

        if ":" in token:
            prefix, local = token.split(":", 1)

            # Look up prefix in transformer state
            if prefix in self._prefixes:
                return IRI(self._prefixes[prefix] + local)

            # Unknown prefix - return as unresolved for error handling
            # Could raise an error here, but keeping lenient for partial parsing
            return IRI(f"{prefix}:{local}")

        return IRI(token)

    # ========================================================================
    # Terminals and basic types
    # ========================================================================

    def var(self, items):
        """[75] Var ::= VAR1 | VAR2"""
        token = items[0]
        # Remove ? or $ prefix
        name = str(token)[1:]
        return Variable(name=name)

    def iri(self, items):
        """[99] iri ::= IRIREF | PrefixedName"""
        if isinstance(items[0], IRI):
            return items[0]
        elif isinstance(items[0], Token):
            token = str(items[0])
            if token.startswith("<") and token.endswith(">"):
                return IRI(token[1:-1])
            # Handle as prefixed name if it contains a colon
            if ":" in token:
                prefix, local = token.split(":", 1)
                if prefix in self._prefixes:
                    return IRI(self._prefixes[prefix] + local)
            return IRI(token)
        return items[0]

    def rdf_literal(self, items):
        """[92] RDFLiteral ::= String ( LANG_DIR | '^^' iri )?"""
        value = items[0]

        if len(items) > 1:
            modifier = items[1]
            if isinstance(modifier, str) and modifier.startswith("@"):
                return Literal(value=value, language=modifier[1:])
            elif isinstance(modifier, IRI):
                return Literal(value=value, datatype=modifier)

        return Literal(value=value)

    def string(self, items):
        """[98] String ::= STRING_LITERAL1 | STRING_LITERAL2 | ..."""
        token = str(items[0])
        # Remove quotes
        if token.startswith('"""') or token.startswith("'''"):
            return token[3:-3]
        else:
            return token[1:-1]

    def numeric_literal_unsigned(self, items):
        """[94] NumericLiteralUnsigned ::= INTEGER | DECIMAL | DOUBLE"""
        value = str(items[0])
        # Determine datatype based on format
        if "e" in value.lower():
            datatype = IRI("http://www.w3.org/2001/XMLSchema#double")
        elif "." in value:
            datatype = IRI("http://www.w3.org/2001/XMLSchema#decimal")
        else:
            datatype = IRI("http://www.w3.org/2001/XMLSchema#integer")

        return Literal(value=value, datatype=datatype)

    def numeric_literal(self, items):
        """[93] NumericLiteral ::= NumericLiteralUnsigned | ..."""
        # Just return the unsigned literal (items[0] is already transformed)
        return items[0]

    def boolean_literal(self, items):
        """[97] BooleanLiteral ::= 'true' | 'false'"""
        if items:
            value = str(items[0]).lower()
        else:
            value = "true"
        return Literal(value=value, datatype=IRI("http://www.w3.org/2001/XMLSchema#boolean"))

    def TRUE(self, token):
        return token

    def FALSE(self, token):
        return token

    def blank_node(self, items):
        """[101] BlankNode ::= BLANK_NODE_LABEL | ANON"""
        token = str(items[0])
        if token.startswith("_:"):
            return BlankNode(label=token[2:])
        else:
            # Generate unique label for anonymous blank node
            import uuid

            return BlankNode(label=f"anon_{uuid.uuid4().hex[:8]}")

    # ========================================================================
    # Expressions
    # ========================================================================

    def expression(self, items):
        """[76] Expression ::= ConditionalOrExpression"""
        return items[0]

    def conditional_or_expression(self, items):
        """[77] ConditionalOrExpression ::= ConditionalAndExpression ( '||' ConditionalAndExpression )*"""
        if len(items) == 1:
            return items[0]

        result = items[0]
        for i in range(1, len(items)):
            result = BinaryOp(operator=BinaryOperator.OR, left=result, right=items[i])
        return result

    def conditional_and_expression(self, items):
        """[78] ConditionalAndExpression ::= ValueLogical ( '&&' ValueLogical )*"""
        if len(items) == 1:
            return items[0]

        result = items[0]
        for i in range(1, len(items)):
            result = BinaryOp(operator=BinaryOperator.AND, left=result, right=items[i])
        return result

    def value_logical(self, items):
        """[79] ValueLogical ::= RelationalExpression"""
        return items[0]

    def relational_expression(self, items):
        """[80] RelationalExpression ::= NumericExpression ( '=' NumericExpression | ... )?"""
        if len(items) == 1:
            return items[0]

        if len(items) < 3:
            # Missing operator - shouldn't happen now with terminals
            return items[0]

        left = items[0]
        op_token = str(items[1])
        right = items[2]

        op_map = {
            "=": BinaryOperator.EQ,
            "!=": BinaryOperator.NE,
            "<": BinaryOperator.LT,
            ">": BinaryOperator.GT,
            "<=": BinaryOperator.LE,
            ">=": BinaryOperator.GE,
        }

        operator = op_map.get(op_token)
        return BinaryOp(operator=operator, left=left, right=right)

    def numeric_expression(self, items):
        """[81] NumericExpression ::= AdditiveExpression"""
        return items[0]

    def additive_expression(self, items):
        """[82] AdditiveExpression ::= MultiplicativeExpression ( '+' | '-' ... )*"""
        if len(items) == 1:
            return items[0]

        result = items[0]
        i = 1
        while i < len(items):
            op_token = str(items[i])
            i += 1
            if i < len(items):
                right = items[i]
                i += 1
                operator = BinaryOperator.ADD if op_token == "+" else BinaryOperator.SUB
                result = BinaryOp(operator=operator, left=result, right=right)

        return result

    def multiplicative_expression(self, items):
        """[83] MultiplicativeExpression ::= UnaryExpression ( '*' | '/' UnaryExpression )*"""
        if len(items) == 1:
            return items[0]

        result = items[0]
        i = 1
        while i < len(items):
            op_token = str(items[i])
            i += 1
            if i < len(items):
                right = items[i]
                i += 1
                operator = BinaryOperator.MUL if op_token == "*" else BinaryOperator.DIV
                result = BinaryOp(operator=operator, left=result, right=right)

        return result

    def unary_expression(self, items):
        """[84] UnaryExpression ::= '!' PrimaryExpression | '+' | '-' | PrimaryExpression"""
        if len(items) == 1:
            return items[0]

        op_token = str(items[0])
        operand = items[1]

        op_map = {
            "!": UnaryOperator.NOT,
            "+": UnaryOperator.PLUS,
            "-": UnaryOperator.MINUS,
        }

        operator = op_map.get(op_token)
        return UnaryOp(operator=operator, operand=operand)

    def primary_expression(self, items):
        """[85] PrimaryExpression ::= BrackettedExpression | BuiltInCall | ..."""
        return items[0]

    def bracketted_expression(self, items):
        """[89] BrackettedExpression ::= '(' Expression ')'"""
        return items[0]

    def built_in_call(self, items):
        """[90] BuiltInCall ::= builtin_str | builtin_lang | ..."""
        # Items contains the result from one of the specific builtin rules
        return items[0]

    def builtin_str(self, items):
        return BuiltInCall(function_name="STR", arguments=items)

    def builtin_lang(self, items):
        return BuiltInCall(function_name="LANG", arguments=items)

    def builtin_langmatches(self, items):
        return BuiltInCall(function_name="LANGMATCHES", arguments=items)

    def builtin_langdir(self, items):
        return BuiltInCall(function_name="LANGDIR", arguments=items)

    def builtin_datatype(self, items):
        return BuiltInCall(function_name="DATATYPE", arguments=items)

    def builtin_bound(self, items):
        return BuiltInCall(function_name="BOUND", arguments=items)

    def builtin_iri(self, items):
        return BuiltInCall(function_name="IRI", arguments=items)

    def builtin_uri(self, items):
        return BuiltInCall(function_name="URI", arguments=items)

    def builtin_bnode(self, items):
        return BuiltInCall(function_name="BNODE", arguments=items)

    def builtin_concat(self, items):
        return BuiltInCall(function_name="CONCAT", arguments=items)
    
    def builtin_rand(self, items):
        return BuiltInCall(function_name="RAND", arguments=[])
    
    def builtin_abs(self, items):
        return BuiltInCall(function_name="ABS", arguments=items)
    
    def builtin_ceil(self, items):
        return BuiltInCall(function_name="CEIL", arguments=items)
    
    def builtin_floor(self, items):
        return BuiltInCall(function_name="FLOOR", arguments=items)
    
    def builtin_round(self, items):
        return BuiltInCall(function_name="ROUND", arguments=items)
    
    def builtin_substr(self, items):
        return BuiltInCall(function_name="SUBSTR", arguments=items)
    
    def builtin_strlen(self, items):
        return BuiltInCall(function_name="STRLEN", arguments=items)
    
    def builtin_replace(self, items):
        return BuiltInCall(function_name="REPLACE", arguments=items)
    
    def builtin_ucase(self, items):
        return BuiltInCall(function_name="UCASE", arguments=items)
    
    def builtin_lcase(self, items):
        return BuiltInCall(function_name="LCASE", arguments=items)
    
    def builtin_encode_for_uri(self, items):
        return BuiltInCall(function_name="ENCODE_FOR_URI", arguments=items)
    
    def builtin_contains(self, items):
        return BuiltInCall(function_name="CONTAINS", arguments=items)
    
    def builtin_strstarts(self, items):
        return BuiltInCall(function_name="STRSTARTS", arguments=items)
    
    def builtin_strends(self, items):
        return BuiltInCall(function_name="STRENDS", arguments=items)
    
    def builtin_strbefore(self, items):
        return BuiltInCall(function_name="STRBEFORE", arguments=items)
    
    def builtin_strafter(self, items):
        return BuiltInCall(function_name="STRAFTER", arguments=items)
    
    def builtin_year(self, items):
        return BuiltInCall(function_name="YEAR", arguments=items)
    
    def builtin_month(self, items):
        return BuiltInCall(function_name="MONTH", arguments=items)
    
    def builtin_day(self, items):
        return BuiltInCall(function_name="DAY", arguments=items)
    
    def builtin_hours(self, items):
        return BuiltInCall(function_name="HOURS", arguments=items)
    
    def builtin_minutes(self, items):
        return BuiltInCall(function_name="MINUTES", arguments=items)
    
    def builtin_seconds(self, items):
        return BuiltInCall(function_name="SECONDS", arguments=items)
    
    def builtin_timezone(self, items):
        return BuiltInCall(function_name="TIMEZONE", arguments=items)
    
    def builtin_tz(self, items):
        return BuiltInCall(function_name="TZ", arguments=items)
    
    def builtin_now(self, items):
        return BuiltInCall(function_name="NOW", arguments=[])
    
    def builtin_uuid(self, items):
        return BuiltInCall(function_name="UUID", arguments=[])
    
    def builtin_struuid(self, items):
        return BuiltInCall(function_name="STRUUID", arguments=[])
    
    def builtin_md5(self, items):
        return BuiltInCall(function_name="MD5", arguments=items)
    
    def builtin_sha1(self, items):
        return BuiltInCall(function_name="SHA1", arguments=items)
    
    def builtin_sha256(self, items):
        return BuiltInCall(function_name="SHA256", arguments=items)
    
    def builtin_sha384(self, items):
        return BuiltInCall(function_name="SHA384", arguments=items)
    
    def builtin_sha512(self, items):
        return BuiltInCall(function_name="SHA512", arguments=items)
    
    def builtin_coalesce(self, items):
        return BuiltInCall(function_name="COALESCE", arguments=items)
    
    def builtin_if(self, items):
        return BuiltInCall(function_name="IF", arguments=items)
    
    def builtin_strlang(self, items):
        return BuiltInCall(function_name="STRLANG", arguments=items)
    
    def builtin_strlangdir(self, items):
        return BuiltInCall(function_name="STRLANGDIR", arguments=items)
    
    def builtin_strdt(self, items):
        return BuiltInCall(function_name="STRDT", arguments=items)
    
    def builtin_sameterm(self, items):
        return BuiltInCall(function_name="sameTerm", arguments=items)
    
    def builtin_isiri(self, items):
        return BuiltInCall(function_name="isIRI", arguments=items)
    
    def builtin_isuri(self, items):
        return BuiltInCall(function_name="isURI", arguments=items)
    
    def builtin_isblank(self, items):
        return BuiltInCall(function_name="isBLANK", arguments=items)
    
    def builtin_isliteral(self, items):
        return BuiltInCall(function_name="isLITERAL", arguments=items)
    
    def builtin_isnumeric(self, items):
        return BuiltInCall(function_name="isNUMERIC", arguments=items)
    
    def builtin_haslang(self, items):
        return BuiltInCall(function_name="hasLANG", arguments=items)
    
    def builtin_haslangdir(self, items):
        return BuiltInCall(function_name="hasLANGDIR", arguments=items)
    
    def builtin_regex(self, items):
        return BuiltInCall(function_name="REGEX", arguments=items)
    
    def builtin_istriple(self, items):
        return BuiltInCall(function_name="isTRIPLE", arguments=items)
    
    def builtin_triple(self, items):
        return BuiltInCall(function_name="TRIPLE", arguments=items)
    
    def builtin_subject(self, items):
        return BuiltInCall(function_name="SUBJECT", arguments=items)
    
    def builtin_predicate(self, items):
        return BuiltInCall(function_name="PREDICATE", arguments=items)
    
    def builtin_object(self, items):
        return BuiltInCall(function_name="OBJECT", arguments=items)

    def function_call(self, items):
        """[31] FunctionCall ::= iri ArgList"""
        function_iri = items[0]
        args = items[1] if len(items) > 1 else []
        return FunctionCall(function=function_iri, arguments=args)

    def arg_list(self, items):
        """[32] ArgList ::= NIL | '(' Expression ( ',' Expression )* ')'"""
        return items if items else []

    # ========================================================================
    # Misc
    # ========================================================================

    def var_or_term(self, items):
        """[64] VarOrTerm ::= Var | iri | RDFLiteral | ..."""
        return items[0]

    def var_or_iri(self, items):
        """[74] VarOrIri ::= Var | iri"""
        return items[0]

    # Terminal pass-throughs
    def IRIREF(self, token):
        value = str(token)[1:-1]  # Remove < >
        return IRI(value)

    def VAR1(self, token):
        return token

    def VAR2(self, token):
        return token

    def INTEGER(self, token):
        return token

    def DECIMAL(self, token):
        return token

    def DOUBLE(self, token):
        return token

    def STRING_LITERAL1(self, token):
        return token

    def STRING_LITERAL2(self, token):
        return token

    def STRING_LITERAL_LONG1(self, token):
        return token

    def STRING_LITERAL_LONG2(self, token):
        return token
