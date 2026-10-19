"""Run mutmut where supported, with a clearly labelled reduced mutation fallback.

mutmut does not support native Windows execution; on Windows the runner uses the
fallback directly and explains how to get a full mutmut run (WSL/Linux/Docker).
"""
from __future__ import annotations
import ast
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
       "%": "*", "**": "*", "==": "!=", "!=": "==", ">": ">=",
       ">=": ">", "<": "<=", "<=": "<", "and": "or", "or": "and"}


def _numeric_replacements(value: str) -> list[str]:
    try:
        number = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        return []
    candidates = []
    for replacement in ("0", "1", str(number + 1), str(number - 1)):
        if replacement != value and replacement not in candidates:
            candidates.append(replacement)
    return candidates[:2]


def _operator_mutants(source: str, limit: int = 48) -> list[tuple[str, str]]:
    """Generate bounded token mutations for operators, boolean literals and numbers."""
    lines = source.splitlines(keepends=True)
    mutants: list[tuple[str, str]] = []
    seen_sources = {source}
    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        for tok in tokens:
            replacements: list[tuple[str, str]] = []
            if tok.type == tokenize.OP and tok.string in OPS:
                replacements.append((OPS[tok.string], f"{tok.string} -> {OPS[tok.string]}"))
            elif tok.type == tokenize.NAME:
                if tok.string in ("and", "or"):
                    replacement = OPS[tok.string]
                    replacements.append((replacement, f"{tok.string} -> {replacement}"))
                elif tok.string == "True":
                    replacements.append(("False", "True -> False"))
                elif tok.string == "False":
                    replacements.append(("True", "False -> True"))
            elif tok.type == tokenize.NUMBER:
                replacements.extend((replacement, f"constant {tok.string} -> {replacement}")
                                    for replacement in _numeric_replacements(tok.string))
            if not replacements:
                continue
            row, col = tok.start
            end_row, end_col = tok.end
            if row != end_row:
                continue
            for replacement, label in replacements:
                changed = list(lines)
                changed[row - 1] = changed[row - 1][:col] + replacement + changed[row - 1][end_col:]
                mutant_source = "".join(changed)
                if mutant_source in seen_sources:
                    continue
                seen_sources.add(mutant_source)
                mutants.append((f"line {row}: {label}", mutant_source))
                if len(mutants) >= limit:
                    return mutants
    except tokenize.TokenError:
        pass
    return mutants


def _fallback_sweep(source_code: str, test_code: str, timeout_seconds: int,
                    max_mutants: int = 48) -> dict[str, Any]:
    deadline = time.monotonic() + max(2, min(timeout_seconds, 45))
    baseline_timeout = max(1, min(10, deadline - time.monotonic()))
    baseline = run_pytest(source_code, test_code, timeout_seconds=baseline_timeout, collect_coverage=True)
    if not baseline["passed"]:
        return {"status": "baseline_failed", "engine": "fallback_token", "evaluation_scope": "reduced_fallback",
                "full_mutation_score_available": False, "total": 0, "killed": 0, "survived": [],
                "details": [], "baseline": baseline}
    details = []
    survivors = []
    inconclusive = []
    mutants = _operator_mutants(source_code, max_mutants)
    for label, mutant_source in mutants:
        remaining = deadline - time.monotonic()
        if remaining < 1:
            break
        result = run_pytest(mutant_source, test_code, timeout_seconds=max(1, min(8, remaining)))
        # Only an ordinary pytest failure counts as killed. Timeouts/tool errors are inconclusive.
        test_status = result.get("status")
        test_output = result.get("output", "")
        collection_error = any(marker in test_output for marker in (
            "ERROR collecting", "SyntaxError:", "ImportError while importing test module",
            "ModuleNotFoundError:", "No module named pytest"))
        killed = test_status == "failed" and not collection_error
        item = {"mutant": label, "killed": killed, "test_status": test_status,
                "inconclusive_reason": "Mutant/test collection failed before assertions could evaluate." if collection_error else None,
                "test_output": test_output[-1200:]}
        details.append(item)
        if test_status == "passed":
            survivors.append(label)
        elif not killed:
            inconclusive.append(label)
    total = len(details)
    killed_count = sum(1 for item in details if item["killed"])
    complete = len(details) == len(mutants)
    return {"status": "completed", "engine": "fallback_token", "evaluation_scope": "reduced_fallback",
            "full_mutation_score_available": False, "evaluation_complete": complete,
            "total": total, "killed": killed_count, "survived": survivors, "inconclusive": inconclusive,
            "score_percent": round((killed_count / total) * 100, 2) if total else None,
            "details": details, "baseline": baseline,
            "limitations": ["Reduced token/constant mutation set; not equivalent to a full mutmut run.",
                            "A 100% fallback score applies only to mutants listed in this result.",
                            "Timed-out or errored mutant executions are inconclusive, not killed."]}


def _mutmut_supported_here() -> bool:
    return os.name != "nt" and sys.platform != "win32"


def run_mutmut(source_code: str, test_code: str, timeout_seconds: int = 45,
               prefer_fallback: bool = False) -> dict[str, Any]:
    """Run mutmut on supported platforms; otherwise transparently use the fallback."""
    if prefer_fallback or not _mutmut_supported_here():
        reason = ("Supervisor selected fallback after a previous mutmut failure." if prefer_fallback else
                  "Native Windows is unsupported by mutmut. Run this project under WSL/Linux/Docker for full mutmut support.")
        result = _fallback_sweep(source_code, test_code, min(timeout_seconds, 45), max_mutants=48)
        result.update({"fallback_reason": reason, "mutmut_attempted": False})
        return result

    fallback_reason = None
    with tempfile.TemporaryDirectory(prefix="mgts-mutmut-") as temp:
        root = Path(temp)
        (root / "candidate.py").write_text(source_code, encoding="utf-8")
        tests_dir = root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_candidate.py").write_text(test_code, encoding="utf-8")
        (root / "pyproject.toml").write_text(
            '[tool.mutmut]\nsource_paths = ["candidate.py"]\npytest_add_cli_args_test_selection = ["tests/"]\n', encoding="utf-8"
        )
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
                # mutmut 3 prints progress such as "6/6  <party> 3 ... <frown> 3"; read the last progress line.
                progress = re.findall(r"(\d+)/(\d+)\s+\U0001F389\s*(\d+)", run_output.replace("\r", "\n"))
                if progress:
                    _, total_text, killed_text = progress[-1]
                    killed, total = int(killed_text), int(total_text)
                else:
                    killed, total = None, None
                return {"status": "completed", "engine": "mutmut", "evaluation_scope": "mutmut",
                        "full_mutation_score_available": bool(total), "evaluation_complete": True,
                        "total": total, "killed": killed, "survived": survivors,
                        "results_output": results_text, "run_output": run_output,
                        "score_percent": round(killed / total * 100, 2) if total else None,
                        "mutmut_attempted": True}
            fallback_reason = f"mutmut exit code {proc.returncode}: {run_output[-2500:]}"
        except subprocess.TimeoutExpired:
            fallback_reason = f"mutmut exceeded {timeout_seconds}s timeout"
        except Exception as exc:
            fallback_reason = f"mutmut invocation failed: {type(exc).__name__}: {exc}"

    # Do not stop the run at the known tool limitation; provide a clearly scoped fallback result.
    result = _fallback_sweep(source_code, test_code, min(timeout_seconds, 45), max_mutants=48)
    result.update({"fallback_reason": fallback_reason, "mutmut_attempted": True})
    return result
