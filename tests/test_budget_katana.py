"""Tests for BudgetState + SandboxState Katana cycle integration."""

import tempfile
from pathlib import Path

import pytest

from hero.state.budget import BudgetState
from hero.state.sandbox import SandboxState


class TestKatanaCycleIntegration:
    """Test the complete Katana cycle: spawn -> complete -> compact.
    
    Verifies that:
    1. spawn_task() / add_pending_task() decrements tokens_remaining
    2. complete_task() increments tokens_remaining
    3. compact_budget() resets compactions_used
    4. add_known_issue() tracks issues without affecting budget
    """

    def test_spawn_decrements_budget_tokens(self, tmp_path):
        """Test that adding a pending task decrements budget tokens."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        # Initial tokens_remaining should be 5000
        data = state.load()
        assert data["budget"]["tokens_remaining"] == 5000
        
        # Spawn a task - should decrement by 100 (default)
        state.add_pending_task("fix bug #123")
        
        data = state.load()
        assert data["budget"]["tokens_remaining"] == 4900
        assert "fix bug #123" in data["katana"]["pending"]

    def test_complete_increments_budget_tokens(self, tmp_path):
        """Test that completing a task increments budget tokens."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        # Add and then complete a task
        state.add_pending_task("fix bug #123")
        initial_tokens = state.load()["budget"]["tokens_remaining"]
        
        # Complete the task
        found = state.complete_task("fix bug #123")
        assert found is True
        
        data = state.load()
        assert data["budget"]["tokens_remaining"] == initial_tokens + 50
        assert "fix bug #123" not in data["katana"]["pending"]

    def test_complete_nonexistent_task_returns_false(self, tmp_path):
        """Test that completing a non-existent task returns False."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        found = state.complete_task("nonexistent task")
        assert found is False

    def test_compact_resets_compactions_used(self, tmp_path):
        """Test that compact_budget() resets compactions_used to 0."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        # Record some compactions directly via budget_state
        state.budget_state.update(field="compactions_used", value=5)
        assert state.load()["budget"]["compactions_used"] == 5
        
        # Compact should reset
        state.compact_budget()
        
        data = state.load()
        assert data["budget"]["compactions_used"] == 0

    def test_full_katana_cycle(self, tmp_path):
        """Test complete Katana cycle: spawn -> complete -> compact."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        # Initial state
        data = state.load()
        assert data["budget"]["tokens_remaining"] == 5000
        assert data["budget"]["compactions_used"] == 0
        assert data["katana"]["pending"] == []
        
        # Spawn phase: add 3 tasks
        state.add_pending_task("task A")
        state.add_pending_task("task B")
        state.add_pending_task("task C")
        
        data = state.load()
        assert len(data["katana"]["pending"]) == 3
        assert data["budget"]["tokens_remaining"] == 5000 - 300  # 3 * 100
        
        # Complete phase: complete 2 tasks
        state.complete_task("task A")
        state.complete_task("task B")
        
        data = state.load()
        assert len(data["katana"]["pending"]) == 1
        assert data["budget"]["tokens_remaining"] == 5000 - 300 + 100  # 2 * 50
        
        # Record compactions
        state.budget_state.record_compaction()
        state.budget_state.record_compaction()
        assert state.load()["budget"]["compactions_used"] == 2
        
        # Compact phase: reset compactions
        state.compact_budget()
        
        data = state.load()
        assert data["budget"]["compactions_used"] == 0

    def test_add_known_issue_does_not_affect_budget(self, tmp_path):
        """Test that adding known issues doesn't change budget."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        initial_tokens = state.load()["budget"]["tokens_remaining"]
        
        state.add_known_issue("memory leak in worker")
        state.add_known_issue("crash on startup")
        
        data = state.load()
        assert data["budget"]["tokens_remaining"] == initial_tokens
        assert len(data["katana"]["known_issues"]) == 2
        assert "memory leak in worker" in data["katana"]["known_issues"]

    def test_get_katana_status_returns_all_info(self, tmp_path):
        """Test that get_katana_status() returns pending, issues, and budget."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        state.add_pending_task("task 1")
        state.add_known_issue("issue 1")
        state.budget_state.update(field="compactions_used", value=3)
        
        status = state.get_katana_status()
        
        assert "task 1" in status["pending"]
        assert "issue 1" in status["known_issues"]
        assert status["budget"]["compactions_used"] == 3
        assert status["budget"]["tokens_remaining"] == 4900

    def test_spawn_task_is_alias_for_add_pending_task(self, tmp_path):
        """Test that spawn_task() behaves identically to add_pending_task()."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        state.spawn_task("spawned task")
        
        data = state.load()
        assert "spawned task" in data["katana"]["pending"]
        assert data["budget"]["tokens_remaining"] == 4900


