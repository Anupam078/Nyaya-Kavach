"""
Merges every labeled data source into one final training dataset:
  - seed_labeled_clauses.json       (27 hand-labeled real chunks)
  - synthetic_batch_01.json         (30 directly-authored examples)
  - synthetic_batch_gemini.json     (however many Gemini accepted, after you've
                                      run generate_via_gemini.py and reviewed
                                      review_needed_high_risk.json)
  - synthetic_batch_ollama.json     (however many Ollama accepted, after you've
                                      run generate_via_ollama.py and reviewed
                                      review_needed_high_risk.json)

Run this AFTER you've done the human review of the high-risk Gemini examples,
not before - this script doesn't know which ones you actually checked.
"""

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
SOURCES = [
    "seed_labeled_clauses.json",
    "synthetic_batch_01.json",
    "synthetic_batch_gemini.json",
    "synthetic_batch_ollama.json"
]


def main():
    combined = []
    for filename in SOURCES:
        path = HERE / filename
        if not path.exists():
            print(f"  Skipping {filename} - not found yet (that's fine if you haven't generated it).")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        combined.extend(data)
        print(f"  {filename}: {len(data)} examples")

    out_path = HERE / "combined_training_data.json"
    out_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nTotal combined: {len(combined)} examples")
    print(f"Written to {out_path}\n")

    print("Category distribution:")
    for cat, n in sorted(Counter(c["clause_category"] for c in combined).items()):
        flag = "  <-- thin, consider generating more" if n < 15 else ""
        print(f"  {cat}: {n}{flag}")

    print("\nRisk label distribution:")
    for risk, n in sorted(Counter(c["risk_label"] for c in combined).items()):
        print(f"  {risk}: {n}")

    print("\nSource breakdown:")
    for source, n in sorted(Counter(c["source"] for c in combined).items()):
        print(f"  {source}: {n}")


if __name__ == "__main__":
    main()
