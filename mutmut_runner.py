"""Run mutmut in a disposable project; if it fails, use a transparent AST-token fallback.

The fallback is intentionally small and reported as fallback_token, never as mutmut.
"""
from __future__ import annotations
import os
import re
import subprocess
import sys
import time
import tempfile
import tokenize
from io import StringIO
from pathlib import Path
from typing import Any
from tools.pytest_runner import run_pytest

OPS = {"+": "-", "-": "+", "*": "/", "/": "*", "//": "/",
       "%": "*", "==": "!=", "!=": "==", ">": ">=", ">=": ">",
       "<": "<=", "<=": "<", "and": "or", "or": "and"}


def _operator_mutants(source: str, limit: int = 24) -> list[tuple[str, str]]:
    lines = source.splitlines(keepends=True)
    mutants: list[tuple[str, str]] = []
    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        for tok in tokens:
            replacement = OPS.get(tok.string) if tok.type in (tokenize.OP, tokenize.NAME) else None
            if not replacement:
                continue
            row, col = tok.start
            end_row, end_col = tok.end
            changed = list(lines)
            if row != end_row:
                continue
            changed[row - 1] = changed[row - 1][:col] + replacement + changed[row - 1][end_col:]
            mutant = "".join(changed)
            if mutant != source:
                mutants.append((f"line {row}: {tok.string} -> {replacement}", mutant))
            if len(mutants) >= limit:
                break
    except tokenize.TokenError:
        pass
    return mutants


def _fallback_sweep(source_code: str, test_code: str, timeout_seconds: int, max_mutants: int = 24) -> dict[str, Any]:
    deadline = time.monotonic() + max(2, min(timeout_seconds, 25))
    baseline_timeout = max(1, min(8, deadline - time.monotonic()))
    baseline = run_pytest(source_code, test_code, timeout_seconds=baseline_timeout)
    if not baseline["passed"]:
        return {"status": "baseline_failed", "engine": "fallback_token", "total": 0,
                "killed": 0, "survived": [], "details": [], "baseline": baseline}
    details = []
    survivors = []
    for label, mutant_source in _operator_mutants(source_code, max_mutants):
        remaining = deadline - time.monotonic()
        if remaining < 1:
            break
        result = run_pytest(mutant_source, test_code, timeout_seconds=max(1, min(8, remaining)))
        item = {"mutant": label, "killed": not result["passed"], "test_output": result["output"][-1200:]}
        details.append(item)
        if result["passed"]:
            survivors.append(label)
    total = len(details)
    killed = sum(1 for item in details if item["killed"])
    return {"status": "completed", "engine": "fallback_token", "total": total,
            "killed": killed, "survived": survivors,
            "score_percent": round((killed / total) * 100, 2) if total else None,
            "details": details, "baseline": baseline}


def run_mutmut(source_code: str, test_code: str, timeout_seconds: int = 45,
               prefer_fallback: bool = False) -> dict[str, Any]:
    """Run mutmut, or use a reduced token-mutation fallback after supervisor recovery."""
    if prefer_fallback:
        fallback = _fallback_sweep(source_code, test_code, min(timeout_seconds, 25), max_mutants=12)
        fallback["fallback_reason"] = "Supervisor selected reduced token-mutation fallback after a prior mutmut failure."
        fallback["mutmut_attempted"] = False
        return fallback
    fallback_reason = None
    with tempfile.TemporaryDirectory(prefix="mgts-mutmut-") as temp:
        root = Path(temp)
        (root / "candidate.py").write_text(source_code, encoding="utf-8")
        tests_dir = root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_candidate.py").write_text(test_code, encoding="utf-8")
        (root / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = "candidate.py"\ntests_dir = "tests/"\n', encoding="utf-8"
        )
        # Do not pass ANTHROPIC_API_KEY or other parent secrets into mutation execution.
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(root),
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
               "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONPATH": str(root)}
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            if key in os.environ:
                env[key] = os.environ[key]
        try:
            proc = subprocess.run([sys.executable, "-m", "mutmut", "run"], cwd=root,
                                  env=env, capture_output=True, text=True,
                                  timeout=timeout_seconds, check=False)
            run_output = (proc.stdout + "\n" + proc.stderr).strip()[-12000:]
            if proc.returncode == 0:
                result_proc = subprocess.run([sys.executable, "-m", "mutmut", "results"], cwd=root,
                                             env=env, capture_output=True, text=True,
                                             timeout=min(timeout_seconds, 15), check=False)
                results_text = (result_proc.stdout + "\n" + result_proc.stderr).strip()[-12000:]
                survivors = [line.strip() for line in results_text.splitlines()
                             if line.strip() and ("candidate.py" in line or "candidate." in line)]
                summary = re.search(r"(?:killed|killed mutants?)\D+(\d+).*?(?:total|mutants?)\D+(\d+)",
                                    run_output, flags=re.I | re.S)
                if summary:
                    killed, total = int(summary.group(1)), int(summary.group(2))
                else:
                    killed, total = None, None
                return {"status": "completed", "engine": "mutmut", "total": total,
                        "killed": killed, "survived": survivors, "results_output": results_text,
                        "run_output": run_output,
                        "score_percent": round(killed / total * 100, 2) if total else None}
            fallback_reason = f"mutmut exit code {proc.returncode}: {run_output[-2500:]}"
        except subprocess.TimeoutExpired:
            fallback_reason = f"mutmut exceeded {timeout_seconds}s timeout"
        except Exception as exc:
            fallback_reason = f"mutmut invocation failed: {type(exc).__name__}: {exc}"
    return {"status": "error", "engine": "mutmut", "total": None, "killed": None,
            "survived": [], "score_percent": None, "fallback_reason": fallback_reason,
            "mutmut_attempted": True}
