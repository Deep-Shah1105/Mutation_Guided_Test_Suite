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


def test_fallback_mutator_includes_constant_mutations():
    mutants = _operator_mutants("def shipping(weight):\n    return 40 + 8 * weight\n", limit=20)
    assert any("constant" in label for label, _ in mutants)


def test_fallback_result_does_not_claim_full_mutation_score():
    result = _fallback_sweep("def add(a, b): return a + b\n",
                             "from candidate import add\ndef test_add(): assert add(2, 3) == 5\n",
                             timeout_seconds=12, max_mutants=2)
    assert result["evaluation_scope"] == "reduced_fallback"
    assert result["full_mutation_score_available"] is False
    assert result["engine"] == "fallback_token"


def test_windows_limitation_uses_transparent_fallback(monkeypatch):
    import tools.mutmut_runner as runner
    monkeypatch.setattr(runner, "_mutmut_supported_here", lambda: False)
    result = runner.run_mutmut("def add(a, b): return a + b\n",
                               "from candidate import add\ndef test_add(): assert add(2, 3) == 5\n",
                               timeout_seconds=8)
    assert result["engine"] == "fallback_token"
    assert result["status"] == "completed"
    assert result["mutmut_attempted"] is False
    assert "Windows" in result["fallback_reason"]
    assert result["full_mutation_score_available"] is False
