# Nyaya Kavach (न्याय कवच)

**A legal-protection platform for people who sign contracts they cannot easily read.**
Area: Legal Technology + Document Intelligence · EPICS project, VIT Bhopal University

Nyaya Kavach has two phases that share one data pipeline:

| Phase | Name | Purpose | Status |
|---|---|---|---|
| 1 | **Kavach** (prevention) | Analyse a document *before* signing: flag risky clauses, explain them in Hindi and English, and cite the law. | Built; integration and validation in progress |
| 2 | **Nyaya Setu** (legal aid) | Turn the Phase 1 risk report into a case intake that connects the user to a human lawyer. | Designed, not built |

> **Important:** Nyaya Kavach is an informational triage tool. It is **not legal advice** and does not replace a lawyer.

---

## Phase 1 at a glance

Supported documents: **loan chit**, **land lease**, **labour contract** · Languages: **Hindi, English** · Legal context: **Madhya Pradesh**

```
raw text ─► segment ─► classify ─► rules ─┬─► verdict
                                          └─► retrieve law ─► LLM explanation (guard-railed) ─► verdict
```

1. **Segment**: a rule-based segmenter splits the text into clauses.
2. **Classify**: a fine-tuned `google/muril-base-cased` model assigns one of 13 clause categories.
3. **Rules**: deterministic checks (interest, wages, bonded labour and more) run on the clause text.
4. **Retrieve**: multilingual-e5-base embeddings and PostgreSQL (pgvector) fetch the relevant legal provisions.
5. **Explain**: an LLM (Gemini) writes the explanation, using *only* the retrieved law.
6. **Verdict**: per-clause and overall risk with cited provisions.

### Routing and guard-rails

- A rule decides the verdict on its own **only** if `risk-engine/rule_policy.json` marks it `decisive`. Otherwise its result is a hint to the LLM.
- Low classifier confidence gives the category `uncertain`. A confident `other_uncategorized` clause with no rule hints is `not_applicable`. Everything else goes to the LLM.
- Every LLM citation is checked against the retrieved set. A medium or high verdict without a valid citation becomes `uncertain_needs_human_review`.
- Clause text is treated as data, never as instructions.
- If the LLM or database is unavailable, the document still returns a result with warnings and `needs_human_review` flags.

---

## Repository layout

```
Nyaya-Kavach/
├── docs/                  Project context, execution roadmap, Review 0 deck, Phase 2 build guide
├── legal-corpus/          Curated legal provisions (JSON) used for retrieval and citations
├── sample-documents/      12 sample documents (3 types x compliant/high-risk x English/Hindi)
└── ml-pipeline/
    ├── api-contract/      openapi.yaml and discussion notes (shared with the backend team)
    ├── schemas/           Clause schema
    ├── segmenter/         Rule-based clause segmenter and sample tests
    ├── synthetic-data/    Dataset generation, human review and merge scripts
    ├── fine-tuning/       Fine-tuning script, training log, classifier wrapper
    ├── rag/               docker-compose, schema.sql, embed / search / evaluate retrieval
    ├── risk-engine/       Rules, rule policy, thresholds, risk engine, LLM explainer
    ├── pipeline/          analyze_document.py (the orchestrator)
    ├── service/           FastAPI service (main.py)
    ├── demo/              demo_call.py (readable terminal demo)
    └── tests/             Offline pipeline test with fake model parts
```

The backend/OCR service and the React frontend are maintained by the Frontend & Backend team: [add repository links here].

---

## Quick start (Windows PowerShell)

### 1. Prerequisites
Python 3.10+, Docker Desktop, a Gemini API key, and the fine-tuned classifier folder (weights are not committed; train with `fine-tuning/fine_tune_indicbert.py`).

```powershell
pip install sentence-transformers psycopg2-binary python-dotenv fastapi "uvicorn[standard]" requests
# plus torch and transformers for the classifier (see the header of fine_tune_indicbert.py)
```

### 2. Start the database
```powershell
cd ml-pipeline\rag
Copy-Item env.example .env        # then set the DATABASE_URL port to match docker-compose.yml
docker compose up -d
$env:DATABASE_URL="postgresql://nyaya:<password>@localhost:5433/nyaya_kavach"
python embed_legal_corpus.py      # embeds the legal corpus
python search_legal_corpus.py     # optional: try a clause interactively
python eval_retrieval.py          # optional: measure retrieval
```
If another Postgres already uses port 5432, map Docker to another port (for example `"5433:5432"`) and use that port in `DATABASE_URL`. Environment variables last only for the current terminal window.

