"""CLI runner: python run.py --file examples/sample_function.py --function clamp"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from core.service import run_generation


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Mutation-guided pytest test suite generator")
    parser.add_argument("--file", default="examples/sample_function.py", help="Python file containing the function")
    parser.add_argument("--function", default=None, help="Top-level function to test (required if file contains multiple functions)")
    parser.add_argument("--notes", default="", help="Expected behavior or additional context")
    parser.add_argument("--max-rounds", type=int, default=None, help="Maximum mutation-feedback rounds (1-5)")
    parser.add_argument("--trace", default=None, help="JSONL trace path; defaults to TRACE_PATH or trace.jsonl")
    args = parser.parse_args()
    source = Path(args.file).read_text(encoding="utf-8")
    result = run_generation(source, args.function, args.notes, args.max_rounds, args.trace)
    print(json.dumps({"run_id": result.get("run_id"), "report": result.get("report"),
                      "generated_tests": result.get("generated_tests"),
                      "pytest_result": result.get("pytest_result"),
                      "mutation_result": result.get("mutation_result"),
                      "trace_path": result.get("trace_path", args.trace or os.getenv("TRACE_PATH", "trace.jsonl"))},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
