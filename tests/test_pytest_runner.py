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


def test_runner_collects_coverage_when_requested():
    result = run_pytest("def choose(x):\n    if x > 0:\n        return 1\n    return 0\n",
                        "from candidate import choose\ndef test_positive(): assert choose(1) == 1\n",
                        collect_coverage=True)
    assert result["passed"] is True
    assert result["coverage"]["status"] in {"collected", "unavailable"}
    if result["coverage"]["status"] == "collected":
        assert result["coverage"]["statement_percent"] < 100
        assert result["coverage"]["missing_lines"]