### 3. Run the service
```powershell
cd ml-pipeline
$env:DATABASE_URL="..."           # same value as above
$env:GEMINI_API_KEY="..."         # never commit this key
python -m uvicorn service.main:app --port 8000
```
Check `http://localhost:8000/health`: `classifier_loaded` and `llm_key_present` should be `true`. Interactive API docs are at `http://localhost:8000/docs`.

### 4. Run the demo
```powershell
python demo\demo_call.py ..\sample-documents\loan-chit\loan-chit-02-highrisk-english.txt loan_chit
```

### 5. Run the offline test (no model, database or API key needed)
```powershell
python tests\test_pipeline_offline.py
```
This checks that the pieces connect and the guard-rails work. It says nothing about accuracy.

---

## API

| Endpoint | Description |
|---|---|
| `POST /analyze-document` | Body: `document_id`, `raw_text`, `doc_type_hint` (`loan_chit`, `land_lease` or `labor_contract`). Returns a `RiskVerdict`. |
| `GET /health` | Classifier and key status, thresholds warning. |

Errors follow the contract: `422` for empty text or an unsupported type, `500` for a pipeline failure. The full contract is in `ml-pipeline/api-contract/openapi.yaml`.

**Fields added to the contract that the backend team must adopt:** `complete`, `warnings`, clause `needs_human_review`, `cited_provisions[].verification_status`, and the clause category value `uncertain`.

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (embed, search, service) |
| `GEMINI_API_KEY` | Key for the LLM explanation layer |
| `NYAYA_LLM_MODEL` | Optional override of the Gemini model name |
| `NYAYA_LLM_MIN_INTERVAL` | Optional minimum seconds between LLM calls |

---

## Current status and known limitations

Results are baselines, reported as they were measured.

| Item | Result |
|---|---|
| Training data | 706 labelled clauses, 13 categories (synthetic plus human review) |
| Fine-tuning | Run 1: 207 examples, 28.1% accuracy, macro-F1 0.085. Run 2: 706 examples, 53.8%, 0.454. Run 3 (corrected labels): 50.0%, 0.412 |
| Validation set | Only 106 examples, so Run 2 and Run 3 are statistically indistinguishable |
| Deterministic rules | 98% precision on development data; **17.6% on the first unseen test**, cause not yet diagnosed |
| Retrieval | Working; quality evaluation in progress |
| LLM layer | Written and run through the service; not benchmarked |

Known gaps:
- Rule policy (`rule_policy.json`) is **provisional**. Several rules are set to `llm_review` until validated on a fresh, independent test set.
- Confidence thresholds (`CATEGORY_CONFIDENCE_MIN`, `OTHER_SKIP_MIN`) are placeholders awaiting calibration.
- Legal figures such as minimum wages change over time; `law_thresholds.json` raises a staleness warning. Keep the corpus current.
- Hindi and handwriting OCR accuracy are untested (see the backend notes).

---

## Roadmap

### Before Review 2 (finish Phase 1)
- Connect the ML service to the FastAPI backend and the React frontend
- Validate the rules on a fresh test set and re-set `rule_policy.json`
- Longer fine-tuning and calibrated confidence thresholds
- Measure retrieval quality; update wage entries to the latest notification
- End-to-end testing on real photos of documents

### Phase 2: Nyaya Setu (planned)
An agentic pipeline with a human lawyer always in the loop:

| Component | Role |
|---|---|
| Intake agent | Turns "something bad is happening" into structured facts (voice or text) |
| Classifier / router | Categorises the case and sets urgency; danger signals go straight to a human |
| Research agent | Pulls matching statutes with citations from the shared legal knowledge base |
| Drafting agent | Writes a plain-language rights explanation and a draft, watermarked "AI-generated, pending review" |
| Lawyer dashboard | A panel lawyer approves, edits or rejects every draft before release |
| Escalation and tracking | Urgent cases alert the nearest clinic; status is tracked to resolution |

Phase 1 hands over to Phase 2 through "Talk to someone about this", which creates a pre-filled draft case containing the document, risk report and category. See `docs/` for the full Phase 2 build guide.

---

## Team

| AI / ML | Frontend & Backend |
|---|---|
| Anupam Ojha (24BCE10746) | Ayush Mishra (24BEC10012) |
| Rashi Bhatt (24BCE10636) | Om Sinha (24BCY10257) |
| Devang Srivastava (24BCE10124) | Reet Jain (24BCE11435) |

## Security notes
- Never commit `.env` files or API keys. If a key is ever shared in a chat or log, rotate it.
- Documents may contain personal data; treat samples and logs accordingly.

## License
See `LICENSE`.
