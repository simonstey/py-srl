"""
Rich formatting helpers for SRL CLI.

Provides styled output using Rich for tables, trees, panels, and error display.
"""

from typing import Any, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from ..ast.nodes import (
    RuleSet,
    Rule,
    TriplePattern,
    TripleTemplate,
    ConditionExpression,
    Assignment,
    NegationElement,
    Variable,
    IRI,
    Literal,
)

console = Console()
error_console = Console(stderr=True)


def format_term(term: Any) -> str:
    """Format an RDF term for display."""
    if isinstance(term, Variable):
        return f"?{term.name}"
    elif isinstance(term, IRI):
        return f"<{term.value}>"
    elif isinstance(term, Literal):
        if term.language:
            return f'"{term.value}"@{term.language}'
        elif term.datatype:
            return f'"{term.value}"^^<{term.datatype.value}>'
        return f'"{term.value}"'
    return str(term)


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_error(title: str, message: str, line: Optional[int] = None, column: Optional[int] = None) -> None:
    """Print an error panel with optional location info."""
    error_text = message
    if line is not None:
        error_text += f"\n\n[dim]Location: line {line}"
        if column is not None:
            error_text += f", column {column}"
        error_text += "[/dim]"

    error_console.print(Panel(error_text, title=f"[bold red]{title}[/bold red]", border_style="red", padding=(1, 2)))


def print_parse_error(message: str, line: Optional[int] = None, column: Optional[int] = None) -> None:
    """Print a parse error panel."""
    print_error("Parse Error", message, line, column)


def print_stratification_error(message: str) -> None:
    """Print a stratification error panel."""
    print_error("Stratification Error", message)


def print_file_error(filepath: str, message: str) -> None:
    """Print a file error panel."""
    print_error("File Error", f"[bold]{filepath}[/bold]\n\n{message}")


def display_rule_set_summary(rule_set: RuleSet, verbose: bool = False) -> None:
    """Display a summary of the parsed rule set."""
    console.print()

    console.print(
        Panel(
            f"[bold cyan]Rules:[/bold cyan] {len(rule_set.rules)}\n"
            f"[bold cyan]Data Blocks:[/bold cyan] {len(rule_set.data_blocks)}\n"
            f"[bold cyan]Prefixes:[/bold cyan] {len(rule_set.prologue.prefixes)}",
            title="[bold]Rule Set Summary[/bold]",
            border_style="blue",
        )
    )

    if rule_set.prologue.prefixes:
        prefix_table = Table(title="Prefixes", show_header=True, header_style="bold magenta")
        prefix_table.add_column("Prefix", style="cyan")
        prefix_table.add_column("IRI", style="green")

        for prefix, iri in rule_set.prologue.prefixes.items():
            prefix_table.add_row(prefix, format_term(iri) if isinstance(iri, IRI) else str(iri))

        console.print(prefix_table)

    if rule_set.rules:
        rules_table = Table(title="Rules", show_header=True, header_style="bold magenta")
        rules_table.add_column("#", style="dim", width=4)
        rules_table.add_column("Head Templates", style="cyan")
        rules_table.add_column("Body Elements", style="yellow")

        for i, rule in enumerate(rule_set.rules, 1):
            head_count = len(rule.head.templates) if rule.head else 0
            body_count = len(rule.body.elements) if rule.body else 0
            rules_table.add_row(str(i), str(head_count), str(body_count))

        console.print(rules_table)

    if verbose:
        display_rules_detail(rule_set)


def display_rules_detail(rule_set: RuleSet) -> None:
    """Display detailed information about each rule."""
    console.print()
    console.print("[bold]Rule Details[/bold]")
    console.print()

    for i, rule in enumerate(rule_set.rules, 1):
        rule_tree = Tree(f"[bold cyan]Rule {i}[/bold cyan]")

        head_branch = rule_tree.add("[bold green]Head Templates[/bold green]")
        if rule.head and rule.head.templates:
            for template in rule.head.templates:
                head_branch.add(format_triple_template(template))
        else:
            head_branch.add("[dim](none)[/dim]")

        body_branch = rule_tree.add("[bold yellow]Body Elements[/bold yellow]")
        if rule.body and rule.body.elements:
            for element in rule.body.elements:
                body_branch.add(format_body_element(element))
        else:
            body_branch.add("[dim](none)[/dim]")

        console.print(rule_tree)
        console.print()


def format_triple_template(template: TripleTemplate) -> str:
    """Format a triple template for display."""
    s = format_term(template.subject)
    p = format_term(template.predicate)
    o = format_term(template.object)
    return f"{s} {p} {o} ."


