from tools.pytest_runner import run_pytest


def test_runner_passes_a_correct_test():
    result = run_pytest("def add(a, b): return a + b\n",
                        "from candidate import add\ndef test_add(): assert add(2, 3) == 5\n")
    assert result["status"] == "passed"
    assert result["passed"] is True


def test_runner_reports_failure():
    result = run_pytest("def add(a, b): return a + b\n",
                        "from candidate import add\ndef test_add(): assert add(2, 3) == 6\n")
    assert result["status"] == "failed"
    assert result["passed"] is False
