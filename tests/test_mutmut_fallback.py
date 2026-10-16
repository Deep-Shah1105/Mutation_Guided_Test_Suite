from tools.mutmut_runner import _operator_mutants, _fallback_sweep


def test_operator_mutator_changes_an_operator():
    mutants = _operator_mutants("def add(a, b):\n    return a + b\n")
    assert mutants
    assert any("+ -> -" in label for label, _ in mutants)


def test_fallback_mutation_sweep_kills_addition_mutant():
    result = _fallback_sweep("def add(a, b): return a + b\n",
                             "from candidate import add\ndef test_add(): assert add(2, 3) == 5\n",
                             timeout_seconds=12, max_mutants=1)
    assert result["engine"] == "fallback_token"
    assert result["status"] == "completed"
    assert result["total"] >= 1
    assert result["killed"] >= 1
