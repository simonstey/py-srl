#!/usr/bin/env python3
"""
Generate expected result files for W3C manifest-based test suite.

This script runs each .srl/.ttl pair through the SRL engine, computes
the inferred triples (result graph minus input graph), and writes
corresponding {test}-result.ttl files.

Usage:
    python scripts/generate_results.py [--test-dir PATH] [--overwrite]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from rdflib import Graph

# Add src to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from srl.parser import SRLParser
from srl.engine import RuleEngine
from srl.engine.stratification import StratificationError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def find_test_pairs(test_dir: Path) -> list[tuple[Path, Path]]:
    """
    Find all .srl/.ttl test pairs in the test directory.
    
    Returns:
        List of (srl_path, ttl_path) tuples
    """
    pairs = []
    
    for srl_path in test_dir.rglob("*.srl"):
        # Look for corresponding .ttl file (same name, different extension)
        ttl_path = srl_path.with_suffix(".ttl")
        if ttl_path.exists():
            pairs.append((srl_path, ttl_path))
        else:
            logger.warning(f"No .ttl file found for {srl_path}")
    
    return sorted(pairs)


def generate_result_file(
    srl_path: Path,
    ttl_path: Path,
    overwrite: bool = False
) -> Optional[Path]:
    """
    Generate a result file for a single test case.
    
    Args:
        srl_path: Path to the SRL rules file
        ttl_path: Path to the input TTL data file
        overwrite: Whether to overwrite existing result files
        
    Returns:
        Path to the generated result file, or None if skipped/failed
    """
    # Determine result file path
    result_path = srl_path.with_name(srl_path.stem + "-result.ttl")
    
    if result_path.exists() and not overwrite:
        logger.debug(f"Skipping {srl_path.name} (result file exists)")
        return None
    
    try:
        # Parse the SRL rules
        parser = SRLParser()
        srl_text = srl_path.read_text(encoding="utf-8")
        rule_set = parser.parse(srl_text)
        
        # Load input data
        input_graph = Graph()
        input_graph.parse(str(ttl_path), format="turtle")
        input_size = len(input_graph)
        
        # Evaluate rules
        engine = RuleEngine(rule_set)
        result_graph = engine.evaluate(input_graph, inplace=False)
        
        # Compute inferred triples (result minus input)
        inferred_graph = Graph()
        
        # Copy namespace bindings from result_graph
        for prefix, namespace in result_graph.namespaces():
            inferred_graph.bind(prefix, namespace)
        
        for triple in result_graph:
            if triple not in input_graph:
                inferred_graph.add(triple)
        
        inferred_size = len(inferred_graph)
        
        if inferred_size == 0:
            logger.warning(f"{srl_path.name}: No triples inferred")
        
        # Serialize inferred triples
        inferred_graph.serialize(str(result_path), format="turtle")
        
        logger.info(f"Generated {result_path.name}: {inferred_size} triples inferred (input: {input_size})")
        return result_path
        
    except StratificationError as e:
        logger.warning(f"{srl_path.name}: Stratification error - {e}")
        # For stratification tests, we don't generate result files
        return None
        
    except Exception as e:
        logger.error(f"{srl_path.name}: Error - {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate expected result files for W3C manifest-based tests"
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=Path(__file__).parent.parent / "tests" / "test-cases",
        help="Directory containing test cases (default: tests/test-cases)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing result files"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Only process tests in this category subdirectory"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine test directory
    test_dir = args.test_dir
    if args.category:
        test_dir = test_dir / args.category
    
    if not test_dir.exists():
        logger.error(f"Test directory not found: {test_dir}")
        sys.exit(1)
    
    logger.info(f"Scanning for test cases in: {test_dir}")
    
    # Find and process test pairs
    pairs = find_test_pairs(test_dir)
    logger.info(f"Found {len(pairs)} test case pairs")
    
    generated = 0
    skipped = 0
    failed = 0
    
    for srl_path, ttl_path in pairs:
        result = generate_result_file(srl_path, ttl_path, args.overwrite)
        if result:
            generated += 1
        elif result is None:
            skipped += 1
        else:
            failed += 1
    
    logger.info(f"Summary: {generated} generated, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
