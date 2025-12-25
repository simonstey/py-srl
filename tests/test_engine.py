"""
Test producing both results only and combined results & data
"""
from rdflib import Graph
import pytest
from src.srl.engine import RuleEngine
from src.srl.parser import SRLParser


def rule_engine(rule_text):
    return RuleEngine(SRLParser().parse(rule_text))


def test_results_without_data():
    r = """
        PREFIX : <http://example.org/>

        RULE {
            ?x :z ?y .
        } WHERE {
            ?x :b ?y .
        }
        """
    d = Graph().parse(
        data="""
            PREFIX : <http://example.org/>
            
            :a 
                :b :c ;
                :b :d ;
            .
            
            :e
                :b :f ;
                :g :h ;
            .
            
            :i :j :k .
            """
    )
    o = rule_engine(r).evaluate(d, inplace=False)  # results_only=False

    assert len(o) == 8  # 5 orig. + 3 inferred

    d = Graph().parse(
        data="""
            PREFIX : <http://example.org/>

            :a 
                :b :c ;
                :b :d ;
            .

            :e
                :b :f ;
                :g :h ;
            .

            :i :j :k .
            """
    )
    o2 = rule_engine(r).evaluate(d)  # inplace=True, results_only=False

    assert len(o2) == 8  # 5 orig. + 3 inferred

    with pytest.raises(ValueError):
        rule_engine(r).evaluate(d, inplace=True, results_only=True)

    d = Graph().parse(
        data="""
            PREFIX : <http://example.org/>

            :a 
                :b :c ;
                :b :d ;
            .

            :e
                :b :f ;
                :g :h ;
            .

            :i :j :k .
            """
    )
    o3 = rule_engine(r).evaluate(d, inplace=False, results_only=True)

    assert len(o3) == 3  # inferred only