def format_triple_pattern(pattern: TriplePattern) -> str:
    """Format a triple pattern for display."""
    s = format_term(pattern.subject)
    p = format_term(pattern.predicate)
    o = format_term(pattern.object)
    return f"{s} {p} {o} ."


def format_body_element(element: Any) -> str:
    """Format a body element for display."""
    if isinstance(element, TriplePattern):
        return f"[blue]PATTERN:[/blue] {format_triple_pattern(element)}"
    elif isinstance(element, ConditionExpression):
        return f"[magenta]FILTER:[/magenta] {element.expression}"
    elif isinstance(element, Assignment):
        return f"[green]BIND:[/green] ({element.expression} AS ?{element.variable.name})"
    elif isinstance(element, NegationElement):
        patterns = ", ".join(format_triple_pattern(p) for p in element.body_patterns if isinstance(p, TriplePattern))
        return f"[red]NOT:[/red] {{ {patterns} }}"
    return str(element)


def display_strata(strata: List[List[int]], rules: List[Rule], verbose: bool = False) -> None:
    """Display stratification layers as a tree."""
    console.print()

    if not strata:
        print_info("No stratification layers (no rules)")
        return

    tree = Tree("[bold]Stratification Layers[/bold]")

    for stratum_idx, rule_indices in enumerate(strata):
        stratum_branch = tree.add(f"[bold cyan]Stratum {stratum_idx}[/bold cyan] ({len(rule_indices)} rule(s))")

        for rule_idx in rule_indices:
            rule = rules[rule_idx]
            if rule.head and rule.head.templates:
                first_template = rule.head.templates[0]
                summary = format_triple_template(first_template)
                if len(rule.head.templates) > 1:
                    summary += f" [dim](+{len(rule.head.templates) - 1} more)[/dim]"
            else:
                summary = "[dim](no head templates)[/dim]"

            rule_branch = stratum_branch.add(f"[yellow]Rule {rule_idx + 1}:[/yellow] {summary}")

            if verbose and rule.body and rule.body.elements:
                for element in rule.body.elements:
                    rule_branch.add(f"[dim]{format_body_element(element)}[/dim]")

    console.print(tree)


def display_evaluation_results(
    original_count: int,
    result_count: int,
    inferred_count: int,
    provenance: Optional[List[Tuple]] = None,
    rules: Optional[List[Rule]] = None,
    verbose: bool = False,
) -> None:
    """Display evaluation results."""
    console.print()

    console.print(
        Panel(
            f"[bold cyan]Original triples:[/bold cyan] {original_count}\n"
            f"[bold cyan]Result triples:[/bold cyan] {result_count}\n"
            f"[bold green]Inferred triples:[/bold green] {inferred_count}",
            title="[bold]Evaluation Results[/bold]",
            border_style="green",
        )
    )

    if verbose and provenance and rules:
        console.print()
        console.print("[bold]Inference Details[/bold]")

        provenance_table = Table(show_header=True, header_style="bold magenta")
        provenance_table.add_column("Rule", style="cyan", width=6)
        provenance_table.add_column("Stratum", style="yellow", width=8)
        provenance_table.add_column("Inferred Triple", style="green")

        for triple, rule_idx, stratum in provenance[:50]:  # Limit to 50 for readability
            s, p, o = triple
            triple_str = f"{s} {p} {o}"
            provenance_table.add_row(str(rule_idx + 1), str(stratum), triple_str)

        if len(provenance) > 50:
            provenance_table.add_row("...", "...", f"[dim]({len(provenance) - 50} more)[/dim]")

        console.print(provenance_table)


def display_shacl_coming_soon() -> None:
    """Display a 'coming soon' message for SHACL integration."""
    console.print()
    console.print(
        Panel(
            "[bold yellow]SHACL Shapes Integration[/bold yellow]\n\n"
            "This feature is planned for Phase 5 of the implementation roadmap.\n\n"
            "[bold]Current Status:[/bold]\n"
            "• Core SRL parsing and evaluation: [green]✓ Complete[/green]\n"
            "• SHACL shapes graph loading: [dim]Pending[/dim]\n"
            "• sh:TripleRule extraction: [dim]Pending[/dim]\n"
            "• sh:SPARQLRule extraction: [dim]Pending[/dim]\n\n"
            "[bold]Workaround:[/bold]\n"
            "You can manually convert SHACL rules to SRL syntax and use the [cyan]eval[/cyan] command.\n\n"
            "See the documentation for more details on converting SHACL rules to SRL format.",
            title="[bold blue]Coming Soon[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
    )
