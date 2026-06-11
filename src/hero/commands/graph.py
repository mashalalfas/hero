"""hero graph — Query Graphify for code knowledge and analyze project dependencies."""

from __future__ import annotations

from typing import Any

import click

from hero.graphify.client import GraphifyClient
from hero.state.index import IndexState


def _build_toon_output(query: str, sandbox: str | None, results: dict[str, Any]) -> str:
    """Build TOON-formatted output for graph results.

    Args:
        query: The query string that was searched.
        sandbox: Optional sandbox name that was used.
        results: Structured results from GraphifyClient.

    Returns:
        TOON formatted string.
    """
    lines = ["graph_results:"]
    lines.append(f"  query: \"{query}\"")
    if sandbox:
        lines.append(f"  sandbox: {sandbox}")

    # Add answer if present
    if results.get("answer"):
        answer_lines = results["answer"].split("\n")
        if len(answer_lines) > 1:
            lines.append("  answer: |")
            for line in answer_lines:
                lines.append(f"    {line}")
        else:
            lines.append(f'  answer: "{results["answer"]}"')

    # Add nodes if present
    nodes = results.get("nodes", [])
    if nodes:
        node_list = ", ".join(f'"{n}"' for n in nodes)
        lines.append(f"  nodes[{len(nodes)}]: {node_list}")

    # Add edges if present
    edges = results.get("edges", [])
    if edges:
        lines.append(f"  edges[{len(edges)}]:")
        for src, tgt, ctx in edges:
            if ctx:
                lines.append(f'    {{path: {src}, relation: "{ctx}", target: {tgt}}}')
            else:
                lines.append(f"    {{src: {src}, tgt: {tgt}}}")

    return "\n".join(lines)


@click.group()
def graph() -> None:
    """Query Graphify for code knowledge or analyze project dependencies.

    \b
    Subcommands:
      query        Query Graphify for code relationships
      dependencies Show dependency graph across sandboxes

    Examples:
      hero graph query --query "flutter debugging" --sandbox sook-pro
      hero graph dependencies
      hero graph dependencies --sandbox sook_pro --format list
    """


@graph.command("query")
@click.option(
    "--query",
    required=True,
    type=str,
    help="Query string for graphify.",
)
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Optional sandbox name to scope the query.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["toon", "json", "plain"]),
    default="toon",
    help="Output format for results.",
)
def query(query: str, sandbox: str | None, output_format: str) -> None:
    """Query Graphify for code knowledge.

    Graphify provides code-aware navigation by indexing project code
    and answering relationship queries (e.g., "how does X relate to Y").

    Example:
      hero graph query --query "flutter debugging" --sandbox sook-pro
      hero graph query --query "user authentication flow"
    """
    if sandbox:
        index = IndexState()
        entry = index.get_sandbox(sandbox)
        if not entry:
            raise click.ClickException(
                f"Sandbox '{sandbox}' not found. Run 'hero scan' first."
            )

    click.echo(f"Querying graphify...")
    click.echo(f"  query: {query}")
    if sandbox:
        click.echo(f"  sandbox: {sandbox}")

    try:
        client = GraphifyClient()
        result = client.query(query, sandbox or "", format=output_format)

        if output_format == "plain":
            # For plain, just output the raw answer
            if result.get("answer"):
                click.echo(result["answer"])
            else:
                click.echo("No results found.")
        elif output_format == "json":
            # Output as JSON
            import json
            click.echo(json.dumps(result, indent=2))
        else:
            # Default: toon format
            toon_output = _build_toon_output(query, sandbox, result)
            click.echo(toon_output)

    except Exception as e:
        raise click.ClickException(str(e)) from e


@graph.command("dependencies")
@click.option(
    "--sandbox",
    type=str,
    default=None,
    help="Filter to one sandbox.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["tree", "list"]),
    default="tree",
    help="Output format (tree or list).",
)
def dependencies(sandbox: str | None, output_format: str) -> None:
    """Show dependency graph across all sandboxes.

    Scans pubspec.yaml, package.json, pyproject.toml, and Cargo.toml
    files to discover cross-project and external dependencies.

    \b
    Examples:
      hero graph dependencies
      hero graph dependencies --sandbox sook_pro
      hero graph dependencies --format list
    """
    from hero.graph.dependencies import scan_all_sandboxes, scan_sandbox

    if sandbox:
        all_deps = scan_sandbox(sandbox)
    else:
        all_deps = scan_all_sandboxes()

    if not all_deps:
        click.echo("No dependencies found.")
        return

    if output_format == "tree":
        # Group by source
        by_source: dict[str, list[dict[str, Any]]] = {}
        for d in all_deps:
            by_source.setdefault(d["source"], []).append(d)
        for src in sorted(by_source):
            click.echo(f"  {src}")
            grouped = sorted(by_source[src], key=lambda x: x["target"])
            for i, dep in enumerate(grouped):
                prefix = "    └── " if i == len(grouped) - 1 else "    ├── "
                click.echo(f"{prefix}{dep['target']}  ({dep['type']}) [{dep['version']}]")
    else:
        # List format
        click.echo(f"{'Source':<20} {'Target':<25} {'Type':<10} Version")
        click.echo("-" * 70)
        for d in sorted(all_deps, key=lambda x: (x["source"], x["target"])):
            click.echo(f"{d['source']:<20} {d['target']:<25} {d['type']:<10} {d['version']}")


if __name__ == "__main__":
    graph()
