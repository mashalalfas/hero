"""Tests for graphify client and query utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hero.graphify.client import GraphifyClient, _find_graphify_binary
from hero.graphify.query import build_query, parse_response


class TestFindGraphifyBinary:
    """Tests for _find_graphify_binary function."""

    def test_finds_via_which(self) -> None:
        """Test that which is used to find the binary."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/custom/path/graphify"
            result = _find_graphify_binary()
            assert result == "/custom/path/graphify"
            mock_which.assert_called_once_with("graphify")

    def test_fallback_to_known_path(self) -> None:
        """Test fallback to known path when which returns None."""
        with patch("shutil.which", return_value=None):
            result = _find_graphify_binary()
            assert result == "/home/max/.local/bin/graphify"


class TestGraphifyClient:
    """Tests for GraphifyClient class."""

    @pytest.fixture
    def client(self) -> GraphifyClient:
        """Create a GraphifyClient for testing."""
        return GraphifyClient()

    def test_query_builds_correct_command(self, client: GraphifyClient) -> None:
        """Test that query method builds correct subprocess command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="test output", returncode=0)
            mock_run.return_value.stdout = "test output"

            result = client.query("how does X relate to Y", "/tmp/sandbox")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            # call_args[0] = positional args tuple, call_args[1] = kwargs dict
            cmd = call_args[0][0]  # first positional arg is the cmd list
            assert "query" in cmd
            assert "how does X relate to Y" in cmd
            assert "--graph" in cmd
            assert "--format" in cmd
            assert "toon" in cmd

    def test_query_returns_structured_result(self, client: GraphifyClient) -> None:
        """Test that query returns structured dict with answer, nodes, edges."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="answer from graphify", returncode=0)

            result = client.query("test question", "/tmp/sandbox")

            assert isinstance(result, dict)
            assert result["answer"] == "answer from graphify"
            assert "nodes" in result
            assert "edges" in result

    def test_path_builds_correct_command(self, client: GraphifyClient) -> None:
        """Test that path method builds correct subprocess command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="path output", returncode=0)

            result = client.path("NodeA", "NodeB", "/tmp/sandbox")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "path" in cmd
            assert "NodeA" in cmd
            assert "NodeB" in cmd

    def test_explain_builds_correct_command(self, client: GraphifyClient) -> None:
        """Test that explain method builds correct subprocess command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="explanation output", returncode=0)

            result = client.explain("MyClass", "/tmp/sandbox")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "explain" in cmd
            assert "MyClass" in cmd

    def test_update_builds_correct_command(self, client: GraphifyClient) -> None:
        """Test that update method builds correct subprocess command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="update output", returncode=0)

            result = client.update("/tmp/sandbox")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "update" in cmd
            assert "/tmp/sandbox" in cmd


class TestBuildQuery:
    """Tests for build_query function."""

    def test_returns_stripped_question(self) -> None:
        """Test that build_query strips whitespace."""
        result = build_query("  how does X work?  ")
        assert result == "how does X work?"

    def test_returns_question_unchanged(self) -> None:
        """Test that build_query returns the question unchanged."""
        result = build_query("what is the relationship between A and B")
        assert result == "what is the relationship between A and B"


class TestParseResponse:
    """Tests for parse_response function."""

    def test_returns_answer_key(self) -> None:
        """Test that parse_response returns dict with answer key."""
        result = parse_response("some raw output")
        assert "answer" in result
        assert result["answer"] == "some raw output"

    def test_returns_nodes_key(self) -> None:
        """Test that parse_response returns dict with nodes key."""
        result = parse_response("some raw output")
        assert "nodes" in result
        assert isinstance(result["nodes"], list)

    def test_returns_edges_key(self) -> None:
        """Test that parse_response returns dict with edges key."""
        result = parse_response("some raw output")
        assert "edges" in result
        assert isinstance(result["edges"], list)

    def test_extracts_nodes_from_backticks(self) -> None:
        """Test that nodes in backticks are extracted."""
        raw = "The `MyClass` uses `MyOtherClass` internally."
        result = parse_response(raw)
        assert "MyClass" in result["nodes"]
        assert "MyOtherClass" in result["nodes"]

    def test_extracts_edges_from_arrows(self) -> None:
        """Test that edges with arrows are extracted."""
        raw = "A -> B and C --> D"
        result = parse_response(raw)
        assert ("A", "B", "") in result["edges"]
        assert ("C", "D", "") in result["edges"]

    def test_extracts_from_code_block(self) -> None:
        """Test that content from code blocks is used as answer."""
        raw = '```\nsome code block content\n```'
        result = parse_response(raw)
        assert "some code block content" in result["answer"]

    def test_deduplicates_nodes(self) -> None:
        """Test that duplicate nodes are deduplicated."""
        raw = "`MyClass` extends `MyClass` and uses `MyClass`"
        result = parse_response(raw)
        assert result["nodes"].count("MyClass") == 1
