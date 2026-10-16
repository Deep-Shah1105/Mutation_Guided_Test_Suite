"""Runs candidate code and generated tests in a temporary subprocess with a timeout.

Important: subprocess + timeout is not a complete security sandbox. Use the Docker
executor before exposing arbitrary untrusted code on a public deployment.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def run_pytest(source_code: str, test_code: str, timeout_seconds: int = 12) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mgts-test-") as temp:
        root = Path(temp)
        (root / "candidate.py").write_text(source_code, encoding="utf-8")
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_candidate.py").write_text(test_code, encoding="utf-8")
        # Do not leak the API key or other parent-process secrets into executed candidate code.
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(root),
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
               "PYTHONPATH": str(root)}
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            if key in os.environ:
                env[key] = os.environ[key]
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests/test_candidate.py"],
                cwd=root, env=env, capture_output=True, text=True,
                timeout=timeout_seconds, check=False,
            )
            output = (proc.stdout + "\n" + proc.stderr).strip()[-12000:]
            return {"status": "passed" if proc.returncode == 0 else "failed",
                    "passed": proc.returncode == 0, "returncode": proc.returncode,
                    "output": output, "timeout": False}
        except subprocess.TimeoutExpired as exc:
            output = ((exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
            return {"status": "timeout", "passed": False, "returncode": None,
                    "output": output[-4000:], "timeout": True}
        except Exception as exc:
            return {"status": "error", "passed": False, "returncode": None,
                    "output": f"{type(exc).__name__}: {exc}", "timeout": False}
