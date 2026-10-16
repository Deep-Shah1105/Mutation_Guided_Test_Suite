from __future__ import annotations
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from core.service import run_generation

load_dotenv()
app = FastAPI(title="Mutation-Guided Test Suite Generator", version="0.1.0",
              description="Multi-agent pytest test generation with mutation-guided refinement.")

# Set FRONTEND_ORIGINS to a comma-separated list of trusted frontend origins when deployed.
# Local defaults support VS Code Live Server and common local development ports.
_allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class GenerateRequest(BaseModel):
    source_code: str = Field(min_length=1, max_length=20000, description="Python source containing the target function")
    function_name: str | None = Field(default=None, max_length=120)
    request_notes: str = Field(default="", max_length=4000)
    max_rounds: int = Field(default=3, ge=1, le=5)


class GenerateResponse(BaseModel):
    run_id: str
    function_name: str | None = None
    generated_tests: str = ""
    pytest_result: dict = Field(default_factory=dict)
    mutation_result: dict = Field(default_factory=dict)
    report: dict = Field(default_factory=dict)
    trace_path: str = "trace.jsonl"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mutation-guided-test-suite-generator"}


@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        result = run_generation(request.source_code, request.function_name,
                                request.request_notes, request.max_rounds)
        return GenerateResponse(
            run_id=result.get("run_id", "unknown"),
            function_name=result.get("function_name"),
            generated_tests=result.get("generated_tests", ""),
            pytest_result=result.get("pytest_result", {}),
            mutation_result=result.get("mutation_result", {}),
            report=result.get("report", {}),
            trace_path=result.get("trace_path", "trace.jsonl"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {type(exc).__name__}: {exc}") from exc
