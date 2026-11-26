"""
service/main.py - TODO J: FastAPI wrapper. Synchronous, as agreed for the MVP.

Run (from ml-pipeline/):
    pip install fastapi "uvicorn[standard]" requests
    $env:GEMINI_API_KEY = "..."
    docker compose up -d            # in rag/, so retrieval works
    uvicorn service.main:app --port 8000

Endpoints:  POST /analyze-document   GET /health
Errors (per openapi.yaml): 422 {error_code, message} for empty/unsupported, 500 for pipeline failure.

The classifier is loaded ONCE at startup (it takes seconds and a lot of RAM). If the model folder is
missing the service still starts and /health says classifier_loaded=false; analyze then returns 500.
"""

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import analyze_document as AD  # noqa: E402

STATE = {"classify": None, "retrieve": None, "model_version": "unknown", "load_error": None}


def _model_version() -> str:
    d = AD.ROOT / "fine-tuning" / "indicbert-clause-classifier"
    return f"{d.name}@{datetime.fromtimestamp(d.stat().st_mtime):%Y-%m-%d}" if d.exists() else "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        STATE["classify"] = AD.default_classifier()
        STATE["model_version"] = _model_version()
    except Exception as e:  # noqa: BLE001
        STATE["load_error"] = f"{type(e).__name__}: {e}"
    STATE["retrieve"] = AD.default_retriever()   # lazy: loads the e5 model on first use
    yield


app = FastAPI(title="Nyaya Kavach ML Pipeline API", version="0.1.0", lifespan=lifespan)


class AnalyzeRequest(BaseModel):
    document_id: str
    raw_text: str
    doc_type_hint: Optional[str] = None
    language_hint: Optional[str] = None


def _err(status: int, code: str, msg: str):
    return JSONResponse(status_code=status, content={"error_code": code, "message": msg})


@app.get("/health")
def health():
    return {
        "status": "ok" if STATE["classify"] else "degraded",
        "classifier_loaded": STATE["classify"] is not None,
        "classifier_error": STATE["load_error"],
        "llm_key_present": bool(os.environ.get("GEMINI_API_KEY")),
        "llm_model": AD.LLM.GEMINI_MODEL,
        "thresholds_warning": AD.RE.thresholds_warning(),
    }


@app.post("/analyze-document")
def analyze(req: AnalyzeRequest):
    if not req.raw_text.strip():
        return _err(422, "empty_text", "The document text is empty.")
    if req.doc_type_hint not in AD.SUPPORTED:
        return _err(422, "unsupported_doc_type",
                    "doc_type_hint must be one of loan_chit, land_lease, labor_contract (the pipeline does not infer it).")
    if STATE["classify"] is None:
        return _err(500, "pipeline_failure", f"Classifier not loaded: {STATE['load_error']}")
    try:
        return AD.analyze_document(req.raw_text, req.doc_type_hint, classify=STATE["classify"],
                                   retrieve=STATE["retrieve"], document_id=req.document_id,
                                   model_version=STATE["model_version"])
    except (AD.EmptyText, AD.UnsupportedDocType) as e:
        return _err(422, "empty_text" if isinstance(e, AD.EmptyText) else "unsupported_doc_type", str(e))
    except Exception as e:  # noqa: BLE001
        return _err(500, "pipeline_failure", f"{type(e).__name__}: {e}")
