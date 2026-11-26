"""
analyze_document.py - TODO I: the orchestrator.

    segment -> classify -> risk engine (rules) -> [retrieve law -> LLM] for unresolved clauses -> RiskVerdict

Every heavy dependency is passed in (classify / retrieve / judge), so the whole flow can be tested with
fakes and so the model is loaded ONCE by the service, not per request.

Returns a plain dict shaped like api-contract/openapi.yaml 'RiskVerdict', plus these ADDITIVE fields
(the backend team must be told): 'complete', 'warnings', clause 'needs_human_review',
cited_provisions[].verification_status, and clause_category may be "uncertain".
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
import re
import uuid

ROOT = Path(__file__).resolve().parent.parent
for sub in ("risk-engine", "segmenter", "rag", "fine-tuning"):
    sys.path.insert(0, str(ROOT / sub))

from rule_based_segmenter import segment_document          # noqa: E402
import risk_engine as RE                                    # noqa: E402
import llm_explainer as LLM                                 # noqa: E402

SUPPORTED = {"loan_chit", "land_lease", "labor_contract"}
TOP_K = 3


class UnsupportedDocType(Exception):
    pass


class EmptyText(Exception):
    pass


def detect_language(text: str) -> str:
    dev = len(re.findall(r"[\u0900-\u097F]", text))
    letters = len(re.findall(r"[A-Za-z\u0900-\u097F]", text))
    return "hi" if letters and dev / letters >= 0.3 else "en"


def default_classifier():
    """Real classifier (loads torch + the fine-tuned MURIL model). Call once at service start."""
    from classify_clause import ClauseClassifier
    return ClauseClassifier().classify


def default_retriever():
    """Real retriever (needs the Postgres container up and embed_legal_corpus.py already run)."""
    from search_legal_corpus import retrieve_relevant_law
    return lambda text: retrieve_relevant_law(text, top_k=TOP_K)


def analyze_document(raw_text: str, doc_type: Optional[str], *, classify: Callable, retrieve: Callable,
                     judge: Callable = LLM.judge_clauses, document_id: Optional[str] = None,
                     model_version: str = "unknown") -> dict:
    if not raw_text or not raw_text.strip():
        raise EmptyText("The document text is empty.")
    if doc_type not in SUPPORTED:
        raise UnsupportedDocType(f"doc_type {doc_type!r} is not supported (supported: {sorted(SUPPORTED)}).")
    document_id = document_id or str(uuid.uuid4())

    chunks = [c for c in segment_document(raw_text) if c.strip()]
    if not chunks:
        raise EmptyText("No clauses could be found in the document text.")

    # 1) classify + rules
    assessed = []
    for text in chunks:
        category, confidence = classify(text)
        assessed.append(RE.assess_clause(text, doc_type, category, confidence, doc_text=raw_text))

    # 2) retrieve law + LLM, only for clauses nobody has resolved yet (ONE batched call per 8 clauses)
    pending = [a for a in assessed if a.needs_llm]
    if pending:
        items = []
        for a in pending:
            try:
                provisions = retrieve(a.text)
            except Exception:                       # DB down etc. -> no law -> LLM must say "uncertain"
                provisions = []
            items.append({"text": a.text, "category": a.category, "provisions": provisions, "hints": a.hints})
        verdicts = judge(doc_type, items)
        for a, v in zip(pending, verdicts):
            RE.resolve_with_llm(a, v)

    # 3) assemble the RiskVerdict
    summary = RE.summarize_document(assessed)
    clauses = []
    for i, a in enumerate(assessed, 1):
        clauses.append({
            "clause_id": f"{document_id}-c{i:03d}",
            "text": a.text,
            "language": detect_language(a.text),
            "clause_category": a.category,
            "risk_label": a.risk_label,
            "risk_source": a.risk_source,
            "needs_human_review": a.needs_human_review,
            "explanation_hi": a.explanation_hi,
            "explanation_en": a.explanation_en,
            "cited_provisions": a.cited_provisions,
        })
    return {
        "document_id": document_id,
        "doc_type": doc_type,
        "overall_risk_level": summary["overall_risk_level"],
        "complete": summary["complete"],
        "warnings": summary["warnings"],
        "clauses": clauses,
        "model_version": model_version,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
