"""AST-based function inspection; never executes the submitted source."""
from __future__ import annotations
import ast
from typing import Any


def analyse_code(source: str, function_name: str | None = None) -> dict[str, Any]:
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not functions:
        raise ValueError("No top-level Python function was found.")
    selected = next((n for n in functions if n.name == function_name), None) if function_name else None
    if function_name and selected is None:
        raise ValueError(f"Function {function_name!r} was not found at module top level.")
    if selected is None:
        if len(functions) != 1:
            names = ", ".join(n.name for n in functions)
            raise ValueError(f"Found multiple functions ({names}); supply function_name.")
        selected = functions[0]
    nodes = list(ast.walk(selected))
    args = [a.arg for a in selected.args.posonlyargs + selected.args.args + selected.args.kwonlyargs]
    complexity = 1 + sum(isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.Try, ast.ExceptHandler, ast.BoolOp)) for n in nodes)
    constants = sorted({repr(n.value) for n in nodes if isinstance(n, ast.Constant)})
    return {
        "function_name": selected.name,
        "async": isinstance(selected, ast.AsyncFunctionDef),
        "parameters": args,
        "required_positional_parameters": [a.arg for a in selected.args.posonlyargs + selected.args.args][
            : max(0, len(selected.args.posonlyargs + selected.args.args) - len(selected.args.defaults))
        ],
        "line_start": selected.lineno,
        "line_end": getattr(selected, "end_lineno", selected.lineno),
        "decision_complexity_estimate": complexity,
        "branch_count": sum(isinstance(n, (ast.If, ast.IfExp, ast.Match)) for n in nodes),
        "loop_count": sum(isinstance(n, (ast.For, ast.AsyncFor, ast.While)) for n in nodes),
        "exception_count": sum(isinstance(n, (ast.Raise, ast.ExceptHandler)) for n in nodes),
        "calls": sorted({n.func.id if isinstance(n.func, ast.Name) else n.func.attr
                          for n in nodes if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}),
        "constants": constants,
        "source_function": ast.get_source_segment(source, selected) or "",
        "all_top_level_functions": [n.name for n in functions],
    }
