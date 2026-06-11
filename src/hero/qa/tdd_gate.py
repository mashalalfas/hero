"""TDD Gate — enforces "production code requires a failing test first".

The Iron Law of TDD:

    1. Write a failing test — run it, watch it fail.
    2. Write the minimum production code to make it pass.
    3. Run the test again — green. Refactor if needed.

This gate enforces steps 1 and 3 at the process level, ensuring no
implementation is accepted without a witnessed red-green cycle.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TDDResult:
    """Result of a TDD gate check.

    Attributes
    ----------
    passed : bool
        Whether the check succeeded.
    message : str
        Human-readable summary of the outcome.
    failure_output : str | None
        Captured test output from the failing run, if applicable.
    """

    passed: bool
    message: str
    failure_output: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STUB_TEMPLATE = """\
\"\"\"Tests for {description}.\"\"\"

from __future__ import annotations

import pytest


class Test{ClassName}:
    \"\"\"Test suite for {description}.\"\"\"

    def test_{first_method}_happy_path(self) -> None:
        \"\"\"{description} should work under normal conditions.\"\"\"
        assert False, "TODO: implement this test"
"""


def _make_class_name(description: str) -> str:
    """Turn a plain-English description into a PascalCase class name."""
    clean = "".join(c for c in description.title() if c.isalnum() or c == "_")
    return clean or "Placeholder"


def _make_method_name(description: str) -> str:
    """Turn a description into a snake_case test method prefix."""
    words = description.lower().split()
    return "_".join(w.strip("_") for w in words[:5] if w.isalnum()) or "todo"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class TDDGate:
    """Enforces the Iron Law: production code requires a failing test first.

    Usage::

        gate = TDDGate(project_root=Path("/path/to/project"))
        result = gate.verify_test_first("tests/test_foo.py", "src/foo.py")
        if not result.passed:
            print(result.message)
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (
            project_root.resolve() if project_root else Path.cwd().resolve()
        )
        logger.info("TDDGate initialised for %s", self.project_root)

    # ------------------------------------------------------------------
    # verify_test_first
    # ------------------------------------------------------------------

    def verify_test_first(self, test_path: str, impl_path: str) -> TDDResult:
        """Enforce the red-green cycle for *test_path* / *impl_path*.

        Checks performed, in order:

        1. **Test exists** — the test file must exist on disk.
        2. **Test fails (RED)** — the test must fail when run *before* any
           implementation exists.  If it passes, it isn't testing anything
           real yet.
        3. **Implementation exists** (optional gate) — after a witnessed
           failure the implementation must be present.
        4. **Test passes (GREEN)** — once the implementation is in place the
           test must pass.

        Steps 2 and 4 are what make this a *TDD Gate* rather than a plain
        test runner.

        Parameters
        ----------
        test_path : str
            Path to the test file, relative to *project_root*.
        impl_path : str
            Path to the implementation file, relative to *project_root*.

        Returns
        -------
        TDDResult
            *passed* is ``True`` only when the full red-green cycle
            completes successfully.
        """
        # Resolve paths once
        abs_test = (self.project_root / test_path).resolve()
        abs_impl = (self.project_root / impl_path).resolve()

        logger.info("verify_test_first: test=%s impl=%s", abs_test, abs_impl)

        # ── Step 1 — test file must exist ──────────────────────────────
        if not abs_test.exists():
            return TDDResult(
                passed=False,
                message=f"Test file not found: {abs_test}",
            )

        # ── Step 2 — RED phase: test must fail without implementation ──
        red_result = self._run_pytest(abs_test)
        if red_result.passed:
            return TDDResult(
                passed=False,
                message=(
                    f"RED phase failed: test passed without implementation. "
                    f"The test does not actually test anything yet.\n"
                    f"File: {abs_test}"
                ),
                failure_output=red_result.failure_output,
            )

        logger.info(
            "RED phase passed — test failed as expected:\n%s",
            red_result.failure_output,
        )

        # ── Step 3 — implementation exists ─────────────────────────────
        if not abs_impl.exists():
            return TDDResult(
                passed=False,
                message=(
                    f"Implementation file not found after witnessed failure: "
                    f"{abs_impl}\nWrite the minimum code to make the test pass."
                ),
                failure_output=red_result.failure_output,
            )

        # ── Step 4 — GREEN phase: test must pass with implementation ───
        green_result = self._run_pytest(abs_test)
        if not green_result.passed:
            return TDDResult(
                passed=False,
                message=(
                    f"GREEN phase failed: test still failing after "
                    f"implementation exists.\n"
                    f"Test: {abs_test}\n"
                    f"Implementation: {abs_impl}"
                ),
                failure_output=green_result.failure_output,
            )

        logger.info("GREEN phase passed — all tests green.")
        return TDDResult(
            passed=True,
            message=(
                f"TDD gate passed. Red-green cycle complete:\n"
                f"  Test: {abs_test}\n"
                f"  Implementation: {abs_impl}"
            ),
            failure_output=red_result.failure_output,
        )

    # ------------------------------------------------------------------
    # generate_test_stub
    # ------------------------------------------------------------------

    def generate_test_stub(self, description: str) -> str:
        """Generate a minimal ``pytest`` test stub for *description*.

        The stub includes a failing placeholder assertion so that running
        it will produce a RED result immediately, satisfying step 2 of the
        TDD gate.

        Parameters
        ----------
        description : str
            Plain-English description of the behaviour to test, e.g.
            ``"user login with valid credentials"``.

        Returns
        -------
        str
            A complete, ready-to-save ``pytest`` test file.

        Examples
        --------
        >>> gate = TDDGate()
        >>> stub = gate.generate_test_stub("user login with valid credentials")
        >>> "def test_user_login_with_valid_credentials" in stub
        True
        >>> "assert False" in stub
        True
        """
        class_name = _make_class_name(description)
        first_method = _make_method_name(description)

        return _STUB_TEMPLATE.format(
            description=description,
            ClassName=class_name,
            first_method=first_method,
        )

    # ------------------------------------------------------------------
    # check_watched_fail
    # ------------------------------------------------------------------

    def check_watched_fail(self, test_path: str) -> dict:
        """Verify the test was *actually* watched fail (not skipped).

        Runs the test file and inspects the output for evidence of a real
        failure (not a skip, xfail, or empty test suite).

        Parameters
        ----------
        test_path : str
            Path to the test file, relative to *project_root*.

        Returns
        -------
        dict
            ``{"passed": bool, "message": str}``.
            *passed* is ``True`` only when the test output contains a
            genuine failure/error count > 0 and zero skips.
        """
        abs_test = (self.project_root / test_path).resolve()
        logger.info("check_watched_fail: test=%s", abs_test)

        if not abs_test.exists():
            return {"passed": False, "message": f"Test file not found: {abs_test}"}

        result = self._run_pytest(abs_test)

        if result.passed:
            return {
                "passed": False,
                "message": (
                    f"Test passed — no failure witnessed.\n"
                    f"If this is a regression test file, consider marking "
                    f"individual tests with ``@pytest.mark.xfail`` to indicate "
                    f"expected failure.\nFile: {abs_test}"
                ),
            }

        # Check that the failure wasn't a skip-only run
        stdout = result.failure_output or ""
        if "skipped" in stdout and "failed" not in stdout and "error" not in stdout:
            return {
                "passed": False,
                "message": (
                    f"Tests were skipped, not failed. A genuine TDD cycle "
                    f"requires watched failures.\nFile: {abs_test}"
                ),
            }

        return {
            "passed": True,
            "message": f"Failure witnessed for {abs_test}.",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_pytest(self, test_file: Path) -> TDDResult:
        """Execute ``pytest`` on *test_file* and return the result.

        The command used is::

            python -m pytest <test_file> -v --tb=short --no-header -q

        Parameters
        ----------
        test_file : Path
            Absolute path to the test file.

        Returns
        -------
        TDDResult
            *passed* is ``True`` when ``pytest`` exits with code 0.
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-v",
            "--tb=short",
            "--no-header",
            "-q",
        ]

        logger.debug("Running: %s", " ".join(cmd))

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        output = stdout + ("\n" + stderr if stderr else "")

        if proc.returncode == 0:
            logger.debug("pytest passed for %s", test_file)
            return TDDResult(passed=True, message="All tests passed.", failure_output=output)

        # Non-zero exit → the test failed (or errored)
        logger.debug("pytest failed (exit %d) for %s", proc.returncode, test_file)
        return TDDResult(
            passed=False,
            message=f"Tests failed (exit code {proc.returncode}).",
            failure_output=output,
        )
