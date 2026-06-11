"""Tests for HERO state modules: IndexState, SandboxState, BudgetState."""

import tempfile
from pathlib import Path

import pytest

from hero.state.index import IndexState
from hero.state.sandbox import SandboxState
from hero.state.budget import BudgetState


class TestIndexState:
    """Tests for IndexState master sandbox registry."""
    
    def test_load_empty_index(self, tmp_path):
        """Test loading a non-existent index returns defaults."""
        state = IndexState(base_path=tmp_path)
        data = state.load()
        assert data["sandboxes"] == []
        assert data["version"] == "1.0.0"
    
    def test_save_and_load(self, tmp_path):
        """Test saving and loading index data."""
        state = IndexState(base_path=tmp_path)
        data = {
            "sandboxes": [
                {"name": "sook-pro", "path": "/dev/sook-pro", "budget_max": 5000, "skills_count": 2, "status": "idle", "last_seen": "2025-05-23T00:00:00"}
            ],
            "version": "1.0.0",
        }
        state.save(data)
        loaded = state.load()
        assert len(loaded["sandboxes"]) == 1
        assert loaded["sandboxes"][0]["name"] == "sook-pro"
    
    def test_add_sandbox(self, tmp_path):
        """Test adding a new sandbox to the index."""
        state = IndexState(base_path=tmp_path)
        state.add_sandbox("sook-pro", "/dev/sook-pro")
        data = state.load()
        assert len(data["sandboxes"]) == 1
        assert data["sandboxes"][0]["name"] == "sook-pro"
    
    def test_add_duplicate_sandbox_updates(self, tmp_path):
        """Test adding the same sandbox twice updates rather than duplicates."""
        state = IndexState(base_path=tmp_path)
        state.add_sandbox("sook-pro", "/dev/sook-pro")
        state.add_sandbox("sook-pro", "/dev/sook-pro-v2")
        data = state.load()
        assert len(data["sandboxes"]) == 1
        assert data["sandboxes"][0]["path"] == "/dev/sook-pro-v2"
    
    def test_remove_sandbox(self, tmp_path):
        """Test removing a sandbox from the index."""
        state = IndexState(base_path=tmp_path)
        state.add_sandbox("sook-pro", "/dev/sook-pro")
        state.add_sandbox("freya", "/dev/freya")
        removed = state.remove_sandbox("sook-pro")
        assert removed is True
        data = state.load()
        assert len(data["sandboxes"]) == 1
        assert data["sandboxes"][0]["name"] == "freya"
    
    def test_remove_nonexistent_sandbox(self, tmp_path):
        """Test removing a sandbox that doesn't exist returns False."""
        state = IndexState(base_path=tmp_path)
        removed = state.remove_sandbox("nonexistent")
        assert removed is False
    
    def test_get_sandbox(self, tmp_path):
        """Test retrieving a specific sandbox entry."""
        state = IndexState(base_path=tmp_path)
        state.add_sandbox("sook-pro", "/dev/sook-pro")
        entry = state.get_sandbox("sook-pro")
        assert entry is not None
        assert entry["name"] == "sook-pro"
    
    def test_get_nonexistent_sandbox(self, tmp_path):
        """Test retrieving a sandbox that doesn't exist returns None."""
        state = IndexState(base_path=tmp_path)
        entry = state.get_sandbox("nonexistent")
        assert entry is None
    
    def test_list_sandboxes(self, tmp_path):
        """Test listing all sandboxes."""
        state = IndexState(base_path=tmp_path)
        state.add_sandbox("sook-pro", "/dev/sook-pro")
        state.add_sandbox("freya", "/dev/freya")
        sandboxes = state.list_sandboxes()
        assert len(sandboxes) == 2
    
    def test_update_last_seen(self, tmp_path):
        """Test updating the last_seen timestamp."""
        state = IndexState(base_path=tmp_path)
        state.add_sandbox("sook-pro", "/dev/sook-pro")
        state.update_last_seen("sook-pro")
        entry = state.get_sandbox("sook-pro")
        assert entry["last_seen"] != "2025-05-23T00:00:00"


