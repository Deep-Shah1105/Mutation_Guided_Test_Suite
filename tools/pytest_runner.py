"""Execute generated tests in a temporary subprocess and optionally collect coverage.

Subprocess isolation and timeouts are not a complete security sandbox.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _clean_env(root: Path) -> dict[str, str]:
    # Do not leak API keys or other parent-process secrets into candidate code.
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(root),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONPATH": str(root)}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _coverage_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        candidate = payload.get("files", {}).get("candidate.py", {})
        summary = candidate.get("summary", {})
        missing_lines = candidate.get("missing_lines", [])
        missing_branches = candidate.get("missing_branches", [])
        return {
            "status": "collected",
            "statement_percent": round(float(summary.get("percent_covered", 0.0)), 2),
            "branch_percent": (round(float(summary["percent_branches_covered"]), 2)
                               if summary.get("num_branches") else None),
            "covered_lines": int(summary.get("covered_lines", 0)),
            "total_lines": int(summary.get("num_statements", 0)),
            "missing_lines": missing_lines,
            "missing_branches": [f"line {pair[0]} -> line {pair[1]}" for pair in missing_branches
                                 if isinstance(pair, list) and len(pair) == 2],
            "note": "Coverage describes executed source lines and branches; it does not prove test assertions are correct.",
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "unavailable", "statement_percent": None, "branch_percent": None,
                "covered_lines": None, "total_lines": None, "missing_lines": [],
                "missing_branches": [], "note": "Coverage JSON could not be read."}


def run_pytest(source_code: str, test_code: str, timeout_seconds: int = 12,
               collect_coverage: bool = False) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mgts-test-") as temp:
        root = Path(temp)
        (root / "candidate.py").write_text(source_code, encoding="utf-8")
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_candidate.py").write_text(test_code, encoding="utf-8")
        env = _clean_env(root)
        coverage_result: dict[str, Any] = {"status": "not_requested", "statement_percent": None,
                                           "branch_percent": None, "covered_lines": None,
                                           "total_lines": None, "missing_lines": [], "missing_branches": []}
        command = [sys.executable, "-m", "pytest", "-q", "tests/test_candidate.py"]
        if collect_coverage:
            command = [sys.executable, "-m", "coverage", "run", "--branch", "--source=candidate",
                       "-m", "pytest", "-q", "tests/test_candidate.py"]
        try:
            proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True,
                                  timeout=timeout_seconds, check=False)
            output = (proc.stdout + "\n" + proc.stderr).strip()[-12000:]
            if collect_coverage:
                if proc.returncode != 0 and ("No module named coverage" in output or "No module named 'coverage'" in output):
                    # Keep test results usable even if optional coverage installation is missing.
                    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_candidate.py"],
                                           cwd=root, env=env, capture_output=True, text=True,
                                           timeout=timeout_seconds, check=False)
                    output = (proc.stdout + "\n" + proc.stderr).strip()[-12000:]
                    coverage_result = {"status": "unavailable", "statement_percent": None,
                                       "branch_percent": None, "covered_lines": None, "total_lines": None,
                                       "missing_lines": [], "missing_branches": [],
                                       "note": "Install requirements.txt to enable coverage.py."}
                else:
                    json_proc = subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "coverage.json"],
                                               cwd=root, env=env, capture_output=True, text=True,
                                               timeout=min(timeout_seconds, 8), check=False)
                    if json_proc.returncode == 0:
                        coverage_result = _coverage_summary(root / "coverage.json")
                    else:
                        coverage_result = {"status": "unavailable", "statement_percent": None,
                                           "branch_percent": None, "covered_lines": None, "total_lines": None,
                                           "missing_lines": [], "missing_branches": [],
                                           "note": (json_proc.stdout + "\n" + json_proc.stderr).strip()[-1000:]}
            return {"status": "passed" if proc.returncode == 0 else "failed",
                    "passed": proc.returncode == 0, "returncode": proc.returncode,
                    "output": output, "timeout": False, "coverage": coverage_result}
        except subprocess.TimeoutExpired as exc:
            output = ((exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
            return {"status": "timeout", "passed": False, "returncode": None,
                    "output": output[-4000:], "timeout": True, "coverage": coverage_result}
        except Exception as exc:
            return {"status": "error", "passed": False, "returncode": None,
                    "output": f"{type(exc).__name__}: {exc}", "timeout": False,
                    "coverage": coverage_result}
