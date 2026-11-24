"""
eval_retrieval.py - Step 7 exit test.

Question answered: for clauses we already labeled with the law they relate to
(related_provision_ids), does retrieve_relevant_law() actually return that law?

Reports hit@1 and hit@3 (hit = ANY linked provision appears in the top-k), a
per-provision breakdown, and the worst misses so you can see WHY retrieval fails.

HONEST LIMITS - read before quoting a number:
  * The links are our own labels, partly AI-assigned during the review, so this
    is a proxy for retrieval quality, not courtroom ground truth.
  * 'usurious-loans-1918-s3-reopening' is attached to ~all 162 reviewed
    high-risk clauses as a generic "harsh bargain" link. It is a vague target,
    so it is reported separately and not mixed into the headline number.

Usage (from ml-pipeline/rag/, with the DB up and embed_legal_corpus.py already run):
    python eval_retrieval.py                 # all linked examples
    python eval_retrieval.py --limit 40      # quick smoke test
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import search_legal_corpus as S

DATA = Path(__file__).parent.parent / "synthetic-data" / "combined_training_data.json"
GENERIC = "usurious-loans-1918-s3-reopening"


def evaluate(limit: int | None, top_k: int = 3, verbose: bool = True):
    data = [d for d in json.loads(DATA.read_text(encoding="utf-8")) if d.get("related_provision_ids")]
    if limit:
        data = data[:limit]

    # Headline set: examples that have at least one SPECIFIC (non-generic) link.
    # For those, only the specific links count as the target.
    rows = []
    for d in data:
        specific = [p for p in d["related_provision_ids"] if p != GENERIC]
        target = specific if specific else d["related_provision_ids"]
        got = [r["provision_id"] for r in S.retrieve_relevant_law(d["text"], top_k=top_k)]
        rows.append({
            "clause_id": d["clause_id"], "text": d["text"], "kind": "specific" if specific else "generic-only",
            "target": target, "got": got,
            "hit1": bool(got) and got[0] in target, "hitk": any(g in target for g in got),
        })

    def summarize(subset, name):
        n = len(subset)
        if not n:
            return
        print(f"{name:<34} n={n:<4} hit@1={sum(r['hit1'] for r in subset)/n:6.1%}   hit@{top_k}={sum(r['hitk'] for r in subset)/n:6.1%}")

    print("\n=== Retrieval results ===")
    summarize([r for r in rows if r["kind"] == "specific"], "HEADLINE (specific-law clauses)")
    summarize([r for r in rows if r["kind"] == "generic-only"], "generic-only (vague target)")
    summarize(rows, "all linked clauses")

    per = defaultdict(list)
    for r in rows:
        if r["kind"] == "specific":
            for t in r["target"]:
                per[t].append(r["hitk"])
    print(f"\nPer-provision recall@{top_k} (specific-law clauses):")
    for pid, hits in sorted(per.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        print(f"  {sum(hits)/len(hits):6.1%}  ({len(hits):>3} clauses)  {pid}")

    misses = [r for r in rows if r["kind"] == "specific" and not r["hitk"]]
    print(f"\nWorst misses ({len(misses)} total, showing up to 8):")
    for r in misses[:8]:
        print(f"  - {r['clause_id']}: \"{r['text'][:90]}\"\n      wanted {r['target']}  got {r['got']}")

    out = Path(__file__).parent / "retrieval_eval_report.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFull per-clause results written to {out.name}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--top-k", type=int, default=3)
    a = ap.parse_args()
    S._get_model()   # load once up front
    evaluate(a.limit, a.top_k)
