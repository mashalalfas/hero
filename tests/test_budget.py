"""Tests for hero budget --query command."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hero.commands.budget import (
    _parse_query_expression,
    _load_all_budgets,
    _format_budget_toon,
    _get_sandbox_dir,
)


class TestParseQueryExpression:
    """Tests for query expression parsing."""

    def test_simple_budget_less_than(self):
        """Test 'budget < 2000' expression."""
        filter_func = _parse_query_expression("budget < 2000")
        
        sandbox_low = {"tokens_remaining": 1500, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        sandbox_high = {"tokens_remaining": 3000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        
        assert filter_func(sandbox_low) is True
        assert filter_func(sandbox_high) is False

    def test_simple_budget_greater_than(self):
        """Test 'budget > 5000' expression."""
        filter_func = _parse_query_expression("budget > 5000")
        
        sandbox_high = {"tokens_remaining": 6000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        sandbox_low = {"tokens_remaining": 3000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        
        assert filter_func(sandbox_high) is True
        assert filter_func(sandbox_low) is False

    def test_budget_equals(self):
        """Test 'budget == 3000' expression."""
        filter_func = _parse_query_expression("budget == 3000")
        
        sandbox_match = {"tokens_remaining": 3000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        sandbox_no_match = {"tokens_remaining": 3001, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        
        assert filter_func(sandbox_match) is True
        assert filter_func(sandbox_no_match) is False

    def test_and_operator(self):
        """Test 'budget < 2000 AND status == active' expression."""
        filter_func = _parse_query_expression("budget < 2000 AND status == active")
        
        sandbox_match = {"tokens_remaining": 1500, "bootstrap_max": 5000, "compactions_used": 0, "status": "active"}
        sandbox_wrong_budget = {"tokens_remaining": 2500, "bootstrap_max": 5000, "compactions_used": 0, "status": "active"}
        sandbox_wrong_status = {"tokens_remaining": 1500, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        
        assert filter_func(sandbox_match) is True
        assert filter_func(sandbox_wrong_budget) is False
        assert filter_func(sandbox_wrong_status) is False

    def test_or_operator(self):
        """Test 'budget < 1000 OR compactions >= 3' expression."""
        filter_func = _parse_query_expression("budget < 1000 OR compactions >= 3")
        
        sandbox_low_budget = {"tokens_remaining": 500, "bootstrap_max": 5000, "compactions_used": 1, "status": "idle"}
        sandbox_high_compactions = {"tokens_remaining": 4000, "bootstrap_max": 5000, "compactions_used": 3, "status": "idle"}
        sandbox_neither = {"tokens_remaining": 2000, "bootstrap_max": 5000, "compactions_used": 1, "status": "idle"}
        
        assert filter_func(sandbox_low_budget) is True
        assert filter_func(sandbox_high_compactions) is True
        assert filter_func(sandbox_neither) is False

    def test_status_string_comparison(self):
        """Test status string comparison with quoted string."""
        filter_func = _parse_query_expression("status == 'active'")
        
        sandbox_active = {"tokens_remaining": 5000, "bootstrap_max": 5000, "compactions_used": 0, "status": "active"}
        sandbox_idle = {"tokens_remaining": 5000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        
        assert filter_func(sandbox_active) is True
        assert filter_func(sandbox_idle) is False

    def test_budget_max_field(self):
        """Test 'budget_max' field (bootstrap_max) comparison."""
        filter_func = _parse_query_expression("budget_max >= 8000")
        
        sandbox_high = {"tokens_remaining": 5000, "bootstrap_max": 10000, "compactions_used": 0, "status": "idle"}
        sandbox_low = {"tokens_remaining": 5000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        
        assert filter_func(sandbox_high) is True
        assert filter_func(sandbox_low) is False

    def test_name_field_filtering(self):
        """Test filtering by sandbox name."""
        filter_func = _parse_query_expression("name == 'HERO'")
        
        sandbox_hero = {"name": "HERO", "tokens_remaining": 5000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        sandbox_other = {"name": "other", "tokens_remaining": 5000, "bootstrap_max": 5000, "compactions_used": 0, "status": "idle"}
        
        assert filter_func(sandbox_hero) is True
        assert filter_func(sandbox_other) is False

    def test_invalid_dangerous_keyword(self):
        """Test that dangerous keywords are rejected."""
        with pytest.raises(ValueError, match="Disallowed keyword"):
            _parse_query_expression("budget < 2000 AND __import__('os').system('rm -rf /')")

    def test_invalid_characters(self):
        """Test that invalid characters are rejected."""
        with pytest.raises(ValueError, match="Invalid characters"):
            _parse_query_expression("budget < 2000; DROP TABLE budgets")


class TestLoadAllBudgets:
    """Tests for loading budgets from sandbox directories."""

    def test_load_from_temp_directory(self):
        """Test loading budgets from a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create test sandbox directories with budget files
            sandbox1 = tmppath / "sandbox1"
            sandbox1.mkdir()
            (sandbox1 / "BUDGET.toon").write_text(
                "bootstrap_max: 5000\ncompactions_used: 2\ntokens_remaining: 3000\n"
            )
            (sandbox1 / "HEARTBEAT.toon").write_text(
                "status: active\n"
            )
            
            sandbox2 = tmppath / "sandbox2"
            sandbox2.mkdir()
            (sandbox2 / "BUDGET.toon").write_text(
                "bootstrap_max: 10000\ncompactions_used: 0\ntokens_remaining: 8000\n"
            )
            (sandbox2 / "HEARTBEAT.toon").write_text(
                "status: idle\n"
            )
            
            budgets = _load_all_budgets(tmppath)
            
            assert len(budgets) == 2
            
            # Check sandbox1
            s1 = next(b for b in budgets if b["name"] == "sandbox1")
            assert s1["tokens_remaining"] == 3000
            assert s1["bootstrap_max"] == 5000
            assert s1["compactions_used"] == 2
            assert s1["status"] == "active"
            
            # Check sandbox2
            s2 = next(b for b in budgets if b["name"] == "sandbox2")
            assert s2["tokens_remaining"] == 8000
            assert s2["bootstrap_max"] == 10000
            assert s2["compactions_used"] == 0
            assert s2["status"] == "idle"

    def test_empty_directory(self):
        """Test loading from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budgets = _load_all_budgets(Path(tmpdir))
            assert budgets == []

    def test_missing_budget_file(self):
        """Test handling of sandbox without budget file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            sandbox = tmppath / "no-budget"
            sandbox.mkdir()
            # No BUDGET.toon file
            
            budgets = _load_all_budgets(tmppath)
            
            assert len(budgets) == 1
            assert budgets[0]["name"] == "no-budget"
            assert budgets[0]["tokens_remaining"] == 5000  # Default
            assert budgets[0]["bootstrap_max"] == 5000  # Default

    def test_skip_non_directory_files(self):
        """Test that non-directory files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create a file (not a directory)
            (tmppath / "not-a-sandbox.txt").write_text("some text")
            
            budgets = _load_all_budgets(tmppath)
            assert budgets == []


class TestFormatBudgetToon:
    """Tests for TOON output formatting."""

    def test_format_single_budget(self):
        """Test formatting a single budget entry."""
        budgets = [{
            "name": "test-sandbox",
            "path": "/home/user/.hero/sandboxes/test-sandbox",
            "bootstrap_max": 5000,
            "compactions_used": 2,
            "tokens_remaining": 3000,
            "status": "active",
        }]
        
        output = _format_budget_toon(budgets)
        
        assert "sandbox: test-sandbox" in output
        assert "tokens_remaining: 3000" in output
        assert "compactions_used: 2" in output
        assert "bootstrap_max: 5000" in output
        assert "status: active" in output

    def test_format_multiple_budgets(self):
        """Test formatting multiple budget entries."""
        budgets = [
            {
                "name": "sandbox1",
                "path": "/path/to/sandbox1",
                "bootstrap_max": 5000,
                "compactions_used": 1,
                "tokens_remaining": 4000,
                "status": "idle",
            },
            {
                "name": "sandbox2",
                "path": "/path/to/sandbox2",
                "bootstrap_max": 10000,
                "compactions_used": 0,
                "tokens_remaining": 10000,
                "status": "active",
            },
        ]
        
        output = _format_budget_toon(budgets)
        
        assert "sandbox: sandbox1" in output
        assert "sandbox: sandbox2" in output

    def test_format_empty_list(self):
        """Test formatting empty budget list."""
        output = _format_budget_toon([])
        assert "# No budgets found" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])