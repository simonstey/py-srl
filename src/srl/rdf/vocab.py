"""
SHACL Rules RDF vocabulary (SRL/RDF concrete syntax).

Namespace: http://www.w3.org/ns/shacl-rules#  (prefix ``srl:``)
Function terms use:  http://www.w3.org/ns/sparql#  (prefix ``sparql:``)

Term set follows rules-rdf-syntax/rdf-syntax-vocab.ttl and the all-features
example in the spec's #rdf-rules-syntax section.
"""

from rdflib import Namespace

# Namespaces
SRL = Namespace("http://www.w3.org/ns/shacl-rules#")
SPARQL = Namespace("http://www.w3.org/ns/sparql#")
SH = Namespace("http://www.w3.org/ns/shacl#")

# Classes
RuleSet = SRL.RuleSet
Rule = SRL.Rule
RuleElement = SRL.RuleElement
TriplePattern = SRL.TriplePattern
ConditionElement = SRL.ConditionElement
AssignmentElement = SRL.AssignmentElement
NegationElement = SRL.NegationElement

# Rule-set structure
rules = SRL.rules
data = SRL.data
head = SRL.head
body = SRL.body

# Triple positions
subject = SRL.subject
predicate = SRL.predicate
object_ = SRL.object  # ``object`` is a Python builtin; expose as object_

# Variables
varName = SRL.varName

# Rule elements
filter_ = SRL.filter  # ``filter`` is a Python builtin; expose as filter_
assign = SRL.assign
assignVar = SRL.assignVar
assignValue = SRL.assignValue
not_ = getattr(SRL, "not")  # srl:not

__all__ = [
    "SRL",
    "SPARQL",
    "SH",
    "RuleSet",
    "Rule",
    "RuleElement",
    "TriplePattern",
    "ConditionElement",
    "AssignmentElement",
    "NegationElement",
    "rules",
    "data",
    "head",
    "body",
    "subject",
    "predicate",
    "object_",
    "varName",
    "filter_",
    "assign",
    "assignVar",
    "assignValue",
    "not_",
]
