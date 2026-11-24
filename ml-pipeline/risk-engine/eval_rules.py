"""
eval_rules.py - how good are the deterministic rules, measured against our labels?

Two subsets, reported separately on purpose:
  DEV    - hand-written seeds + the 162 reviewed day-2 examples. These were read closely
           while the rules were designed, so numbers here are optimistic.
  UNSEEN - Ollama batch, day-1 Gemini batch, and the 337 day-2 examples nobody reviewed.
           Rules were NOT tuned on these. This is the number to quote.

HONEST LIMITS
  * Labels are LLM-generated (plus our review), not courtroom truth. "Wrong" can mean
    the label is wrong. Always read the errors, don't just trust the percentage.
  * A rule that doesn't fire is NOT "safe": the clause goes on to the LLM-judgment layer
    (Step 9). So low recall is expected - rules only cover clear, checkable patterns.
    PRECISION is the number that matters most here: when a rule says "high", is it right?

Usage:  python eval_rules.py --subset dev --errors 12
        python eval_rules.py --subset unseen
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from deterministic_rules import run_rules

ROOT = Path(__file__).parent.parent
DATA = ROOT / "synthetic-data" / "combined_training_data.json"
REVIEW = ROOT / "synthetic-data" / "high_risk_review.csv"


def split():
    reviewed = {r["text"].strip() for r in csv.DictReader(open(REVIEW, encoding="utf-8-sig"))}
    dev, unseen = [], []
    for d in json.loads(DATA.read_text(encoding="utf-8")):
        cid = d["clause_id"]
        is_dev = (not cid.startswith(("gemini-", "ollama-"))) or (cid.startswith("gemini-d2") and d["text"].strip() in reviewed)
        (dev if is_dev else unseen).append(d)
    return dev, unseen


def outcome(d):
    hits = run_rules(d["text"], d["doc_type"])
    return (hits[0].severity if hits else "none"), hits


def report(items, name, show_errors):
    rows = [(d, *outcome(d)) for d in items]
    print(f"\n{'=' * 78}\n{name}: {len(rows)} clauses\n{'=' * 78}")

    labels = ["high", "medium", "low", "not_applicable"]
    outs = ["high", "medium", "low", "none"]
    print(f"\nLabel (rows) vs what the rules said (columns):")
    print(f"{'':>16}" + "".join(f"{o:>9}" for o in outs) + f"{'total':>9}")
    for lab in labels:
        c = Counter(o for d, o, _ in rows if d["risk_label"] == lab)
        print(f"{lab:>16}" + "".join(f"{c[o]:>9}" for o in outs) + f"{sum(c.values()):>9}")

    tp = sum(1 for d, o, _ in rows if o == "high" and d["risk_label"] == "high")
    fired_high = sum(1 for d, o, _ in rows if o == "high")
    label_high = sum(1 for d, _, _ in rows if d["risk_label"] == "high")
    print(f"\nWhen a rule says HIGH: right {tp}/{fired_high} = {tp / fired_high:.1%}  <- precision (the number that matters)" if fired_high else "\nNo HIGH fired.")
    print(f"Of clauses labeled high, rules caught {tp}/{label_high} = {tp / label_high:.1%}  <- recall (the rest go to the LLM layer)" if label_high else "")
    lowfp = sum(1 for d, o, _ in rows if o == "high" and d["risk_label"] in ("low", "not_applicable"))
    print(f"Rules said HIGH on a clause labeled low/not_applicable: {lowfp}  <- the worst kind of mistake (false alarm on a fair clause)")

    per = defaultdict(lambda: [0, 0])
    for d, _, hits in rows:
        for h in hits:
            per[h.rule_id][0] += 1
            per[h.rule_id][1] += d["risk_label"] == h.severity or (h.severity == "high" and d["risk_label"] == "high")
    print("\nPer rule (fires / label agrees with the rule's severity):")
    for rid, (n, ok) in sorted(per.items()):
        print(f"  {rid:<38} fires {n:>3}   agrees {ok / n:6.1%}")

    if show_errors:
        fps = [(d, h) for d, o, h in rows if o == "high" and d["risk_label"] != "high"]
        fns = [(d, h) for d, o, h in rows if o != "high" and d["risk_label"] == "high"]
        print(f"\n--- rule HIGH but label is not high ({len(fps)}), first {show_errors} ---")
        for d, h in fps[:show_errors]:
            print(f"  [{d['risk_label']}] {d['clause_id']}: {d['text'][:110]}\n      fired {h[0].rule_id} on: {h[0].evidence!r}")
        print(f"\n--- label high but rules did NOT say high ({len(fns)}), first {show_errors} ---")
        for d, h in fns[:show_errors]:
            print(f"  {d['clause_id']} [{d['clause_category']}]: {d['text'][:110]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", choices=["dev", "unseen", "all"], default="dev")
    ap.add_argument("--errors", type=int, default=0)
    a = ap.parse_args()
    dev, unseen = split()
    if a.subset in ("dev", "all"):
        report(dev, "DEV (designed against - optimistic)", a.errors)
    if a.subset in ("unseen", "all"):
        report(unseen, "UNSEEN (not tuned on - the honest number)", a.errors)
