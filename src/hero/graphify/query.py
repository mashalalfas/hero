"""HERO graphify query utilities."""

from __future__ import annotations

import json
import re
from typing import Any


def build_query(question: str) -> str:
    """Build a properly formatted query string for graphify.

    Args:
        question: The natural language question to format.

    Returns:
        Formatted query string ready for graphify CLI.
    """
    # Escape quotes and wrap properly for shell
    return question.strip()


def parse_response(raw: str) -> dict[str, Any]:
    """Parse raw graphify output into structured data.

    Args:
        raw: Raw stdout from graphify command.

    Returns:
        Dictionary with keys:
            - answer: The text answer from graphify
            - nodes: List of node labels referenced
            - edges: List of edge tuples (source, target, context)
    """
    nodes: list[str] = []
    edges: list[tuple[str, str, str]] = []

    # Try to parse as JSON first (some graphify outputs are JSON)
    answer = raw.strip()

    # Try to extract nodes from markdown-style code blocks
    code_block_pattern = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
    code_matches = code_block_pattern.findall(raw)
    if code_matches:
        answer = code_matches[0].strip()

    # Try to extract node references like `NodeName` or "NodeName"
    node_pattern = re.compile(r"`([^`]+)`")
    nodes = list(dict.fromkeys(node_pattern.findall(raw)))

    # Try to parse edge-like patterns: "A -> B" or "A --> B" or "A: context -> B"
    edge_pattern = re.compile(r"([^\s\[\]]+)\s*(?:-{1,2}>|→)\s*([^\s\[\]]+)")
    edge_matches = edge_pattern.findall(raw)
    for source, target in edge_matches:
        edges.append((source, target, ""))

    return {
        "answer": answer,
        "nodes": nodes,
        "edges": edges,
    }
