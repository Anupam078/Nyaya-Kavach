"""
risk_engine.py - Step 8 (TODO F): decides, for ONE clause, who produces the verdict.

Order of decisions (the locked design):
  1. Run the deterministic rules on the clause TEXT (never on the classifier's category).
  2. A rule hit decides the verdict ONLY if rule_policy.json marks that rule 'decisive'.
     Rules marked 'llm_review' just pass a hint to the LLM layer.
  3. If no decisive rule fired:
       - classifier confidence < CATEGORY_CONFIDENCE_MIN  -> category becomes "uncertain", goes to the LLM
       - confident other_uncategorized and no hints       -> not_applicable (no LLM call)
       - anything else                                    -> goes to the LLM
  4. summarize_document(): overall = highest severity; complete=False while a clause is unresolved.

Nothing here calls a model, the network or the database, so it is fully unit-testable.

PLACEHOLDERS (not measured yet - calibrate in TODO G from validation predictions):
  CATEGORY_CONFIDENCE_MIN = 0.30, OTHER_SKIP_MIN = 0.60.
  With a classifier at ~50% accuracy, skipping the LLM for a "confident other" clause can hide a
  real risk. If calibration shows high-confidence 'other' predictions are often wrong, set
  OTHER_SKIP_MIN above 1.0 to switch the skip off entirely.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Optional

from deterministic_rules import RuleHit, run_rules, thresholds_warning

HERE = Path(__file__).parent
CORPUS_DIR = HERE.parent.parent / "legal-corpus"
POLICY_PATH = HERE / "rule_policy.json"

CATEGORY_CONFIDENCE_MIN = 0.30
OTHER_SKIP_MIN = 0.60
UNCERTAIN = "uncertain"
OTHER = "other_uncategorized"
RISK_ORDER = {"not_applicable": 0, "low": 1, "medium": 2, "high": 3}

REVIEW_EN = ("This clause could not be checked automatically with enough confidence. "
             "Please have it read by a legal-aid worker or a lawyer before you sign.")
REVIEW_HI = ("इस शर्त की जांच अपने आप पर्याप्त भरोसे के साथ नहीं हो सकी। "
             "हस्ताक्षर से पहले कृपया इसे किसी विधिक सहायता कार्यकर्ता या वकील से पढ़वा लें।")


# ------------------------------------------------------------------ corpus / policy

@lru_cache(maxsize=1)
def load_corpus() -> dict:
    out = {}
    for f in sorted(CORPUS_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for e in data:
                if e.get("provision_id"):
                    out[e["provision_id"]] = e
    return out


def expand_provisions(ids: list) -> list:
    """provision ids -> [{provision_id, act_name, section_number, summary, verification_status}].
    An id that is not in the corpus is dropped: we never cite a law we cannot show."""
    corpus, seen, res = load_corpus(), set(), []
    for pid in ids:
        e = corpus.get(pid)
        if pid in seen or e is None:
            continue
        seen.add(pid)
        res.append({"provision_id": pid, "act_name": e["act_name"], "section_number": e.get("section_number"),
                    "summary": e["simplified_text"], "verification_status": e.get("verification_status")})
    return res


def load_policy() -> dict:
    try:
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def rule_family(rule_id: str) -> str:
    return rule_id.split("_")[0]          # "R9_BELOW_MIN_WAGE" -> "R9"


# ------------------------------------------------------------------ per-clause result

@dataclass
class ClauseAssessment:
    text: str
    category: str                           # a ClauseCategory value, or "uncertain"
    category_confidence: float
    risk_label: Optional[str] = None        # low|medium|high|not_applicable ; None = still unresolved
    risk_source: str = "none"               # deterministic_rule | llm_judgment | none
    needs_llm: bool = False
    needs_human_review: bool = False
    explanation_en: Optional[str] = None
    explanation_hi: Optional[str] = None
    cited_provisions: list = field(default_factory=list)
    rule_ids: list = field(default_factory=list)
    evidence: str = ""
    hints: list = field(default_factory=list)   # RuleHit objects given to the LLM as unconfirmed hints


def assess_clause(text: str, doc_type: Optional[str], category: str, confidence: float,
                  doc_text: Optional[str] = None) -> ClauseAssessment:
    policy = load_policy()
    hits = run_rules(text, doc_type, doc_text)            # most severe first
    decisive = [h for h in hits if policy.get(rule_family(h.rule_id), "llm_review") == "decisive"]
    hints = [h for h in hits if h not in decisive]
    shown = UNCERTAIN if confidence < CATEGORY_CONFIDENCE_MIN else category
    a = ClauseAssessment(text, shown, confidence, hints=hints)

    if decisive:
        top = decisive[0]
        # a LOW decisive hit must not hide a more serious unconfirmed hint
        if not (top.severity == "low" and hints):
            a.risk_label, a.risk_source = top.severity, "deterministic_rule"
            a.explanation_en, a.explanation_hi = top.reason_en, top.reason_hi
            a.rule_ids, a.evidence = [h.rule_id for h in decisive], top.evidence
            a.cited_provisions = expand_provisions([p for h in decisive for p in h.provisions])
            return a

    if shown == OTHER and confidence >= OTHER_SKIP_MIN and not hints:
        a.risk_label, a.risk_source = "not_applicable", "none"
        return a

    a.needs_llm = True
    return a


def resolve_with_llm(a: ClauseAssessment, verdict) -> ClauseAssessment:
    """Fold an LLMVerdict (llm_explainer.LLMVerdict) into the assessment. Never raises."""
    a.needs_llm = False
    a.risk_source = "llm_judgment"
    if verdict is None or verdict.error or verdict.risk_level == "uncertain_needs_human_review":
        # 'medium' + flag is the conservative stand-in: we have NOT measured that it is medium.
        a.risk_label, a.needs_human_review = "medium", True
        a.explanation_en = (verdict.explanation_en if verdict and not verdict.error and verdict.explanation_en else REVIEW_EN)
        a.explanation_hi = (verdict.explanation_hi if verdict and not verdict.error and verdict.explanation_hi else REVIEW_HI)
        a.cited_provisions = expand_provisions([verdict.cited_provision_id]) if verdict and verdict.cited_provision_id else []
        return a
    a.risk_label = verdict.risk_level
    a.explanation_en, a.explanation_hi = verdict.explanation_en, verdict.explanation_hi
    a.cited_provisions = expand_provisions([verdict.cited_provision_id]) if verdict.cited_provision_id else []
    return a


# ------------------------------------------------------------------ whole document

def summarize_document(assessments: list, today: Optional[date] = None) -> dict:
    labels = [a.risk_label for a in assessments]
    resolved = [l for l in labels if l is not None]
    overall = max(resolved, key=lambda l: RISK_ORDER[l]) if resolved else "not_applicable"
    warnings = []
    w = thresholds_warning(today)
    if w:
        warnings.append(w)
    unresolved = sum(1 for l in labels if l is None)
    review = sum(1 for a in assessments if a.needs_human_review)
    if unresolved:
        warnings.append(f"{unresolved} clause(s) were not assessed.")
    if review:
        warnings.append(f"{review} clause(s) need human review.")
    return {"overall_risk_level": overall, "complete": unresolved == 0, "warnings": warnings}
