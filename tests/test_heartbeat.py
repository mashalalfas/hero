"""Tests for soldier heartbeat monitoring system."""

from pathlib import Path

import pytest

from hero.soldier.heartbeat import HeartbeatState, HeartbeatData, STALE_THRESHOLD


class TestHeartbeatState:
    """Tests for HeartbeatState class."""

    def test_create_heartbeat(self, tmp_path):
        """Test creating a new heartbeat file."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        hb = state.create("soldier-123")

        assert hb.soldier_id == "soldier-123"
        assert hb.sandbox_name == "test-sandbox"
        assert hb.status == "active"
        assert hb.missed_count == 0
        assert hb.started_at != ""
        assert hb.last_ping != ""

        # Verify file was created
        assert state.heartbeat_file.exists()

    def test_ping_updates_timestamp(self, tmp_path):
        """Test that ping() updates last_ping and resets missed_count."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        # Miss a few times first
        state.miss()
        state.miss()

        hb = state.ping("soldier-123")

        assert hb is not None
        assert hb.missed_count == 0
        assert hb.status == "active"

    def test_ping_wrong_soldier_id_returns_none(self, tmp_path):
        """Test that ping() returns None for wrong soldier_id."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        result = state.ping("wrong-soldier")

        assert result is None

    def test_ping_no_heartbeat_returns_none(self, tmp_path):
        """Test that ping() returns None when no heartbeat exists."""
        state = HeartbeatState("nonexistent", base_path=tmp_path)

        result = state.ping("any-soldier")

        assert result is None

    def test_miss_increments_count(self, tmp_path):
        """Test that miss() increments missed_count."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        hb = state.miss()

        assert hb is not None
        assert hb.missed_count == 1

    def test_miss_marks_stale_at_threshold(self, tmp_path):
        """Test that miss() marks stale when threshold reached."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        # Miss STALE_THRESHOLD times (3 by default)
        for _ in range(STALE_THRESHOLD - 1):
            hb = state.miss()
            assert hb is not None
            assert hb.status == "active"

        # The STALE_THRESHOLD-th miss should mark as stale
        hb = state.miss()
        assert hb is not None
        assert hb.status == "stale"
        assert hb.missed_count == STALE_THRESHOLD

    def test_complete_marks_completed(self, tmp_path):
        """Test that complete() marks status as completed."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        hb = state.complete()

        assert hb is not None
        assert hb.status == "completed"

    def test_get_heartbeat_returns_data(self, tmp_path):
        """Test that get_heartbeat() returns HeartbeatData."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        hb = state.get_heartbeat()

        assert hb is not None
        assert hb.soldier_id == "soldier-123"

    def test_get_heartbeat_none_when_not_exists(self, tmp_path):
        """Test that get_heartbeat() returns None when no heartbeat exists."""
        state = HeartbeatState("nonexistent", base_path=tmp_path)

        hb = state.get_heartbeat()

        assert hb is None

    def test_is_stale_true_when_stale(self, tmp_path):
        """Test that is_stale() returns True for stale soldiers."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        # Miss enough times to become stale
        for _ in range(STALE_THRESHOLD):
            state.miss()

        assert state.is_stale() is True

    def test_is_stale_false_when_active(self, tmp_path):
        """Test that is_stale() returns False for active soldiers."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")

        assert state.is_stale() is False

    def test_is_stale_false_when_completed(self, tmp_path):
        """Test that is_stale() returns False for completed soldiers."""
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        state.create("soldier-123")
        state.complete()

        assert state.is_stale() is False


class TestHeartbeatStateStaticMethods:
    """Tests for HeartbeatState static methods."""

    def test_get_stale_sandboxes_finds_stale(self, tmp_path):
        """Test get_stale_sandboxes() finds sandboxes with stale soldiers."""
        # Create two sandboxes, one stale, one active
        state1 = HeartbeatState("stale-sandbox", base_path=tmp_path)
        state1.create("soldier-1")
        for _ in range(STALE_THRESHOLD):
            state1.miss()

        state2 = HeartbeatState("active-sandbox", base_path=tmp_path)
        state2.create("soldier-2")

        stale = HeartbeatState.get_stale_sandboxes(base_path=tmp_path)

        assert "stale-sandbox" in stale
        assert "active-sandbox" not in stale

    def test_get_stale_sandboxes_empty_when_none(self, tmp_path):
        """Test get_stale_sandboxes() returns empty list when none stale."""
        state = HeartbeatState("active-sandbox", base_path=tmp_path)
        state.create("soldier-1")

        stale = HeartbeatState.get_stale_sandboxes(base_path=tmp_path)

        assert stale == []

    def test_get_stale_sandboxes_ignores_nonexistent_dirs(self, tmp_path):
        """Test get_stale_sandboxes() handles non-existent base path."""
        stale = HeartbeatState.get_stale_sandboxes(base_path=tmp_path / "nonexistent")

        assert stale == []

    def test_get_all_heartbeats_returns_all(self, tmp_path):
        """Test get_all_heartbeats() returns data for all sandboxes."""
        state1 = HeartbeatState("sandbox-1", base_path=tmp_path)
        state1.create("soldier-1")

        state2 = HeartbeatState("sandbox-2", base_path=tmp_path)
        state2.create("soldier-2")

        all_hb = HeartbeatState.get_all_heartbeats(base_path=tmp_path)

        assert len(all_hb) == 2
        assert "sandbox-1" in all_hb
        assert "sandbox-2" in all_hb
        assert all_hb["sandbox-1"].soldier_id == "soldier-1"
        assert all_hb["sandbox-2"].soldier_id == "soldier-2"

    def test_get_all_heartbeats_empty_when_none(self, tmp_path):
        """Test get_all_heartbeats() returns empty dict when none exist."""
        all_hb = HeartbeatState.get_all_heartbeats(base_path=tmp_path)

        assert all_hb == {}


class TestHeartbeatData:
    """Tests for HeartbeatData dataclass."""

    def test_heartbeat_data_defaults(self):
        """Test HeartbeatData default values."""
        hb = HeartbeatData(
            soldier_id="test-123",
            sandbox_name="test-sandbox",
            started_at="2025-01-01T00:00:00",
            last_ping="2025-01-01T00:00:00",
        )

        assert hb.missed_count == 0
        assert hb.status == "active"

    def test_heartbeat_data_custom_values(self):
        """Test HeartbeatData with custom values."""
        hb = HeartbeatData(
            soldier_id="test-123",
            sandbox_name="test-sandbox",
            started_at="2025-01-01T00:00:00",
            last_ping="2025-01-01T00:00:00",
            missed_count=5,
            status="stale",
        )

        assert hb.missed_count == 5
        assert hb.status == "stale"


class TestSpawnerCreatesHeartbeat:
    """Tests for heartbeat creation during soldier spawn."""

    def test_launch_creates_heartbeat(self, tmp_path):
        """Test that SoldierSpawner.launch() creates a heartbeat."""
        from unittest.mock import MagicMock, patch
        from hero.soldier.spawner import SoldierSpawner, HERMES_AGENT_BIN
        from hero.soldier.context import BudgetConfig

        # Mock subprocess.Popen so we don't actually spawn hermes-agent
        mock_popen = MagicMock()
        mock_popen.return_value.pid = 12345
        with patch("hero.soldier.spawner.subprocess.Popen", mock_popen):
            spawner = SoldierSpawner(tmp_path / "test-sandbox")
            spawner.sandbox_path.mkdir()

            soldier_id = spawner.launch(
                task="test task",
                budget=BudgetConfig(
                    bootstrap_max=5000, compactions_used=0, tokens_remaining=5000
                ),
            )

        # Check heartbeat was created
        heartbeat_file = tmp_path / "test-sandbox" / "HEARTBEAT.toon"
        assert heartbeat_file.exists()

        # Verify the soldier_id matches
        state = HeartbeatState("test-sandbox", base_path=tmp_path)
        hb = state.get_heartbeat()
        assert hb is not None
        assert hb.soldier_id == soldier_id
        assert hb.status == "active"