class TestBudgetStateKatanaMethods:
    """Test BudgetState methods used in Katana cycle directly."""

    def test_spawn_decrement_updates_budget_file(self, tmp_path):
        """Test that spawn_decrement() properly persists to BUDGET.toon."""
        state = BudgetState("test-sbx", base_path=tmp_path)
        
        result = state.spawn_decrement(amount=200)
        
        assert result == 4800
        data = state.load("test-sbx")
        assert data["tokens_remaining"] == 4800

    def test_complete_increment_updates_budget_file(self, tmp_path):
        """Test that complete_increment() properly persists to BUDGET.toon."""
        state = BudgetState("test-sbx", base_path=tmp_path)
        state.update(field="tokens_remaining", value=4000)
        
        result = state.complete_increment(amount=100)
        
        assert result == 4100
        data = state.load("test-sbx")
        assert data["tokens_remaining"] == 4100

    def test_complete_increment_caps_at_bootstrap_max(self, tmp_path):
        """Test that complete_increment() doesn't exceed bootstrap_max."""
        state = BudgetState("test-sbx", base_path=tmp_path)
        state.update(field="tokens_remaining", value=5000)  # already at max
        
        result = state.complete_increment(amount=100)
        
        assert result == 5000  # capped, not 5100

    def test_compact_reset_updates_budget_file(self, tmp_path):
        """Test that compact_reset() properly persists to BUDGET.toon."""
        state = BudgetState("test-sbx", base_path=tmp_path)
        state.update(field="compactions_used", value=10)
        
        state.compact_reset()
        
        data = state.load("test-sbx")
        assert data["compactions_used"] == 0


class TestSandboxStateBudgetIntegration:
    """Test SandboxState properly integrates with BudgetState."""

    def test_budget_state_uses_same_base_path(self, tmp_path):
        """Test that budget_state shares the same file location."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        # budget_state should be at same sandbox dir
        budget_path = state.budget_state.base_path / "BUDGET.toon"
        
        assert budget_path == state.base_path / "BUDGET.toon"

    def test_multiple_spawns_accumulate(self, tmp_path):
        """Test that multiple spawns accumulate token deduction."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        state.add_pending_task("task 1")
        state.add_pending_task("task 2")
        state.add_pending_task("task 3")
        
        data = state.load()
        assert data["budget"]["tokens_remaining"] == 5000 - 300
        assert len(data["katana"]["pending"]) == 3

    def test_multiple_completes_accumulate(self, tmp_path):
        """Test that multiple completes accumulate token return."""
        state = SandboxState("test-sbx", base_path=tmp_path)
        
        # Set tokens to known value
        state.budget_state.update(field="tokens_remaining", value=4900)
        state.add_pending_task("task 1")
        state.add_pending_task("task 2")
        
        # Complete both
        state.complete_task("task 1")
        state.complete_task("task 2")
        
        data = state.load()
        # 4900 - 200 + 100 = 4800
        assert data["budget"]["tokens_remaining"] == 4800