"""
Bulk synthetic data generation via the Gemini API, batched to make daily
quota irrelevant, with built-in automatic quality checks.

SETUP:
1. Get a free API key at https://aistudio.google.com/apikey
2. Set it as an environment variable (never hardcode it in this file):
     Windows (PowerShell):  $env:GEMINI_API_KEY = "your-key-here"
     Mac/Linux:             export GEMINI_API_KEY="your-key-here"
3. pip install requests

USAGE:
    python generate_via_gemini.py --count 1000

Verify your current free-tier model/limits at https://ai.google.dev/gemini-api/docs/rate-limits
before a large run. Confirmed as of this writing: Gemini 2.5 Flash free tier is
10 requests/minute, 250 requests/day - the script's default --delay accounts
for this. This model is labeled "preview" and has unusually tight limits;
gemini-1.5-flash or gemini-2.0-flash-lite have looser limits (15-30 RPM,
1000-1500 RPD) if 2.5 Flash's pacing feels too slow - pass --model to switch.
"""

import argparse
import itertools
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from schemas.clause_schema import LabeledClause

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CATEGORIES = [
    "interest_finance_terms", "principal_repayment_schedule", "penalty_default_consequences",
    "duration_term", "termination_notice_period", "wage_payment_terms", "working_hours_conditions",
    "ownership_transfer", "security_collateral_pledge", "mandatory_disclosure_documentation",
    "dispute_resolution", "renewal_auto_renewal", "other_uncategorized",
]
DOC_TYPES = ["loan_chit", "land_lease", "labor_contract"]
RISK_LEVELS = ["low", "medium", "high"]
LANGUAGES = ["hi", "en"]

SYSTEM_INSTRUCTION = """You generate synthetic training examples for a rural Indian legal-document \
risk classifier (Nyaya Kavach). For each requested slot, write ONE realistic clause (1-3 sentences) \
matching the given doc_type, clause_category, risk_label, and language.

Write in natural, informal register - these are simple rural loan notes, land lease agreements, \
and labor arrangements, often originally handwritten, NOT polished formal legal contracts. Vary \
names, villages, and amounts across examples - do not reuse the same names repeatedly.

For risk_label "high", the clause should contain a genuinely serious issue (e.g. bonded labor \
framing, undefined/unbounded interest, missing required disclosure, wage far below minimum, \
no termination rights). For "low", the clause should be clean and fair. For "medium", it should \
be a real but less severe concern (e.g. harsh but not illegal terms). For "not_applicable" \
(used with other_uncategorized), write plain administrative text like a title, date, or witness line.

Return your response as a JSON array, one object per requested slot, in the exact order given."""

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "doc_type": {"type": "STRING"},
            "clause_category": {"type": "STRING"},
            "risk_label": {"type": "STRING"},
            "language": {"type": "STRING"},
            "text": {"type": "STRING"},
        },
        "required": ["doc_type", "clause_category", "risk_label", "language", "text"],
    },
}

DEVANAGARI_RANGE = re.compile(r'[\u0900-\u097F]')


def build_slot_plan(n: int) -> list[tuple[str, str, str, str]]:
    """Cycles through every (category, doc_type, risk, language) combo to guarantee coverage by design."""
    risk_by_category = {
        # other_uncategorized only makes sense as not_applicable
        "other_uncategorized": ["not_applicable"],
    }
    combos = []
    for category in CATEGORIES:
        risks = risk_by_category.get(category, RISK_LEVELS)
        for doc_type, risk, lang in itertools.product(DOC_TYPES, risks, LANGUAGES):
            combos.append((category, doc_type, risk, lang))

    slots = []
    i = 0
    while len(slots) < n:
        slots.append(combos[i % len(combos)])
        i += 1
    return slots


