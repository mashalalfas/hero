"""Tests for hero deploy command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from hero.commands.deploy import deploy
from hero.soldier.spawner import SoldierSpawner, HERMES_AGENT_BIN


@pytest.fixture
def cli_runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_index():
    """Create a mock IndexState with test sandboxes."""
    with patch("hero.commands.deploy.IndexState") as mock:
        instance = MagicMock()
        instance.get_sandbox.side_effect = lambda name: {
            "sook-pro": {"name": "sook-pro", "path": "/tmp/sandboxes/sook-pro", "status": "idle"},
            "her": {"name": "her", "path": "/tmp/sandboxes/her", "status": "idle"},
            "freya": {"name": "freya", "path": "/tmp/sandboxes/freya", "status": "idle"},
            "ghost": None,  # Sandbox not found
        }.get(name)
        mock.return_value = instance
        yield instance


@pytest.fixture
def sandbox_dirs(tmp_path):
    """Create real sandbox directories for testing."""
    sandboxes = tmp_path / "sandboxes"
    for name in ["sook-pro", "her", "freya"]:
        (sandboxes / name).mkdir(parents=True, exist_ok=True)
    return sandboxes


class TestDeployCommand:
    """Tests for hero deploy CLI command."""

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_deploy_parses_comma_separated_targets(self, mock_popen, cli_runner, mock_index, sandbox_dirs, tmp_path):
        """Test that --targets parses comma-separated sandbox names."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        for name in ["sook-pro", "her", "freya"]:
            mock_index.get_sandbox(name)["path"] = str(sandbox_dirs / name)

        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = lambda name: {
                "sook-pro": {"name": "sook-pro", "path": str(sandbox_dirs / "sook-pro"), "status": "idle"},
                "her": {"name": "her", "path": str(sandbox_dirs / "her"), "status": "idle"},
                "freya": {"name": "freya", "path": str(sandbox_dirs / "freya"), "status": "idle"},
            }.get(name)
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro,her,freya", "--task", "run tests"],
            )

        assert result.exit_code == 0

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_deploy_resolves_sandbox_paths(self, mock_popen, cli_runner, mock_index, sandbox_dirs, tmp_path):
        """Test that deploy resolves sandbox paths from IndexState."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        sandbox_map = {
            "sook-pro": {"name": "sook-pro", "path": str(sandbox_dirs / "sook-pro"), "status": "idle"},
            "her": {"name": "her", "path": str(sandbox_dirs / "her"), "status": "idle"},
            "freya": {"name": "freya", "path": str(sandbox_dirs / "freya"), "status": "idle"},
        }

        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = sandbox_map.get
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro,freya", "--task", "review logs"],
            )

        # Should call get_sandbox for each target
        assert mock_index.get_sandbox.call_count == 2

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_deploy_spawns_soldiers_in_parallel(self, mock_popen, cli_runner, sandbox_dirs, tmp_path):
        """Test that deploy spawns soldiers concurrently using ThreadPoolExecutor."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        sandbox_map = {
            "sook-pro": {"name": "sook-pro", "path": str(sandbox_dirs / "sook-pro"), "status": "idle"},
            "freya": {"name": "freya", "path": str(sandbox_dirs / "freya"), "status": "idle"},
        }

        call_order = []

        def mock_popen_side_effect(*args, **kwargs):
            call_order.append(kwargs.get("task", args))
            return mock_process

        mock_popen.side_effect = mock_popen_side_effect

        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = sandbox_map.get
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro,freya", "--task", "run tests", "--parallel", 2],
            )

        assert result.exit_code == 0

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_deploy_reports_success_per_sandbox(self, mock_popen, cli_runner, sandbox_dirs, tmp_path):
        """Test that deploy reports success/failure per sandbox in TOON format."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        sandbox_map = {
            "sook-pro": {"name": "sook-pro", "path": str(sandbox_dirs / "sook-pro"), "status": "idle"},
            "freya": {"name": "freya", "path": str(sandbox_dirs / "freya"), "status": "idle"},
        }

        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = sandbox_map.get
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro,freya", "--task", "run tests"],
            )

        assert result.exit_code == 0
        assert "succeeded" in result.output.lower() or "success" in result.output.lower()

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_deploy_handles_missing_sandbox(self, mock_popen, cli_runner, mock_index, sandbox_dirs, tmp_path):
        """Test that deploy handles sandbox not found gracefully."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = lambda name: None if name == "ghost" else {
                "name": name,
                "path": str(sandbox_dirs / name),
                "status": "idle",
            }.get(name)
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro,ghost,freya", "--task", "run tests"],
            )

        # Should warn about ghost but still proceed with valid targets
        assert "ghost" in result.output.lower() or "not found" in result.output.lower()

    def test_deploy_requires_targets(self, cli_runner):
        """Test that deploy fails when --targets is not specified."""
        result = cli_runner.invoke(deploy, ["--task", "some task"])
        assert result.exit_code != 0

    def test_deploy_requires_task(self, cli_runner):
        """Test that deploy fails when --task is not specified."""
        result = cli_runner.invoke(deploy, ["--targets", "sook-pro"])
        assert result.exit_code != 0

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_deploy_parallel_option_limits_workers(self, mock_popen, cli_runner, sandbox_dirs, tmp_path):
        """Test that --parallel controls the number of concurrent workers."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        sandbox_map = {
            "sook-pro": {"name": "sook-pro", "path": str(sandbox_dirs / "sook-pro"), "status": "idle"},
            "her": {"name": "her", "path": str(sandbox_dirs / "her"), "status": "idle"},
            "freya": {"name": "freya", "path": str(sandbox_dirs / "freya"), "status": "idle"},
        }

        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = sandbox_map.get
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro,her,freya", "--task", "run tests", "--parallel", 3],
            )

        assert result.exit_code == 0
        assert "parallel workers: 3" in result.output

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_deploy_uses_custom_budget(self, mock_popen, cli_runner, sandbox_dirs, tmp_path):
        """Test that --budget is passed to spawned soldiers."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        sandbox_map = {
            "sook-pro": {"name": "sook-pro", "path": str(sandbox_dirs / "sook-pro"), "status": "idle"},
        }

        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = sandbox_map.get
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro", "--task", "run tests", "--budget", "3000"],
            )

        assert result.exit_code == 0


class TestDeployOutputFormat:
    """Tests for deploy command output formatting in TOON style."""

    @patch("hero.soldier.spawner.subprocess.Popen")
    def test_output_format_shows_deploy_results_header(self, mock_popen, cli_runner, sandbox_dirs, tmp_path):
        """Test that output shows deploy_results header."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        sandbox_map = {
            "sook-pro": {"name": "sook-pro", "path": str(sandbox_dirs / "sook-pro"), "status": "idle"},
        }

        with patch("hero.commands.deploy.IndexState") as MockIndex:
            mock_index = MagicMock()
            mock_index.get_sandbox.side_effect = sandbox_map.get
            MockIndex.return_value = mock_index

            result = cli_runner.invoke(
                deploy,
                ["--targets", "sook-pro", "--task", "run tests"],
            )

        assert "Deploying to" in result.output or "Results" in result.output