class TestSandboxState:
    """Tests for SandboxState per-sandbox state management."""
    
    def test_load_new_sandbox(self, tmp_path):
        """Test loading a non-existent sandbox returns empty state."""
        state = SandboxState("new-sandbox", base_path=tmp_path)
        data = state.load()
        assert data["name"] == "new-sandbox"
        assert data["budget"]["bootstrap_max"] == 5000
        assert data["budget"]["tokens_remaining"] == 5000
    
    def test_save_and_load(self, tmp_path):
        """Test saving and loading sandbox data."""
        state = SandboxState("test-sandbox", base_path=tmp_path)
        data = {
            "name": "test-sandbox",
            "path": "/dev/test",
            "budget": {"bootstrap_max": 5000, "compactions_used": 1, "tokens_remaining": 4500},
            "skills": ["python", "rust"],
            "katana": {"pending": ["task1"], "known_issues": ["issue1"]},
            "status": "running",
        }
        state.save(data=data)
        loaded = state.load()
        assert loaded["name"] == "test-sandbox"
        assert loaded["budget"]["tokens_remaining"] == 4500
        assert loaded["skills"] == ["python", "rust"]
    
    def test_update_status(self, tmp_path):
        """Test updating only the status field."""
        state = SandboxState("test-sandbox", base_path=tmp_path)
        state.save(data={"name": "test-sandbox", "budget": {}, "skills": [], "katana": {}, "status": "idle"})
        state.update_status("running")
        loaded = state.load()
        assert loaded["status"] == "running"
    
    def test_add_pending_task(self, tmp_path):
        """Test adding a pending task."""
        state = SandboxState("test-sandbox", base_path=tmp_path)
        state.add_pending_task("fix bug #123")
        loaded = state.load()
        assert "fix bug #123" in loaded["katana"]["pending"]
    
    def test_add_known_issue(self, tmp_path):
        """Test adding a known issue."""
        state = SandboxState("test-sandbox", base_path=tmp_path)
        state.add_known_issue("memory leak in worker")
        loaded = state.load()
        assert "memory leak in worker" in loaded["katana"]["known_issues"]
    
    def test_files_created_in_correct_locations(self, tmp_path):
        """Test that state files are created in the correct sandbox directory."""
        state = SandboxState("test-sandbox", base_path=tmp_path)
        state.save(data={
            "name": "test-sandbox",
            "budget": {"bootstrap_max": 5000, "compactions_used": 0, "tokens_remaining": 5000},
            "skills": [],
            "katana": {"pending": [], "known_issues": []},
            "status": "idle",
        })
        assert (tmp_path / "test-sandbox" / "BUDGET.toon").exists()
        assert (tmp_path / "test-sandbox" / "SKILLS.toon").exists()
        assert (tmp_path / "test-sandbox" / "MEMORY.toon").exists()
        assert (tmp_path / "test-sandbox" / "HEARTBEAT.toon").exists()


class TestBudgetState:
    """Tests for BudgetState budget tracking."""
    
    def test_load_default_budget(self, tmp_path):
        """Test loading a non-existent budget returns defaults."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        data = state.load()
        assert data["bootstrap_max"] == 5000
        assert data["compactions_used"] == 0
        assert data["tokens_remaining"] == 5000
    
    def test_update_field(self, tmp_path):
        """Test updating a specific budget field."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        state.update(field="tokens_remaining", value=3000)
        data = state.load()
        assert data["tokens_remaining"] == 3000
    
    def test_spawn_decrement(self, tmp_path):
        """Test spawn decrements tokens_remaining."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        new_val = state.spawn_decrement(amount=100)
        assert new_val == 4900
        data = state.load()
        assert data["tokens_remaining"] == 4900
    
    def test_spawn_decrement_caps_at_zero(self, tmp_path):
        """Test spawn decrement doesn't go below zero."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        state.update(field="tokens_remaining", value=50)
        new_val = state.spawn_decrement(amount=100)
        assert new_val == 0
    
    def test_complete_increment(self, tmp_path):
        """Test complete increments tokens_remaining."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        state.update(field="tokens_remaining", value=4900)
        new_val = state.complete_increment(amount=50)
        assert new_val == 4950
    
    def test_complete_increment_caps_at_bootstrap_max(self, tmp_path):
        """Test complete increment doesn't exceed bootstrap_max."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        state.update(field="tokens_remaining", value=5000)
        new_val = state.complete_increment(amount=100)
        assert new_val == 5000
    
    def test_compact_reset(self, tmp_path):
        """Test compact resets compactions_used."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        state.update(field="compactions_used", value=5)
        state.compact_reset()
        data = state.load()
        assert data["compactions_used"] == 0
    
    def test_record_compaction(self, tmp_path):
        """Test recording a compaction."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        count = state.record_compaction()
        assert count == 1
        count = state.record_compaction()
        assert count == 2
    
    def test_is_exhausted_false(self, tmp_path):
        """Test is_exhausted returns False when tokens remain."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        assert state.is_exhausted() is False
    
    def test_is_exhausted_true(self, tmp_path):
        """Test is_exhausted returns True when tokens are 0."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        state.update(field="tokens_remaining", value=0)
        assert state.is_exhausted() is True
    
    def test_get_remaining_ratio(self, tmp_path):
        """Test getting the remaining ratio."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        state.update(field="tokens_remaining", value=2500)
        ratio = state.get_remaining_ratio()
        assert ratio == 0.5
    
    def test_katana_cycle(self, tmp_path):
        """Test full Katana cycle: spawn -> complete -> compact."""
        state = BudgetState("test-sandbox", base_path=tmp_path)
        
        # Initial state
        initial = state.load()
        assert initial["tokens_remaining"] == 5000
        
        # Spawn decrements
        state.spawn_decrement(amount=100)
        assert state.load()["tokens_remaining"] == 4900
        
        # Complete increments
        state.complete_increment(amount=50)
        assert state.load()["tokens_remaining"] == 4950
        
        # Compact resets compactions
        state.record_compaction()
        state.record_compaction()
        assert state.load()["compactions_used"] == 2
        state.compact_reset()
        assert state.load()["compactions_used"] == 0