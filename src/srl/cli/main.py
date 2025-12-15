"""
SRL CLI - Command-line interface for SHACL 1.2 Rules.

Provides commands to parse, evaluate, and analyze SRL rules with Rich output.
"""

import sys
from pathlib import Path
from typing import Optional

import rich_click as click
from rdflib import Graph

from .formatting import (
    console,
    print_success,
    print_info,
    print_parse_error,
    print_stratification_error,
    print_file_error,
    display_rule_set_summary,
    display_strata,
    display_evaluation_results,
    display_shacl_coming_soon,
)
from ..engine import RuleEngine, StratificationError
from ..parser import SRLParser, ParseError

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "yellow italic"
click.rich_click.ERRORS_SUGGESTION = "Try 'srl --help' for usage information."


FORMAT_MAP = {
    ".ttl": "turtle",
    ".turtle": "turtle",
    ".rdf": "xml",
    ".xml": "xml",
    ".nt": "nt",
    ".ntriples": "nt",
    ".n3": "n3",
    ".jsonld": "json-ld",
    ".json": "json-ld",
    ".trig": "trig",
    ".nq": "nquads",
}


def detect_format(filepath: str) -> str:
    """Detect RDF format from file extension."""
    ext = Path(filepath).suffix.lower()
    return FORMAT_MAP.get(ext, "turtle")


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output with detailed information.")
@click.version_option(package_name="py-srl")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """
    **SRL** - SHACL 1.2 Rules command-line interface.

    Parse, evaluate, and analyze SHACL 1.2 rules (Shape Rules Language) with rich terminal output.

    ## Examples

    Parse a rules file:

        srl parse rules.srl

    Evaluate rules on data:

        srl eval rules.srl data.ttl -o output.ttl

    Analyze rule stratification:

        srl analyze rules.srl --show-layers
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("rules_file", type=click.Path(exists=True))
@click.pass_context
def parse(ctx: click.Context, rules_file: str) -> None:
    """
    Parse and validate an SRL rules file.

    Displays rule count, prefixes, body elements, and validation status.
    Use --verbose for detailed AST information.

    ## Arguments

    - **RULES_FILE**: Path to the SRL rules file to parse.

    ## Examples

        srl parse rules.srl
        srl -v parse rules.srl
    """
    verbose = ctx.obj.get("verbose", False)

    try:
        parser = SRLParser()
        rule_set = parser.parse_file(rules_file)

        print_success(f"Successfully parsed [bold]{rules_file}[/bold]")
        display_rule_set_summary(rule_set, verbose=verbose)

    except FileNotFoundError:
        print_file_error(rules_file, "File not found. Please check the path and try again.")
        sys.exit(1)
    except ParseError as e:
        msg = str(e)
        line = None
        column = None
        if "line" in msg and "column" in msg:
            import re

            match = re.search(r"line (\d+)", msg)
            if match:
                line = int(match.group(1))
            match = re.search(r"column (\d+)", msg)
            if match:
                column = int(match.group(1))
        print_parse_error(msg, line, column)
        sys.exit(1)
    except Exception as e:
        print_file_error(rules_file, f"Unexpected error: {e}")
        sys.exit(1)


@cli.command()
@click.argument("rules_file", type=click.Path(exists=True))
@click.argument("data_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Output file path for result graph.")
@click.option("-f", "--format", "rdf_format", type=str, help="RDF format override (turtle, xml, nt, json-ld).")
@click.option("--output-format", type=str, default="turtle", help="Output format (default: turtle).")
@click.option("--max-iterations", type=int, default=1000, help="Maximum fixpoint iterations (default: 1000).")
@click.pass_context
def eval(
    ctx: click.Context,
    rules_file: str,
    data_file: str,
    output: Optional[str],
    rdf_format: Optional[str],
    output_format: str,
    max_iterations: int,
) -> None:
    """
    Evaluate SRL rules on an RDF data graph.

    Loads rules, applies them to the data graph using fixpoint iteration,
    and optionally writes the result to a file.

    ## Arguments

    - **RULES_FILE**: Path to the SRL rules file.
    - **DATA_FILE**: Path to the RDF data file.

    ## Examples

        srl eval rules.srl data.ttl
        srl eval rules.srl data.ttl -o output.ttl
        srl eval rules.srl data.rdf -f xml -o output.ttl
        srl -v eval rules.srl data.ttl
    """
    verbose = ctx.obj.get("verbose", False)

    try:
        parser = SRLParser()
        rule_set = parser.parse_file(rules_file)
        print_success(f"Parsed [bold]{rules_file}[/bold] ({len(rule_set.rules)} rule(s))")
    except FileNotFoundError:
        print_file_error(rules_file, "Rules file not found.")
        sys.exit(1)
    except ParseError as e:
        print_parse_error(str(e))
        sys.exit(1)

    try:
        data_format = rdf_format or detect_format(data_file)
        graph = Graph()
        graph.parse(data_file, format=data_format)
        original_count = len(graph)
        print_success(f"Loaded [bold]{data_file}[/bold] ({original_count} triple(s), format: {data_format})")
    except FileNotFoundError:
        print_file_error(data_file, "Data file not found.")
        sys.exit(1)
    except Exception as e:
        print_file_error(data_file, f"Failed to parse RDF data: {e}")
        sys.exit(1)

    try:
        engine = RuleEngine(rule_set, max_iterations=max_iterations)

        if verbose:
            result_graph, provenance = engine.evaluate_with_provenance(graph, inplace=False)
        else:
            result_graph = engine.evaluate(graph, inplace=False)
            provenance = None

        result_count = len(result_graph)
        inferred_count = result_count - original_count

        display_evaluation_results(
            original_count=original_count,
            result_count=result_count,
            inferred_count=inferred_count,
            provenance=provenance,
            rules=rule_set.rules,
            verbose=verbose,
        )

    except StratificationError as e:
        print_stratification_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_file_error(rules_file, f"Evaluation failed: {e}")
        sys.exit(1)

    if output:
        try:
            result_graph.serialize(destination=output, format=output_format)
            print_success(f"Result written to [bold]{output}[/bold] ({result_count} triple(s))")
        except Exception as e:
            print_file_error(output, f"Failed to write output: {e}")
            sys.exit(1)
    else:
        print_info("Use -o/--output to save results to a file.")


@cli.command()
@click.argument("rules_file", type=click.Path(exists=True))
@click.option("--show-layers", is_flag=True, help="Display stratification layers as a tree.")
@click.pass_context
def analyze(ctx: click.Context, rules_file: str, show_layers: bool) -> None:
    """
    Analyze SRL rules for stratification and dependencies.

    Computes the stratification layers and displays rule dependencies.

    ## Arguments

    - **RULES_FILE**: Path to the SRL rules file to analyze.

    ## Examples

        srl analyze rules.srl
        srl analyze rules.srl --show-layers
        srl -v analyze rules.srl --show-layers
    """
    verbose = ctx.obj.get("verbose", False)

    try:
        parser = SRLParser()
        rule_set = parser.parse_file(rules_file)
        print_success(f"Parsed [bold]{rules_file}[/bold] ({len(rule_set.rules)} rule(s))")
    except FileNotFoundError:
        print_file_error(rules_file, "File not found.")
        sys.exit(1)
    except ParseError as e:
        print_parse_error(str(e))
        sys.exit(1)

    try:
        engine = RuleEngine(rule_set)
        strata = engine.get_stratum_info()

        console.print()
        console.print(f"[bold cyan]Total strata:[/bold cyan] {len(strata)}")
        console.print(f"[bold cyan]Total rules:[/bold cyan] {len(rule_set.rules)}")

        if show_layers or verbose:
            display_strata(strata, rule_set.rules, verbose=verbose)
        else:
            print_info("Use --show-layers to display stratification tree.")

    except StratificationError as e:
        print_stratification_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_file_error(rules_file, f"Analysis failed: {e}")
        sys.exit(1)


@cli.command()
def shacl() -> None:
    """
    Load and evaluate SHACL shapes with embedded rules.

    [yellow]⚠ This feature is not yet implemented.[/yellow]

    SHACL shapes integration is planned for Phase 5 of the implementation.
    Currently, you can convert SHACL rules to SRL syntax and use the 'eval' command.
    """
    display_shacl_coming_soon()


if __name__ == "__main__":
    cli()
