"""
test_pipeline_offline.py - plumbing test with FAKE classifier / retriever / LLM.
Proves the pieces connect and the guard-rails work. It says NOTHING about accuracy.
Run from ml-pipeline/:  python tests/test_pipeline_offline.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import analyze_document as AD
import risk_engine as RE

corpus = RE.load_corpus()
FIRST3 = [dict(provision_id=k, act_name=v["act_name"], section_number=v.get("section_number"),
               simplified_text=v["simplified_text"]) for k, v in list(corpus.items())[:3]]

def fake_classify(text):            # deliberately dumb
    return ("other_uncategorized", 0.9) if len(text) < 40 else ("interest_finance_terms", 0.5)

def fake_retrieve(text):
    return FIRST3

def make_post(cited_ok=True):
    def post(body):
        prompt = body["contents"][0]["parts"][0]["text"]
        n = prompt.count("=== Clause ")
        cid = FIRST3[0]["provision_id"] if cited_ok else "made-up-law-id"
        arr = [{"clause_number": i, "risk_level": "high", "explanation_hi": "हिंदी", "explanation_en": "English",
                "cited_provision_id": cid} for i in range(1, n + 1)]
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(arr)}]}}]}
    return post

def judge_with(post):
    import llm_explainer as L
    return lambda dt, items: L.judge_clauses(dt, items, post_fn=post)

def run(path, dt, post):
    return AD.analyze_document(Path(path).read_text(encoding="utf-8"), dt, classify=fake_classify,
                               retrieve=fake_retrieve, judge=judge_with(post))

# 0. every provision id the rules cite must exist in the corpus
import deterministic_rules, re
src = Path(deterministic_rules.__file__).read_text(encoding="utf-8")
ids = set(re.findall(r'"([a-z0-9\-]+-(?:s\d+\w*|[a-z\-]+))"', src)) & set(re.findall(r'"([a-z0-9]+(?:-[a-z0-9]+)+)"', src))
missing = sorted(i for i in set(re.findall(r'"((?:mp-|bonded-|usurious-|code-on-)[a-z0-9\-]+)"', src)) if i not in corpus)
print("rule-cited provision ids missing from corpus:", missing or "none")

# 1. all 12 sample documents
kinds = {"loan-chit": "loan_chit", "land-lease": "land_lease", "labor-contract": "labor_contract"}
for folder, dt in kinds.items():
    for f in sorted((ROOT.parent / "sample-documents" / folder).glob("*.txt")):
        v = run(f, dt, make_post())
        src_count = {}
        for c in v["clauses"]:
            src_count[c["risk_source"]] = src_count.get(c["risk_source"], 0) + 1
        print(f"{f.name:<52} clauses={len(v['clauses']):<3} overall={v['overall_risk_level']:<14} complete={v['complete']} {src_count}")
        assert all(c["risk_label"] for c in v["clauses"])

# 2. a made-up citation must be dropped and routed to human review
v = run(ROOT.parent / "sample-documents/loan-chit/loan-chit-02-highrisk-english.txt", "loan_chit", make_post(cited_ok=False))
llm_clauses = [c for c in v["clauses"] if c["risk_source"] == "llm_judgment"]
assert llm_clauses and all(c["needs_human_review"] and c["risk_label"] == "medium" for c in llm_clauses)
print("fake citation -> human review: OK (", len(llm_clauses), "clauses )")

# 3. LLM failure must not crash the document
def boom(body): raise RuntimeError("HTTP 429")
v = run(ROOT.parent / "sample-documents/loan-chit/loan-chit-02-highrisk-english.txt", "loan_chit", boom)
assert all(c["risk_label"] for c in v["clauses"]) and v["warnings"]
print("LLM outage -> still returns a verdict, warnings:", v["warnings"])

# 4. API errors
for bad, exc in (("", AD.EmptyText), ("text", AD.UnsupportedDocType)):
    try:
        AD.analyze_document(bad, "other_unsupported" if bad else "loan_chit", classify=fake_classify, retrieve=fake_retrieve)
    except exc: pass
    else: raise SystemExit("expected error not raised")
print("422 cases: OK")
