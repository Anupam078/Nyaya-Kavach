"""
Bulk synthetic data generation using a local Ollama model (free, unlimited,
runs on your machine - no API key, no quota).

HONEST QUALITY NOTE: Mistral and Llama 3.1 are noticeably weaker at Hindi
generation than Gemini or Claude. Expect more awkward phrasing, occasional
grammar mistakes, and less natural legal/administrative register in the
Hindi outputs specifically. Recommended usage: run this to get VOLUME
(pushing toward the roadmap's 1,000+ figure), then do a real human spot-check
pass on the Hindi examples specifically before trusting them for fine-tuning -
don't skip the roadmap's own "Human Review" step, it matters more here than
it would with a stronger model.

Requires: Ollama running locally (https://ollama.com), with a model pulled:
    ollama pull mistral
    ollama pull llama3.1

Usage:
    python generate_via_ollama.py --model mistral --count 200
"""

import argparse
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from schemas.clause_schema import LabeledClause

OLLAMA_URL = "http://localhost:11434/api/chat"

CATEGORIES = [
    "interest_finance_terms", "principal_repayment_schedule", "penalty_default_consequences",
    "duration_term", "termination_notice_period", "wage_payment_terms", "working_hours_conditions",
    "ownership_transfer", "security_collateral_pledge", "mandatory_disclosure_documentation",
    "dispute_resolution", "renewal_auto_renewal", "other_uncategorized",
]
DOC_TYPES = ["loan_chit", "land_lease", "labor_contract"]

SYSTEM_PROMPT = """You generate synthetic training examples for a rural Indian legal-document \
risk classifier. You will be given a document type, a clause category, and a risk level. \
Write ONE realistic clause (1-3 sentences) that a real informal rural document of that type \
might contain, matching the given category and risk level. Write in natural, informal register \
- these are NOT polished legal contracts, they are simple rural loan notes, land agreements, \
and labor arrangements, often handwritten originally.

Respond ONLY with a JSON object in this exact format, nothing else, no markdown fences:
{"text": "the clause text", "language": "hi" or "en"}
"""

FEW_SHOT_EXAMPLES = [
    {"doc_type": "loan_chit", "category": "interest_finance_terms", "risk": "high",
     "text": "ब्याज हर महीने १०% की दर से बढ़ता रहेगा, चाहे जितना भी समय लगे।"},
    {"doc_type": "labor_contract", "category": "wage_payment_terms", "risk": "low",
     "text": "Wages will be paid every Saturday in cash."},
]


def build_user_prompt(doc_type: str, category: str, risk: str, language: str) -> str:
    examples_text = "\n".join(
        f"- ({ex['doc_type']}, {ex['category']}, risk={ex['risk']}): \"{ex['text']}\""
        for ex in FEW_SHOT_EXAMPLES
    )
    return (
        f"Examples of the expected style:\n{examples_text}\n\n"
        f"Now generate ONE new clause for:\n"
        f"doc_type: {doc_type}\ncategory: {category}\nrisk_level: {risk}\nlanguage: {language}"
    )


def call_ollama(model: str, system: str, user: str) -> str:
    response = requests.post(OLLAMA_URL, json={
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }, timeout=60)
    response.raise_for_status()
    return response.json()["message"]["content"]


def parse_model_output(raw: str) -> dict:
    # Models often wrap JSON in markdown fences despite instructions - strip if present.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    return json.loads(cleaned)


def generate_batch(model: str, count: int) -> list[LabeledClause]:
    results: list[LabeledClause] = []
    risks = ["low", "medium", "high"]
    idx = 0
    attempts = 0
    max_attempts = count * 3  # allow retries for malformed JSON without looping forever

    while len(results) < count and attempts < max_attempts:
        attempts += 1
        doc_type = DOC_TYPES[idx % len(DOC_TYPES)]
        category = CATEGORIES[idx % len(CATEGORIES)]
        risk = risks[idx % len(risks)]
        language = "hi" if idx % 2 == 0 else "en"
        idx += 1

        user_prompt = build_user_prompt(doc_type, category, risk, language)
        try:
            raw_output = call_ollama(model, SYSTEM_PROMPT, user_prompt)
            parsed = parse_model_output(raw_output)
            clause = LabeledClause(
                clause_id=f"ollama-{model}-{len(results)+1:04d}",
                text=parsed["text"],
                language=parsed.get("language", language),
                doc_type=doc_type,
                clause_category=category,
                risk_label=risk,
                related_provision_ids=[],
                source="synthetic_llm_generated",
                notes=f"Generated locally via Ollama/{model}. NOT human-reviewed yet - "
                      f"do the roadmap's human spot-check pass before trusting this for training.",
            )
            results.append(clause)
            if len(results) % 20 == 0:
                print(f"  ...{len(results)}/{count} generated")
        except (json.JSONDecodeError, KeyError, requests.RequestException) as e:
            print(f"  Skipped one malformed generation ({type(e).__name__}), retrying with next slot.")
            continue

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mistral", choices=["mistral", "llama3.1"])
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--out", default="synthetic_batch_ollama.json")
    args = parser.parse_args()

    print(f"Generating {args.count} examples via local Ollama model '{args.model}'...")
    print("Make sure Ollama is running (ollama serve) and the model is pulled.\n")

    batch = generate_batch(args.model, args.count)
    print(f"\nDone: {len(batch)}/{args.count} successfully generated and schema-validated.")

    out_path = Path(__file__).parent / args.out
    out_path.write_text(
        json.dumps([c.model_dump() for c in batch], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written to {out_path}")
    print("\nREMINDER: spot-check a real sample of these (especially the Hindi ones) before")
    print("merging into your training set. Local models are noticeably weaker at Hindi than")
    print("Gemini/Claude - this step matters more here than the roadmap implies for a stronger model.")