def call_gemini_batch(slots_batch: list[tuple[str, str, str, str]], model: str, max_retries: int = 4) -> list[dict]:
    slot_desc = "\n".join(
        f"{i+1}. doc_type={d}, clause_category={c}, risk_label={r}, language={l}"
        for i, (c, d, r, l) in enumerate(slots_batch)
    )
    prompt = (
        f"Generate exactly {len(slots_batch)} clauses, one for each numbered slot:\n{slot_desc}\n\n"
        f"Return a JSON array of {len(slots_batch)} objects, in the same order as the slots above."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": RESPONSE_SCHEMA,
        },
    }

    backoff = 20.0  # seconds - starting wait after a 429, doubles each retry
    for attempt in range(max_retries):
        resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=body, timeout=90)
        if resp.status_code == 429:
            wait = backoff * (2 ** attempt)
            print(f"  Rate limited (429). Waiting {wait:.0f}s before retry {attempt+1}/{max_retries}...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)

    raise RuntimeError(f"Still rate-limited after {max_retries} retries - the per-minute pacing (--delay) is likely still too fast, or the daily quota (250 req/day on 2.5 Flash) is exhausted for today.")


def script_matches_language(text: str, language: str) -> bool:
    """Sanity check: does a 'hi' example actually contain Devanagari text?"""
    has_devanagari = bool(DEVANAGARI_RANGE.search(text))
    if language == "hi":
        return has_devanagari
    return True  # not strictly checking English/Latin - "en" examples may still contain proper nouns etc.


def generate(count: int, model: str, batch_size: int, delay_seconds: float) -> tuple[list[LabeledClause], dict]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set. See the setup instructions at the top of this file.")

    slots = build_slot_plan(count)
    accepted: list[LabeledClause] = []
    seen_texts: set[str] = set()
    stats = {"total_requested": len(slots), "duplicates_dropped": 0, "script_mismatch_dropped": 0,
              "schema_invalid_dropped": 0, "api_errors": 0}

    for batch_start in range(0, len(slots), batch_size):
        batch_slots = slots[batch_start:batch_start + batch_size]
        try:
            results = call_gemini_batch(batch_slots, model)
        except RuntimeError as e:
            print(f"\n  STOPPING EARLY at batch {batch_start}: {e}")
            print(f"  Returning the {len(accepted)} examples successfully generated before this point.")
            stats["stopped_early"] = True
            return accepted, stats
        except (requests.RequestException, json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"  Batch at {batch_start} failed ({type(e).__name__}: {e}), skipping this batch.")
            stats["api_errors"] += 1
            time.sleep(delay_seconds)
            continue

        for item in results:
            text = item.get("text", "").strip()
            normalized = re.sub(r'\s+', ' ', text.lower())
            if not text:
                continue
            if normalized in seen_texts:
                stats["duplicates_dropped"] += 1
                continue
            if not script_matches_language(text, item.get("language", "")):
                stats["script_mismatch_dropped"] += 1
                continue
            try:
                clause = LabeledClause(
                    clause_id=f"gemini-{len(accepted)+1:04d}",
                    text=text,
                    language=item["language"],
                    doc_type=item["doc_type"],
                    clause_category=item["clause_category"],
                    risk_label=item["risk_label"],
                    related_provision_ids=[],
                    source="synthetic_llm_generated",
                    notes="Generated via Gemini API - NOT human-reviewed yet.",
                )
            except Exception as e:
                stats["schema_invalid_dropped"] += 1
                continue

            seen_texts.add(normalized)
            accepted.append(clause)

        print(f"  ...{len(accepted)} accepted so far (after {batch_start + len(batch_slots)}/{len(slots)} requested)")
        time.sleep(delay_seconds)

    return accepted, stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--batch-size", type=int, default=15)
    parser.add_argument("--delay", type=float, default=7.0, help="Seconds between API calls. Gemini 2.5 Flash free tier allows 10 requests/minute (6s minimum gap) - 7s leaves safety margin. Lower this only if you've confirmed a higher RPM limit for your model/tier.")
    parser.add_argument("--out", default="synthetic_batch_gemini.json")
    args = parser.parse_args()

    print(f"Generating {args.count} examples via Gemini ({args.model}), batches of {args.batch_size}...\n")
    clauses, stats = generate(args.count, args.model, args.batch_size, args.delay)
    if stats.get("stopped_early"):
        print("\n(Run stopped early due to persistent rate limiting - see message above. Saving partial results.)")

    print(f"\n=== Done ===")
    print(f"Accepted: {len(clauses)}")
    print(f"Dropped - duplicates: {stats['duplicates_dropped']}")
    print(f"Dropped - script mismatch (claimed Hindi, no Devanagari found): {stats['script_mismatch_dropped']}")
    print(f"Dropped - failed schema validation: {stats['schema_invalid_dropped']}")
    print(f"API batch errors: {stats['api_errors']}")

    out_path = Path(__file__).parent / args.out
    out_path.write_text(
        json.dumps([c.model_dump() for c in clauses], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWritten to {out_path}")

    high_risk = [c for c in clauses if c.risk_label.value == "high"]
    review_path = Path(__file__).parent / "review_needed_high_risk.json"
    review_path.write_text(
        json.dumps([c.model_dump() for c in high_risk], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nIMPORTANT: {len(high_risk)} high-risk examples written separately to {review_path}")
    print("Per the roadmap's own 'Human Review' step - review ALL of these before training,")
    print("not just a random sample. A wrong label matters most exactly where risk is highest.")
