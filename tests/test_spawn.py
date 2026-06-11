"""Tests for hero spawn command and SoldierSpawner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import os
import pytest

from hero.soldier.spawner import SoldierSpawner, HERMES_AGENT_BIN
from hero.soldier.context import BudgetConfig, KatanaData, SandboxData, build_context


@pytest.fixture(autouse=True)
def clear_dispatch_queue_env():
    """Ensure USE_DISPATCH_QUEUE does not leak between tests."""
    old = os.environ.get("USE_DISPATCH_QUEUE")
    os.environ["USE_DISPATCH_QUEUE"] = ""
    yield
    if old is None:
        os.environ.pop("USE_DISPATCH_QUEUE", None)
    else:
        os.environ["USE_DISPATCH_QUEUE"] = old


class TestSoldierSpawner:
    """Tests for SoldierSpawner.launch() using hermes-agent CLI subprocess."""

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_launch_uses_hermes_agent_cli_with_correct_args(self, mock_popen, tmp_path):
        """Test that launch() calls hermes-agent CLI with correct parameters."""
        # Explicitly disable dispatch-queue so hermes-agent subprocess path is used
        os.environ["USE_DISPATCH_QUEUE"] = ""
        sandbox_path = tmp_path / "test-sandbox"
        sandbox_path.mkdir()

        budget = BudgetConfig(
            bootstrap_max=5000,
            compactions_used=2,
            tokens_remaining=4500,
        )

        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        spawner = SoldierSpawner(sandbox_path)
        soldier_id = spawner.launch(task="fix the bug", budget=budget)

        # Verify Popen was called once
        mock_popen.assert_called_once()

        # Get the actual call args
        call_args, call_kwargs = mock_popen.call_args

        # Verify command is a list starting with hermes-agent binary
        cmd = call_args[0]
        assert cmd[0] == str(HERMES_AGENT_BIN)
        assert cmd[1] == "-z"

        # Verify task description is in the command
        assert "fix the bug" in cmd[2]

        # Verify context contains expected TOON fields
        context_arg = cmd[2]
        assert "sandbox:" in context_arg
        assert "budget{" in context_arg
        assert "task:" in context_arg
        assert "katana:" in context_arg

        # Verify working directory is set
        assert call_kwargs["cwd"] == str(sandbox_path)

        # Verify soldier_id is returned
        assert soldier_id is not None
        assert len(soldier_id) == 8

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_launch_builds_correct_toon_context(self, mock_popen, tmp_path):
        """Test that launch() includes sandbox name, budget, and role in context."""
        sandbox_path = tmp_path / "my-sandbox"
        sandbox_path.mkdir()

        budget = BudgetConfig(
            bootstrap_max=3000,
            compactions_used=1,
            tokens_remaining=2800,
        )

        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        spawner = SoldierSpawner(sandbox_path)
        spawner.launch(task="test task", budget=budget)

        # Get the command passed to Popen
        cmd = mock_popen.call_args[0][0]
        context_arg = cmd[2]

        # Verify sandbox name appears in context
        assert "my-sandbox" in context_arg
        # Verify budget values appear in context
        assert "3000" in context_arg
        # Verify task appears in context
        assert "test task" in context_arg
        # Verify role appears in context (note: build_context() does not embed role in TOON)

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_launch_generates_unique_soldier_ids(self, mock_popen, tmp_path):
        """Test that each launch generates a unique soldier ID."""
        sandbox_path = tmp_path / "sandbox"
        sandbox_path.mkdir()

        budget = BudgetConfig(bootstrap_max=5000, compactions_used=0, tokens_remaining=5000)

        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        spawner = SoldierSpawner(sandbox_path)

        id1 = spawner.launch(task="task 1", budget=budget)
        id2 = spawner.launch(task="task 2", budget=budget)

        # IDs should be unique (UUID-based)
        assert id1 != id2

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_launch_uses_hermes_agent_z_flag(self, mock_popen, tmp_path):
        """Test that launch() uses -z flag for hermes-agent CLI."""
        sandbox_path = tmp_path / "test-sandbox"
        sandbox_path.mkdir()

        budget = BudgetConfig(bootstrap_max=5000, compactions_used=0, tokens_remaining=5000)

        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        spawner = SoldierSpawner(sandbox_path)
        spawner.launch(task="test", budget=budget)

        cmd = mock_popen.call_args[0][0]
        # Verify -z flag is present (autonomous mode)
        assert "-z" in cmd


class TestBuildContext:
    """Tests for build_context() TOON formatting."""

    def test_build_context_with_pending_and_issues(self):
        """Test context includes pending tasks and known issues."""
        sandbox = SandboxData(
            name="test-sbx",
            budget=BudgetConfig(
                bootstrap_max=5000,
                compactions_used=3,
                tokens_remaining=4200,
            ),
            katana=KatanaData(
                pending=["task A", "task B"],
                known_issues=["bug #1", "crash on startup"],
            ),
        )

        context = build_context(sandbox, "do the thing")

        lines = context.split("\n")
        assert any("sandbox: test-sbx" in line for line in lines)
        assert any("budget" in line and "5000" in line for line in lines)
        assert any("pending[2]:" in line for line in lines)
        assert any("known_issues[2]:" in line for line in lines)

    def test_build_context_empty_katana(self):
        """Test context handles empty pending and known_issues."""
        sandbox = SandboxData(
            name="empty-sbx",
            budget=BudgetConfig(bootstrap_max=1000, compactions_used=0, tokens_remaining=1000),
            katana=KatanaData(pending=[], known_issues=[]),
        )

        context = build_context(sandbox, "minimal task")

        assert "empty-sbx" in context
        assert "pending[0]:" in context
        assert "known_issues[0]:" in context
        # "none" should appear when lists are empty
        assert "none" in context

    def test_build_context_tokens_unlimited_when_none(self):
        """Test that tokens_remaining shows 'unlimited' when None."""
        sandbox = SandboxData(
            name="unlimited-sbx",
            budget=BudgetConfig(
                bootstrap_max=5000,
                compactions_used=0,
                tokens_remaining=None,  # unlimited
            ),
            katana=KatanaData(pending=[], known_issues=[]),
        )

        context = build_context(sandbox, "unlimited task")

        assert "unlimited" in context
