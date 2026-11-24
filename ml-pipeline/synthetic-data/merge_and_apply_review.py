"""
merge_and_apply_review.py - replaces merge_all_sources.py.

Fixes two real problems found in combined_training_data.json:

1. The AI review of the 162 high-risk examples (high_risk_review.csv) was
   never applied. The training data still carried the ORIGINAL labels
   (e.g. gemini-0023 as principal_repayment_schedule, note "NOT
   human-reviewed yet"), so the model was trained on uncorrected labels.

2. clause_ids were not unique. Every Gemini run restarts its counter at
   gemini-0001, so the day-1 smoke test and the day-2 batch collided on 50
   ids. That is why the review is matched on TEXT here, not on clause_id:
   matching on id would have "corrected" the wrong (day-1) examples too.

Run from ml-pipeline/synthetic-data/:
    python merge_and_apply_review.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from schemas.clause_schema import LabeledClause

HERE = Path(__file__).parent

SOURCES = [
    "seed_labeled_clauses.json",
    "synthetic_batch_01.json",
    "synthetic_batch_gemini.json",
    "synthetic_batch_ollama.json",
    "synthetic_batch_gemini_day2.json",
]

# Files whose clause_ids are auto-numbered per run, and so collide across runs.
# Their ids get a file tag prefix so every id in the merged set is unique.
AUTO_NUMBERED = {
    "synthetic_batch_gemini.json": "gemini-d1",
    "synthetic_batch_gemini_day2.json": "gemini-d2",
    "synthetic_batch_ollama.json": "ollama",
}

# The review CSV was generated from the day-2 batch's high-risk subset.
REVIEWED_SOURCE = "synthetic_batch_gemini_day2.json"
REVIEW_CSV = HERE / "high_risk_review.csv"


def load_review() -> dict[str, dict]:
    """text -> review row. Text is unique across the dataset (checked), so it is a safe key."""
    with open(REVIEW_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    bad = [r["clause_id"] for r in rows if r["decision"].strip().lower() not in ("keep", "edit")]
    if bad:
        sys.exit(f"{len(bad)} review rows have a decision other than keep/edit (e.g. {bad[:3]}). "
                 f"This script only applies keep/edit; handle reject/flag_for_human first.")
    return {r["text"].strip(): r for r in rows}


def main():
    review = load_review()
    print(f"Loaded {len(review)} review decisions from {REVIEW_CSV.name}\n")

    merged, stats = [], Counter()
    for fname in SOURCES:
        path = HERE / fname
        if not path.exists():
            print(f"  skipping {fname} (not found)")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"  {fname}: {len(data)} examples")
        tag = AUTO_NUMBERED.get(fname)

        for item in data:
            if tag:
                item["clause_id"] = f"{tag}-{item['clause_id'].split('-')[-1]}"

            if fname == REVIEWED_SOURCE:
                row = review.get(item["text"].strip())
                if row:
                    stats["review_matched"] += 1
                    if row["decision"].strip().lower() == "edit" and row["corrected_clause_category"].strip():
                        item["clause_category"] = row["corrected_clause_category"].strip()
                        stats["category_corrected"] += 1
                    provs = [p for p in row["added_provision_id"].split(";") if p]
                    item["related_provision_ids"] = sorted(set(item.get("related_provision_ids", [])) | set(provs))
                    item["notes"] = row["reviewer_notes"].strip() or item.get("notes")
                    stats["provisions_added"] += len(provs)
            merged.append(item)

    # Validate everything against the schema, and enforce unique ids.
    validated = [LabeledClause(**m) for m in merged]
    ids = [c.clause_id for c in validated]
    dupes = len(ids) - len(set(ids))
    if dupes:
        sys.exit(f"STOP: {dupes} duplicate clause_ids remain - fix before training.")
    if stats["review_matched"] != len(review):
        print(f"\nWARNING: only {stats['review_matched']} of {len(review)} review rows matched a training example by text.")

    out = HERE / "combined_training_data.json"
    out.write_text(json.dumps([c.model_dump(mode="json") for c in validated], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nTotal: {len(validated)} examples, all clause_ids unique, all schema-valid")
    print(f"Review matched: {stats['review_matched']}  |  categories corrected: {stats['category_corrected']}  |  provision links added: {stats['provisions_added']}")
    print("\nCategory distribution:")
    for k, v in sorted(Counter(c.clause_category.value for c in validated).items()):
        print(f"  {k}: {v}")
    print(f"\nWritten to {out}")
    print("Now re-run fine_tune_indicbert.py - the next training_log.json entry is the first run on corrected labels.")


if __name__ == "__main__":
    main()
