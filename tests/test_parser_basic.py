"""
Basic test script to verify parser infrastructure.
"""

from src.srl.parser import SRLParser

# Simple SRL example
srl_text = """
PREFIX ex: <http://example.org/>

RULE {
    ?s ex:predicate ?o .
} WHERE {
    ?s ex:source ?o .
}
"""

def test_parser():
    parser = SRLParser()
    try:
        result = parser.parse(srl_text)
        print("Parse successful!")
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Parse failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parser()
