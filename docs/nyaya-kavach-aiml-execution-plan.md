# Nyaya Kavach — Phase 1 (Kavach) — AIML Engineer's Execution Plan

**Your ownership:** Data processing, ML training, external LLM integration, AI agents.
**Locked scope:** Madhya Pradesh law · Hindi + English · No legal-literate teammate · Document sourcing via internet (template-based bootstrap, to be replaced with real field documents before final demo).

**Working principle:** Build strictly in order. Each step's output is the next step's input — don't parallelize until the chain is proven end-to-end once, even at toy scale.

---

## ✅ Step 1 — Taxonomy (DONE)

**Document types (MVP):** Loan/moneylending chit · Land lease/tenancy · Labor contract · Other/unsupported
*(Contract-farming dropped for MVP, revisit Semester 2)*

**Clause categories (shared, 13 tags):**
1. Interest / finance charge terms
2. Principal & repayment schedule
3. Penalty / default consequences
4. Duration / term
5. Termination / notice period
6. Wage / payment terms
7. Working hours / conditions
8. Ownership / transfer
9. Security / collateral / pledge
10. Mandatory disclosure / documentation compliance
11. Dispute resolution
12. Renewal / auto-renewal
13. Other / uncategorized (catch-all — mandatory, don't force-fit messy real clauses into a wrong tag)

This taxonomy is the backbone for: segmenter output tags, synthetic data categories, risk-engine rule keys, and RAG corpus tagging.

---

## ⏭️ Step 2 — Legal Corpus + Document Sourcing (NEXT — not started)

**Known risk to flag to supervisor now:** no legal-literate teammate. Mitigation: primary-source-only research (India Code, official gazette, state govt portals), never secondary blogs, for anything that becomes a hardcoded threshold.

**Track A — Legal Corpus (primary sources only):**
- [ ] MP Moneylenders Act, 1934 + **2020 Amendment** (confirm exact interest cap % — original 1934 Act had NO cap; the cap came from the 2020 amendment, verify the number from an official source, not a secondary summary)
- [ ] Usurious Loans Act, 1918 (central act, applies alongside MP Act)
- [ ] MP Land Revenue Code, 1959 (tenancy/lease-relevant sections)
- [ ] Minimum Wages Act, 1948 + **current** MP state minimum wage notification (revised periodically — get the current rate, not a stale figure)
- [ ] Contract Labour (Regulation & Abolition) Act, 1970

**Track B — Document Sourcing (internet bootstrap):**
- [ ] Loan-chit / promissory note templates (Hindi + English)
- [ ] Agricultural land lease agreement templates (India/MP context)
- [ ] Informal labor contract / daily-wage agreement templates
- [ ] **Label this batch "template-sourced, not field-sourced"** in dataset metadata from day one — this is an honest limitation to disclose later, not something to obscure

**Exit criteria for Step 2:** a folder of ~15-30 template/sample documents (mix of the 3 doc types) + a plain-text simplified corpus of the 5 statutes above, each chunked by section with a citation tag (act name + section number).

---

## Step 3 — Dataset & Labeling Schema Design (not started)

Before writing the segmenter or generating synthetic data, define:
- [ ] JSON schema for a labeled clause: `{ text, doc_type, clause_category, risk_relevant: bool }`
- [ ] Labeling format for the synthetic data generation step (Stage 1.2 in team roadmap) — must match what the fine-tuning step (Stage 1.3) expects as input
- [ ] Confirm this schema against the API contract Java/Spring Boot expects (don't design in isolation — check Stage 0's Swagger/OpenAPI draft)

---

## Step 4 — Rule-Based Segmenter (Team Roadmap Task 1.1)

- [ ] Whitespace/paragraph chunking script on OCR text
- [ ] Regex for bullet points / localized legal keywords (Hindi + English)
- [ ] Output: `List[String]` per team's API contract
- [ ] Test against the messy template documents from Step 2, not clean text you typed yourself

---

## Step 5 — Synthetic Data Generation (Team Roadmap Task 1.2)

- [ ] Manually label ~20 real chunks first (from Step 4's output) across the 13 clause categories
- [ ] Write system prompt for LLM-based synthetic generation, seeded with those 20 examples
- [ ] Generate 1,000+ synthetic chunks across categories
- [ ] Human spot-check for hallucination / unnatural Hindi phrasing

---

## Step 6 — Model Fine-Tuning (Team Roadmap Task 1.3)

- [ ] Convert synthetic + real labeled data into HF dataset format
- [ ] Fine-tune IndicBERT (or similar) for sequence classification (13-class + doc-type, multi-label per context doc §5.1 edge case)
- [ ] Serve via lightweight FastAPI/Flask wrapper

---

## Step 7 — Vector DB + Legal RAG Corpus (Team Roadmap Task 3.1)

- [ ] Enable pgvector
- [ ] Embed Step 2's chunked legal corpus with a multilingual embedding model
- [ ] Store with citation metadata (act name, section number)

---

## Step 8 — Dual-Layer Risk Engine (Team Roadmap Task 3.2)

- [ ] Deterministic layer: hardcode ONLY verified thresholds from Step 2 Track A (e.g., MP moneylending interest cap, minimum wage floor)
- [ ] ML layer: call Step 6's fine-tuned model for soft-risk patterns
- [ ] Combine into single risk verdict JSON

---

## Step 9 — RAG Explanation Generation (Team Roadmap Task 3.3)

- [ ] Retrieval: flagged clause → embedding → similarity search against Step 7's vector table
- [ ] Prompt LLM: clause + retrieved law → plain-language Hindi/English explanation
- [ ] Must always cite which act/section triggered the flag (never a bare "this seems risky")

---

## Step 10 — Integration & Testing (Team Roadmap Stage 5)

- [ ] Hand off pipeline output to Java/Spring Boot per API contract
- [ ] Run template documents (and any real documents secured by then) end-to-end
- [ ] Compare AI verdicts against your own best-effort legal reasoning (since no lawyer is on the team yet — flag any case you're unsure about rather than guessing)

---

## Open risks to keep surfacing to your supervisor
1. No legal-literate teammate — verification gap on legal thresholds.
2. Documents are template-sourced, not field-sourced, for MVP — may not generalize to real messy handwriting/formatting.
3. Segmentation on messy real documents is explicitly the hardest NLP problem in this project (per project context doc) — budget slack time here, don't assume Step 4 is quick.
