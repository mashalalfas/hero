"""Tests for hero prompt template system."""

import pytest

from hero.prompts.loader import _resolve_template, load_rule, render_template


class TestResolveTemplate:
    def test_loads_bundled_default_soldier(self):
        content = _resolve_template("roles/soldier.md")
        assert "HERO army" in content
        assert "$sandbox" in content

    def test_loads_bundled_default_architect(self):
        content = _resolve_template("roles/architect.md")
        assert "architect" in content.lower()

    def test_loads_bundled_default_researcher(self):
        content = _resolve_template("roles/researcher.md")
        assert "research" in content.lower()

    def test_loads_bundled_default_archivist(self):
        content = _resolve_template("roles/archivist.md")
        assert "Archivist" in content

    def test_loads_bundled_default_utility(self):
        content = _resolve_template("roles/utility.md")
        assert "utility" in content.lower()

    def test_loads_bundled_default_communicator(self):
        content = _resolve_template("roles/communicator.md")
        assert "Communicator" in content

    def test_loads_bundled_default_lead(self):
        content = _resolve_template("roles/lead.md")
        assert "Lead" in content

    def test_loads_phase_verify(self):
        content = _resolve_template("phases/verify.md")
        assert "Verify" in content

    def test_loads_phase_fix(self):
        content = _resolve_template("phases/fix.md")
        assert "Fix Agent" in content

    def test_loads_phase_archive(self):
        content = _resolve_template("phases/archive.md")
        assert "Archivist" in content

    def test_loads_rule_tdd(self):
        content = _resolve_template("rules/tdd.md")
        assert "Red-Green-Refactor" in content

    def test_loads_rule_context_budget(self):
        content = _resolve_template("rules/context-budget.md")
        assert "5k tokens" in content

    def test_user_override_takes_priority(self, tmp_path, monkeypatch):
        user_dir = tmp_path / "prompts"
        role_file = user_dir / "roles" / "soldier.md"
        role_file.parent.mkdir(parents=True)
        role_file.write_text("Custom soldier template for $sandbox")
        monkeypatch.setattr("hero.prompts.loader.PROMPTS_DIR", user_dir)

        content = _resolve_template("roles/soldier.md")
        assert "Custom soldier template" in content

    def test_raises_on_missing_template(self):
        with pytest.raises(FileNotFoundError):
            _resolve_template("roles/nonexistent.md")


class TestRenderTemplate:
    def test_renders_soldier_template(self):
        prompt = render_template(
            "roles/soldier.md",
            sandbox="test-sandbox",
            workdir="/tmp/test",
            model="step-3.5-flash",
            context_window=128000,
            max_tokens=8000,
            budget=5000,
            task="fix the bug",
            extra_rules="",
        )
        assert "test-sandbox" in prompt
        assert "fix the bug" in prompt
        assert "step-3.5-flash" in prompt

    def test_renders_architect_template(self):
        prompt = render_template(
            "roles/architect.md",
            sandbox="my-app",
            workdir="/tmp/my-app",
            model="glm-5.1",
            context_window=1000000,
            task="design auth system",
            extra_rules="",
        )
        assert "my-app" in prompt
        assert "glm-5.1" in prompt

    def test_renders_verify_template(self):
        prompt = render_template(
            "phases/verify.md",
            sandbox="my-sandbox",
            original_task="fix tests",
            checks="1. Analyze: flutter analyze\n2. Build: flutter build",
        )
        assert "my-sandbox" in prompt
        assert "flutter analyze" in prompt

    def test_renders_fix_template(self):
        prompt = render_template(
            "phases/fix.md",
            sandbox="app",
            task="fix lint errors",
            verify_task_id="abc123",
        )
        assert "app" in prompt
        assert "abc123" in prompt

    def test_renders_archive_template(self):
        prompt = render_template(
            "phases/archive.md",
            sandbox="proj",
            task="add dark mode",
            sandbox_path="/tmp/proj",
            date="2026-05-26",
            date_time="2026-05-26 14:30",
            task_short="add dark mode",
        )
        assert "proj" in prompt
        assert "2026-05-26" in prompt

    def test_extra_rules_injected(self):
        prompt = render_template(
            "roles/soldier.md",
            sandbox="test",
            workdir="/tmp",
            model="step-3.5-flash",
            context_window=128000,
            max_tokens=8000,
            budget=5000,
            task="do something",
            extra_rules="CUSTOM RULE: always use tabs",
        )
        assert "CUSTOM RULE: always use tabs" in prompt

    def test_missing_variable_keeps_dollar(self):
        prompt = render_template("roles/soldier.md", sandbox="test")
        # safe_substitute leaves unresolved $vars as-is
        assert "$" in prompt


class TestLoadRule:
    def test_loads_tdd_rule(self):
        rule = load_rule("tdd")
        assert "Red-Green-Refactor" in rule

    def test_loads_context_budget_rule(self):
        rule = load_rule("context-budget")
        assert "5k tokens" in rule

    def test_returns_empty_for_missing_rule(self):
        rule = load_rule("nonexistent-rule-xyz")
        assert rule == ""
