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
    args = [a.arg for a in selected.args.posonlyargs + selected.args.args + selected.args.kwonlyargs]
    return {
        "function_name": selected.name,
        "async": isinstance(selected, ast.AsyncFunctionDef),
        "parameters": args,
        "required_positional_parameters": [a.arg for a in selected.args.posonlyargs + selected.args.args][
            : max(0, len(selected.args.posonlyargs + selected.args.args) - len(selected.args.defaults))
        ],
        "line_start": selected.lineno,
        "line_end": getattr(selected, "end_lineno", selected.lineno),
        "source_function": ast.get_source_segment(source, selected) or "",
        "all_top_level_functions": [n.name for n in functions],
    }
