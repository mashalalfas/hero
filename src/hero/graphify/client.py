"""HERO graphify client wrapper."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from hero.graphify.query import parse_response


def _find_graphify_binary() -> str:
    """Find the graphify binary path."""
    binary = shutil.which("graphify")
    if binary is not None:
        return binary
    # Fallback to known path
    return "/home/max/.local/bin/graphify"


class GraphifyClient:
    """Client wrapper for the graphify CLI tool."""

    def __init__(self) -> None:
        self._binary = _find_graphify_binary()

    def _resolve_sandbox(self, sandbox: str) -> str:
        """Resolve sandbox name to absolute path, or return if already a path."""
        if not sandbox or sandbox.startswith("/"):
            return sandbox
        from hero.state.index import IndexState
        index = IndexState()
        entry = index.get_sandbox(sandbox)
        if entry:
            return entry["path"]
        raise ValueError(f"Sandbox '{sandbox}' not found. Run 'hero scan' first.")

    def query(
        self, question: str, sandbox: str, format: str = "toon"
    ) -> dict[str, Any]:
        """Run a BFS query against the graph.

        Args:
            question: The question to ask the graph.
            sandbox: Sandbox name to look up in INDEX, OR an absolute path.
            format: Output format (toon, json, plain). Defaults to toon.

        Returns:
            Structured dict with query results.
        """
        resolved = self._resolve_sandbox(sandbox)
        graph_path = f"{resolved}/graphify-out/graph.json" if resolved else ""
        cmd = [
            self._binary,
            "query",
            "--format",
            format,
            "--graph",
            graph_path,
            question,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()

        # Parse output into structured result
        return parse_response(output)

    def path(self, node_a: str, node_b: str, sandbox: str) -> str:
        """Find shortest path between two nodes.

        Args:
            node_a: Starting node label.
            node_b: Target node label.
            sandbox: Sandbox name or path.

        Returns:
            Raw output from graphify path command.
        """
        resolved = self._resolve_sandbox(sandbox) if sandbox else ""
        graph_path = f"{resolved}/graphify-out/graph.json" if resolved else ""
        cmd = [
            self._binary,
            "path",
            node_a,
            node_b,
            "--graph",
            graph_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout

    def explain(self, concept: str, sandbox: str) -> str:
        """Get plain-language explanation of a node and its neighbors.

        Args:
            concept: Node label to explain.
            sandbox: Sandbox name or path.

        Returns:
            Raw output from graphify explain command.
        """
        resolved = self._resolve_sandbox(sandbox) if sandbox else ""
        graph_path = f"{resolved}/graphify-out/graph.json" if resolved else ""
        cmd = [
            self._binary,
            "explain",
            concept,
            "--graph",
            graph_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout

    def update(self, sandbox_path: str) -> str:
        """Re-extract code files and update the graph.

        Args:
            sandbox_path: Path to the sandbox directory to update.

        Returns:
            Raw output from graphify update command.
        """
        cmd = [self._binary, "update", sandbox_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
